"""Dead Letter Queue (DLQ) Service for failed announcements.

Routes failed announcements for operator review and retry.
Handles both state errors (retry) and validation errors (manual review).

**Error Categories:**
- AnnouncementStateError: State machine violation → retry with backoff
- AnnouncementValidationError: Pre-condition failure → manual review
- Timeout/Network: Transient failure → retry with backoff
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from enum import Enum
import logging

from abby_core.database.mongodb import get_database

logger = logging.getLogger(__name__)


class DLQStatus(Enum):
    """DLQ item status."""
    PENDING = "pending"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class DLQErrorCategory(Enum):
    """Error categorization for DLQ routing."""
    STATE_TRANSITION = "state_transition"  # Retry
    VALIDATION = "validation"  # Manual review
    TRANSIENT = "transient"  # Retry with backoff
    UNKNOWN = "unknown"  # Manual review


def get_dlq_collection():
    """Return the MongoDB collection for DLQ items."""
    db = get_database()
    collection = db["content_delivery_dlq"]
    
    # Indexes for efficient querying
    try:
        collection.create_index([("guild_id", 1), ("status", 1), ("created_at", -1)])
        collection.create_index([("announcement_id", 1)])
        collection.create_index([("error_category", 1), ("status", 1)])
        collection.create_index([("next_retry_at", 1)])
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[dlq_service] index creation skipped: {exc}")
    
    return collection


class DLQService:
    """Manages failed announcement routing and retry logic."""
    
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECONDS = 60  # 1 minute
    MAX_BACKOFF_SECONDS = 3600  # 1 hour
    BACKOFF_MULTIPLIER = 2
    
    def __init__(self):
        self.collection = get_dlq_collection()
    
    def route_error(
        self,
        announcement_id: str,
        error_type: type,
        error_message: str,
        guild_id: int,
        operator_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Route a failed announcement to the DLQ.
        
        Args:
            announcement_id: The announcement that failed
            error_type: Exception class (e.g., AnnouncementValidationError)
            error_message: Error description
            guild_id: Guild ID for the announcement
            operator_id: Who was handling the operation
            context: Additional context about the failure
        
        Returns:
            DLQ item ID
        """
        operator_id = operator_id or "system"
        context = context or {}
        
        # Categorize the error
        from abby_core.services.announcement_dispatcher import (
            AnnouncementStateError,
            AnnouncementValidationError,
        )
        
        if issubclass(error_type, AnnouncementStateError):
            error_category = DLQErrorCategory.STATE_TRANSITION
        elif issubclass(error_type, AnnouncementValidationError):
            error_category = DLQErrorCategory.VALIDATION
        else:
            error_category = DLQErrorCategory.UNKNOWN
        
        now = datetime.utcnow()
        next_retry = now + timedelta(seconds=self.INITIAL_BACKOFF_SECONDS)
        
        dlq_item = {
            "announcement_id": ObjectId(announcement_id) if isinstance(announcement_id, str) else announcement_id,
            "guild_id": guild_id,
            "error_type": error_type.__name__,
            "error_message": error_message,
            "error_category": error_category.value,
            "status": DLQStatus.PENDING.value,
            "retry_count": 0,
            "max_retries": self.MAX_RETRIES,
            "operator_id": operator_id,
            "context": context,
            "created_at": now,
            "updated_at": now,
            "next_retry_at": next_retry,
        }
        
        result = self.collection.insert_one(dlq_item)
        dlq_id = str(result.inserted_id)
        
        logger.warning(
            f"[🚫 dlq] ROUTED "
            f"dlq_id={dlq_id[:8]}... "
            f"announcement_id={announcement_id[:8]}... "
            f"guild={guild_id} "
            f"category={error_category.value} "
            f"error='{error_message[:50]}...'"
        )
        
        return dlq_id
    
    def retry_announcement(
        self,
        dlq_id: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Retry a failed announcement.
        
        Args:
            dlq_id: DLQ item ID
            operator_id: Who initiated the retry
        
        Returns:
            True if retry scheduled
        """
        operator_id = operator_id or "system:operator"
        oid = ObjectId(dlq_id)
        
        item = self.collection.find_one({"_id": oid})
        if not item:
            logger.error(f"[🚫 dlq] DLQ item not found: {dlq_id}")
            return False
        
        retry_count = item.get("retry_count", 0) + 1
        if retry_count > item.get("max_retries", self.MAX_RETRIES):
            logger.warning(
                f"[🚫 dlq] MAX_RETRIES exceeded "
                f"dlq_id={dlq_id[:8]}... "
                f"announcement_id={item['announcement_id']}"
            )
            return False
        
        # Calculate next retry time with exponential backoff
        backoff = min(
            self.INITIAL_BACKOFF_SECONDS * (self.BACKOFF_MULTIPLIER ** (retry_count - 1)),
            self.MAX_BACKOFF_SECONDS
        )
        next_retry = datetime.utcnow() + timedelta(seconds=backoff)
        
        result = self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "status": DLQStatus.RETRYING.value,
                "retry_count": retry_count,
                "next_retry_at": next_retry,
                "updated_at": datetime.utcnow(),
                "last_retry_by": operator_id,
            }}
        )
        
        if result.modified_count > 0:
            logger.info(
                f"[🔄 dlq] RETRY_SCHEDULED "
                f"dlq_id={dlq_id[:8]}... "
                f"attempt={retry_count}/{item.get('max_retries')} "
                f"next_in_seconds={int(backoff)} "
                f"operator={operator_id}"
            )
            return True
        
        return False
    
    def resolve_dlq_item(
        self,
        dlq_id: str,
        resolution: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark DLQ item as resolved.
        
        Args:
            dlq_id: DLQ item ID
            resolution: How it was resolved (e.g., "manual_fix", "abandoned")
            operator_id: Who resolved it
        
        Returns:
            True if resolved
        """
        operator_id = operator_id or "system:operator"
        oid = ObjectId(dlq_id)
        
        result = self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "status": DLQStatus.RESOLVED.value,
                "resolution": resolution,
                "resolved_at": datetime.utcnow(),
                "resolved_by": operator_id,
                "updated_at": datetime.utcnow(),
            }}
        )
        
        if result.modified_count > 0:
            item = self.collection.find_one({"_id": oid})
            logger.info(
                f"[✅ dlq] RESOLVED "
                f"dlq_id={dlq_id[:8]}... "
                f"announcement_id={item['announcement_id'] if item else '?'} "
                f"resolution={resolution} "
                f"operator={operator_id}"
            )
            return True
        
        return False
    
    def execute_retry(
        self,
        dlq_id: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Execute a retry for a DLQ item.
        
        Attempts to re-execute the original operation through AnnouncementDispatcher.
        If successful, marks as resolved. If failed, increments retry count or marks as failed.
        
        Args:
            dlq_id: DLQ item ID
            operator_id: Who initiated the retry
        
        Returns:
            True if retry succeeded (item resolved)
            False if retry failed (will retry again or give up)
        """
        from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
        
        operator_id = operator_id or "system:dlq_retry"
        oid = ObjectId(dlq_id)
        
        item = self.collection.find_one({"_id": oid})
        if not item:
            logger.error(f"[🚫 dlq] DLQ item not found for retry: {dlq_id}")
            return False
        
        announcement_id = str(item["announcement_id"])
        error_category = item.get("error_category")
        context = item.get("context", {})
        operation = context.get("operation", "unknown")
        
        dispatcher = get_announcement_dispatcher()
        
        # CRITICAL FIX: Check if announcement is already in a final state before retry
        # This prevents retrying operations on announcements that were already delivered
        from abby_core.services.content_delivery import get_content_delivery_collection
        content_collection = get_content_delivery_collection()
        announcement = content_collection.find_one({"_id": ObjectId(announcement_id)})
        
        if not announcement:
            logger.warning(
                f"[⚠️  dlq] ANNOUNCEMENT_NOT_FOUND "
                f"dlq_id={dlq_id[:8]}... "
                f"announcement_id={announcement_id[:8]}... "
                f"reason=Announcement no longer exists"
            )
            self._mark_permanently_failed(dlq_id, "announcement_not_found")
            return False
        
        # If announcement is already in final state (delivered/archived), abandon retry
        lifecycle_state = announcement.get("lifecycle_state")
        if lifecycle_state in ["delivered", "archived"]:
            logger.warning(
                f"[⚠️  dlq] ANNOUNCEMENT_ALREADY_FINAL "
                f"dlq_id={dlq_id[:8]}... "
                f"announcement_id={announcement_id[:8]}... "
                f"state={lifecycle_state} "
                f"reason=Announcement already in final state, no retry needed"
            )
            self._mark_permanently_failed(dlq_id, "announcement_already_final")
            return False
        
        try:
            # Attempt the original operation based on context
            success = False
            
            if operation == "generate_content":
                # Can't retry generation - would need LLM call
                # Mark as failed permanently
                logger.warning(
                    f"[🔄 dlq] Cannot retry generation operation "
                    f"dlq_id={dlq_id[:8]}... "
                    f"announcement_id={announcement_id[:8]}..."
                )
                self._mark_permanently_failed(dlq_id, "generation_not_retryable")
                return False
            
            elif operation == "queue_for_delivery":
                # Retry queueing
                success = dispatcher.queue_for_delivery(
                    item_id=announcement_id,
                    operator_id=operator_id
                )
            
            elif operation == "deliver":
                # Can't retry delivery without message_id/channel_id
                # These should be in context
                message_id = context.get("message_id")
                channel_id = context.get("channel_id")
                
                if not message_id or not channel_id:
                    logger.warning(
                        f"[🔄 dlq] Cannot retry delivery without message_id/channel_id "
                        f"dlq_id={dlq_id[:8]}..."
                    )
                    self._mark_permanently_failed(dlq_id, "missing_delivery_context")
                    return False
                
                success = dispatcher.deliver(
                    item_id=announcement_id,
                    message_id=message_id,
                    channel_id=channel_id,
                    operator_id=operator_id
                )
            
            else:
                logger.warning(
                    f"[🔄 dlq] Unknown operation type for retry "
                    f"dlq_id={dlq_id[:8]}... "
                    f"operation={operation}"
                )
                self._mark_permanently_failed(dlq_id, "unknown_operation")
                return False
            
            # If successful, resolve the DLQ item
            if success:
                self.resolve_dlq_item(
                    dlq_id=dlq_id,
                    resolution="retry_successful",
                    operator_id=operator_id
                )
                logger.info(
                    f"[✅ dlq] RETRY_SUCCESS "
                    f"dlq_id={dlq_id[:8]}... "
                    f"announcement_id={announcement_id[:8]}... "
                    f"operation={operation}"
                )
                return True
            else:
                # Operation returned False - schedule next retry or give up
                retry_count = item.get("retry_count", 0)
                max_retries = item.get("max_retries", self.MAX_RETRIES)
                
                if retry_count >= max_retries:
                    self._mark_permanently_failed(dlq_id, "max_retries_exceeded")
                    logger.warning(
                        f"[❌ dlq] MAX_RETRIES exceeded "
                        f"dlq_id={dlq_id[:8]}... "
                        f"announcement_id={announcement_id[:8]}..."
                    )
                    return False
                else:
                    # Schedule next retry with exponential backoff
                    self.retry_announcement(dlq_id, operator_id)
                    return False
        
        except Exception as e:
            # Exception during retry - same logic as operation returning False
            retry_count = item.get("retry_count", 0)
            max_retries = item.get("max_retries", self.MAX_RETRIES)
            error_str = str(e)[:50]
            
            # Check for non-retryable errors (missing resource, validation, etc.)
            from abby_core.services.announcement_dispatcher import AnnouncementStateError
            
            if isinstance(e, AnnouncementStateError):
                # Announcement was deleted or state is invalid - don't retry
                logger.warning(
                    f"[⚠️  dlq] ANNOUNCEMENT_NOT_FOUND "
                    f"dlq_id={dlq_id[:8]}... "
                    f"announcement_id={announcement_id[:8]}... "
                    f"reason={error_str}"
                )
                self._mark_permanently_failed(dlq_id, "announcement_not_found")
                return False
            
            # Other exceptions: log without traceback on subsequent retries
            if retry_count > 0:
                logger.warning(
                    f"[🔄 dlq] RETRY_EXCEPTION "
                    f"dlq_id={dlq_id[:8]}... "
                    f"announcement_id={announcement_id[:8]}... "
                    f"error={error_str}"
                )
            else:
                # First attempt: include traceback for debugging
                logger.error(
                    f"[🔄 dlq] RETRY_EXCEPTION "
                    f"dlq_id={dlq_id[:8]}... "
                    f"announcement_id={announcement_id[:8]}... "
                    f"error={error_str}",
                    exc_info=True
                )
            
            if retry_count >= max_retries:
                self._mark_permanently_failed(dlq_id, f"exception: {str(e)[:100]}")
                return False
            else:
                self.retry_announcement(dlq_id, operator_id)
                return False
    
    def _mark_permanently_failed(self, dlq_id: str, reason: str) -> None:
        """Mark DLQ item as permanently failed (no more retries).
        
        Args:
            dlq_id: DLQ item ID
            reason: Reason for permanent failure
        """
        oid = ObjectId(dlq_id)
        self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "status": DLQStatus.ABANDONED.value,
                "resolution": reason,
                "resolved_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }}
        )
        logger.warning(
            f"[❌ dlq] PERMANENT_FAILURE "
            f"dlq_id={dlq_id[:8]}... "
            f"reason={reason}"
        )
    
    def get_pending_retries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get announcements due for retry.
        
        Returns items with status=PENDING or RETRYING that are past their next_retry_at time.
        
        Args:
            limit: Maximum number to return
        
        Returns:
            List of DLQ items ready for retry
        """
        return list(self.collection.find(
            {
                "status": {"$in": [DLQStatus.PENDING.value, DLQStatus.RETRYING.value]},
                "next_retry_at": {"$lte": datetime.utcnow()}
            }
        ).limit(limit))
    
    def get_dlq_summary(self, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of DLQ items.
        
        Args:
            guild_id: Optional guild filter
        
        Returns:
            Dictionary with status counts and summaries
        """
        match = {}
        if guild_id:
            match["guild_id"] = guild_id
        
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        results = list(self.collection.aggregate(pipeline))
        
        summary = {
            "total": sum(r["count"] for r in results),
            "by_status": {r["_id"]: r["count"] for r in results},
            "by_category": {},
        }
        
        # Also group by error category
        category_pipeline = [
            {"$match": match},
            {"$group": {
                "_id": "$error_category",
                "count": {"$sum": 1}
            }}
        ]
        
        category_results = list(self.collection.aggregate(category_pipeline))
        summary["by_category"] = {r["_id"]: r["count"] for r in category_results}
        
        return summary
    
    def get_failure_diagnostics(
        self,
        dlq_item_id: str,
    ) -> Dict[str, Any]:
        """Get detailed diagnostic information for a DLQ item.
        
        **Use Case:** Operator investigating why an announcement failed
        
        Returns comprehensive failure analysis including:
        - Root cause (error category)
        - Full error context
        - Retry history
        - Related metadata
        - Remediation suggestions
        
        Args:
            dlq_item_id: DLQ item ID to diagnose
        
        Returns:
            Dict with diagnostic details
        
        Example:
            diag = dlq_service.get_failure_diagnostics(dlq_item_id)
            print(f"Error: {diag['error_message']}")
            print(f"Category: {diag['category']}")
            print(f"Retries: {diag['retry_count']}/{dlq_service.MAX_RETRIES}")
            print(f"Suggestion: {diag['remediation_suggestion']}")
        """
        try:
            item = self.collection.find_one({"_id": ObjectId(dlq_item_id)})
            if not item:
                return {"error": f"DLQ item not found: {dlq_item_id}"}
            
            # Get related announcement details
            from abby_core.services.content_delivery import get_content_delivery_collection
            announcement = get_content_delivery_collection().find_one(
                {"_id": ObjectId(item.get("announcement_id"))} if item.get("announcement_id") else None
            )
            
            # Determine remediation suggestion based on error category
            category = item.get("error_category", "unknown")
            remediation_map = {
                "state_transition": (
                    "This is a state machine error. The announcement transitioned to an invalid state. "
                    "Review the announcement state and try retrying."
                ),
                "validation": (
                    "This failed validation checks. Likely a data integrity issue. "
                    "Manual intervention may be required. Review error details and fix the underlying cause."
                ),
                "transient": (
                    "This is a transient error (timeout, network, etc.). "
                    "The system will automatically retry. Monitor for recurring failures."
                ),
                "unknown": (
                    "Unknown error category. Check logs and contact support if issue persists."
                ),
            }
            remediation = remediation_map.get(category, "Unknown error - see logs")
            
            # Get retry history
            retry_attempts = item.get("retry_attempts", [])
            
            return {
                "dlq_item_id": str(item.get("_id")),
                "announcement_id": str(item.get("announcement_id")) if item.get("announcement_id") else "unknown",
                "guild_id": item.get("guild_id"),
                "error_message": item.get("error_message"),
                "error_category": category,
                "status": item.get("status", "pending"),
                "created_at": item.get("created_at"),
                "next_retry_at": item.get("next_retry_at"),
                "retry_count": item.get("retry_count", 0),
                "max_retries": self.MAX_RETRIES,
                "context": item.get("context", {}),
                "announcement_title": announcement.get("title") if announcement else "unknown",
                "announcement_state": announcement.get("lifecycle_state") if announcement else "unknown",
                "remediation_suggestion": remediation,
                "retry_attempts": [
                    {
                        "attempt": i + 1,
                        "timestamp": attempt.get("timestamp"),
                        "error": attempt.get("error"),
                    }
                    for i, attempt in enumerate(retry_attempts[:3])  # Last 3 attempts
                ],
            }
        
        except Exception as e:
            logger.error(
                f"[❌ dlq_diagnostics] Failed to get diagnostics for {dlq_item_id}: {e}"
            )
            return {"error": str(e)}



_dlq_service: Optional[DLQService] = None


def get_dlq_service() -> DLQService:
    """Get or create the DLQ service."""
    global _dlq_service
    if _dlq_service is None:
        _dlq_service = DLQService()
    return _dlq_service
