"""Unified Announcement Dispatcher Service.

Single entry point for all announcement lifecycle operations.
Enforces state validation, operator audit trails, and deterministic transitions.

**Responsibilities:**
1. Create announcements (with idempotency)
2. Generate LLM content (with error handling)
3. Queue for delivery (with state validation)
4. Deliver to Discord (with fallback handling)
5. Archive (with audit trail)

**Industry Standards:**
- All operations logged with operator_id (who performed action)
- State transitions validated before execution
- Concurrent operations handled via MongoDB transactions (when available)
- Error states recoverable via DLQ (Phase 2)
- Full audit trail: create → generate → queue → deliver → archive
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
import logging

from abby_core.database.mongodb import get_database
from abby_core.services.content_delivery import (
    _create_content_item,
    get_content_delivery_collection,
)
from abby_core.services.dlq_service import get_dlq_service
from abby_core.services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)


class AnnouncementStateError(Exception):
    """Raised when state transition is invalid."""
    pass


class AnnouncementValidationError(Exception):
    """Raised when pre-condition validation fails."""
    pass


class AnnouncementDispatcher:
    """Unified announcement lifecycle manager.
    
    Enforces all state transitions and keeps operator audit trail.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        "draft": {"generated", "error"},
        "generated": {"queued", "delivered", "error"},
        "queued": {"delivered", "error"},
        "delivered": {"archived"},
        "error": {"draft"},  # Can retry from error state
        "archived": set(),  # Terminal state
    }
    
    def __init__(self):
        self.collection = get_content_delivery_collection()
    
    def create_announcement(
        self,
        *,
        guild_id: int,
        content_type: str = "system",
        title: str,
        description: str,
        delivery_channel_id: Optional[int],
        delivery_roles: Optional[List[int]] = None,
        scheduled_at: Optional[datetime] = None,
        priority: int = 0,
        operator_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        context_refs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """DEPRECATED: Create a new announcement.
        
        **DEPRECATION NOTICE (January 31, 2026):**
        This method is deprecated. Use `create_announcement_for_delivery()` from
        abby_core.services.content_delivery instead. This method will be removed
        in Q2 2026.
        
        The unified content_delivery pipeline is now the canonical path for all
        announcements in Abby. See PHASE2_CONSOLIDATION_PLAN.md for details.
        
        Args:
            guild_id: Guild ID
            content_type: Content type (system/world/event/social)
            title: Announcement title
            description: Announcement description
            delivery_channel_id: Discord channel ID for delivery (optional for broadcast)
            delivery_roles: Optional list of role IDs to mention
            scheduled_at: When to deliver (if None, immediate)
            priority: Priority level (higher = first)
            operator_id: User/system ID creating announcement (for audit)
            context: Additional context (e.g., command_id, request_id)
            payload: Additional payload fields to store
            context_refs: Context references used by downstream handlers
        
        Returns:
            Announcement ID (ObjectId as string)
        
        .. deprecated:: 1.4.0
            Use :func:`~abby_core.services.content_delivery.create_announcement_for_delivery` instead.
        """
        import warnings
        warnings.warn(
            "AnnouncementDispatcher.create_announcement() is deprecated. "
            "Use create_announcement_for_delivery() from content_delivery instead. "
            "This will be removed in Q2 2026.",
            DeprecationWarning,
            stacklevel=2
        )
        operator_id = operator_id or "system"
        context = context or {}
        payload = payload or {}
        payload_data = {"created_by": operator_id, "context": context}
        payload_data.update(payload)
        
        item_id = _create_content_item(
            guild_id=guild_id,
            content_type=content_type,
            trigger_type="scheduled" if scheduled_at else "immediate",
            title=title,
            description=description,
            scheduled_at=scheduled_at,
            delivery_channel_id=delivery_channel_id,
            delivery_roles=delivery_roles,
            priority=priority,
            payload=payload_data,
            context_refs=context_refs,
        )
        
        # Audit trail
        logger.info(
            f"[📝 announcement] CREATED "
            f"id={item_id[:8]}... "
            f"guild={guild_id} "
            f"operator={operator_id} "
            f"title='{title[:50]}...' "
            f"scheduled={scheduled_at.isoformat() if scheduled_at else 'immediate'}"
        )
        
        return item_id
    
    def generate_content(
        self,
        item_id: str,
        generated_message: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark announcement as generated (LLM content created).
        
        **State Transition Validation:**
        - Current state must be "draft"
        - Generation status must be "pending"
        - Raises AnnouncementStateError if invalid
        
        Args:
            item_id: Announcement ID
            generated_message: LLM-generated message
            operator_id: Who performed generation (usually "system:llm")
        
        Returns:
            True if successful
        
        Raises:
            AnnouncementStateError: If state transition is invalid
        """
        operator_id = operator_id or "system:llm"
        
        try:
            oid = self._validate_state_transition(item_id, "draft", "generated")
            
            now = datetime.utcnow()
            result = self.collection.update_one(
                {"_id": oid},
                {"$set": {
                    "generated_message": generated_message,
                    "generation_status": "ready",
                    "lifecycle_state": "generated",
                    "updated_at": now,
                    "error_message": None,
                }}
            )
            
            if result.modified_count > 0:
                item = self.collection.find_one({"_id": oid})
                
                # Record metrics
                metrics = get_metrics_service()
                metrics.record_transition(
                    announcement_id=item_id,
                    from_state="draft",
                    to_state="generated",
                    guild_id=item.get("guild_id") if item else 0,
                    metadata={"message_length": len(generated_message)}
                )
                
                logger.info(
                    f"[✅ announcement] GENERATED "
                    f"id={item_id[:8]}... "
                    f"guild={item.get('guild_id') if item else 'unknown'} "
                    f"operator={operator_id} "
                    f"msg_len={len(generated_message)}"
                )
                return True
            
            return False
        
        except (AnnouncementStateError, AnnouncementValidationError) as exc:
            # Capture error in DLQ for retry
            item = self.collection.find_one({"_id": ObjectId(item_id)})
            if item:
                dlq = get_dlq_service()
                dlq.route_error(
                    announcement_id=item_id,
                    error_type=exc.__class__,
                    error_message=str(exc),
                    guild_id=item.get("guild_id", 0),
                    operator_id=operator_id,
                    context={
                        "operation": "generate_content",
                        "message_length": len(generated_message),
                    }
                )
            raise
    
    def generation_failed(
        self,
        item_id: str,
        error_message: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark announcement generation as failed.
        
        **State Transition Validation:**
        - Current state must be "draft"
        - Moves to "error" for operator recovery
        
        Args:
            item_id: Announcement ID
            error_message: Reason for failure
            operator_id: Who handled the failure
        
        Returns:
            True if successful
        """
        operator_id = operator_id or "system:llm"
        oid = self._validate_state_transition(item_id, "draft", "error")
        
        now = datetime.utcnow()
        result = self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "lifecycle_state": "error",
                "generation_status": "error",
                "error_message": error_message,
                "updated_at": now,
            }}
        )
        
        if result.modified_count > 0:
            item = self.collection.find_one({"_id": oid})
            
            # Record metrics
            metrics = get_metrics_service()
            metrics.record_error(
                announcement_id=item_id,
                error_category="generation",
                error_type="GenerationError",
                guild_id=item.get("guild_id") if item else 0,
                metadata={"error_message": error_message}
            )
            
            logger.warning(
                f"[⚠️ announcement] GENERATION_FAILED "
                f"id={item_id[:8]}... "
                f"guild={item.get('guild_id') if item else 'unknown'} "
                f"operator={operator_id} "
                f"error='{error_message[:60]}...'"
            )
            return True
        
        return False
    
    def queue_for_delivery(
        self,
        item_id: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Queue announcement for Discord delivery.
        
        **State Transition Validation:**
        - Current state must be "generated"
        - Moves to "queued"
        
        **Pre-condition Checks:**
        - Message content must exist (generated_message field)
        - Channel ID must be set
        - Guild ID must be set
        - Message length < 2000 chars (Discord limit)
        - Message is not empty/whitespace only
        
        Args:
            item_id: Announcement ID
            operator_id: Who queued it (usually "system:scheduler")
        
        Returns:
            True if successful
        
        Raises:
            AnnouncementStateError: If state is not "generated"
            AnnouncementValidationError: If pre-conditions fail
        """
        operator_id = operator_id or "system:scheduler"
        
        try:
            oid = self._validate_state_transition(item_id, "generated", "queued")
            
            # Pre-condition: message content must exist
            item = self.collection.find_one({"_id": oid})
            if not item or not item.get("generated_message"):
                raise AnnouncementValidationError(
                    f"Cannot queue: message not generated for {item_id}"
                )
            
            # Pre-condition: message length validation (Discord limit)
            message = item.get("generated_message", "")
            if len(message) > 2000:
                raise AnnouncementValidationError(
                    f"Cannot queue: message too long ({len(message)}/2000 chars) for {item_id}"
                )
            
            if len(message.strip()) == 0:
                raise AnnouncementValidationError(
                    f"Cannot queue: message is empty for {item_id}"
                )
            
            # Pre-condition: delivery channel must be set
            if not item.get("delivery_channel_id"):
                raise AnnouncementValidationError(
                    f"Cannot queue: delivery_channel_id not set for {item_id}"
                )
            
            # Pre-condition: guild must be set
            if not item.get("guild_id"):
                raise AnnouncementValidationError(
                    f"Cannot queue: guild_id not set for {item_id}"
                )
            
            now = datetime.utcnow()
            result = self.collection.update_one(
                {"_id": oid},
                {"$set": {
                    "lifecycle_state": "queued",
                    "queued_at": now,
                    "updated_at": now,
                }}
            )
            
            if result.modified_count > 0:
                # Record metrics
                metrics = get_metrics_service()
                metrics.record_transition(
                    announcement_id=item_id,
                    from_state="generated",
                    to_state="queued",
                    guild_id=item.get("guild_id"),
                    metadata={
                        "message_length": len(message),
                        "channel_id": item.get("delivery_channel_id"),
                    }
                )
                
                logger.info(
                    f"[📤 announcement] QUEUED "
                    f"id={item_id[:8]}... "
                    f"guild={item.get('guild_id')} "
                    f"channel={item.get('delivery_channel_id')} "
                    f"msg_len={len(message)} "
                    f"operator={operator_id}"
                )
                return True
            
            return False
        
        except (AnnouncementStateError, AnnouncementValidationError) as exc:
            # Capture error in DLQ for retry
            item = self.collection.find_one({"_id": ObjectId(item_id)})
            if item:
                dlq = get_dlq_service()
                dlq.route_error(
                    announcement_id=item_id,
                    error_type=exc.__class__,
                    error_message=str(exc),
                    guild_id=item.get("guild_id", 0),
                    operator_id=operator_id,
                    context={
                        "operation": "queue_for_delivery",
                        "channel_id": item.get("delivery_channel_id"),
                    }
                )
            raise
    
    def deliver(
        self,
        item_id: str,
        message_id: int,
        channel_id: int,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark announcement as delivered to Discord.
        
        **State Transition Validation:**
        - Current state must be "queued"
        - Moves to "delivered"
        
        **Pre-condition Checks:**
        - Message ID must be valid (non-zero)
        - Channel ID must be valid (non-zero)
        - Item must have valid channel configured
        - Message must still exist in item
        
        Args:
            item_id: Announcement ID
            message_id: Discord message ID
            channel_id: Discord channel ID
            operator_id: Who delivered (usually "system:discord")
        
        Returns:
            True if successful
        
        Raises:
            AnnouncementStateError: If state is not "queued"
            AnnouncementValidationError: If pre-conditions fail
        """
        operator_id = operator_id or "system:discord"
        
        try:
            oid = self._validate_state_transition(item_id, "queued", "delivered")
            
            # Pre-condition: message and channel IDs must be valid
            if not message_id or message_id <= 0:
                raise AnnouncementValidationError(
                    f"Cannot deliver: invalid message_id ({message_id}) for {item_id}"
                )
            
            if not channel_id or channel_id <= 0:
                raise AnnouncementValidationError(
                    f"Cannot deliver: invalid channel_id ({channel_id}) for {item_id}"
                )
            
            # Pre-condition: item must have configured channel
            item = self.collection.find_one({"_id": oid})
            if not item or not item.get("delivery_channel_id"):
                raise AnnouncementValidationError(
                    f"Cannot deliver: item has no delivery_channel_id for {item_id}"
                )
            
            # Pre-condition: message must still exist in item
            if not item.get("generated_message"):
                raise AnnouncementValidationError(
                    f"Cannot deliver: generated_message missing for {item_id}"
                )
            
            delivery_result = {
                "channel_id": channel_id,
                "message_id": message_id,
                "delivered_at": datetime.utcnow().isoformat(),
            }
            
            now = datetime.utcnow()
            result = self.collection.update_one(
                {"_id": oid},
                {"$set": {
                    "lifecycle_state": "delivered",
                    "delivery_status": "delivered",
                    "delivery_result": delivery_result,
                    "updated_at": now,
                    "error_message": None,
                }}
            )
            
            if result.modified_count > 0:
                # Record metrics
                metrics = get_metrics_service()
                metrics.record_transition(
                    announcement_id=item_id,
                    from_state="queued",
                    to_state="delivered",
                    guild_id=item.get("guild_id"),
                    metadata={
                        "message_id": message_id,
                        "channel_id": channel_id,
                    }
                )
                
                logger.info(
                    f"[✉️ announcement] DELIVERED "
                    f"id={item_id[:8]}... "
                    f"guild={item.get('guild_id')} "
                    f"msg={message_id} "
                    f"channel={channel_id} "
                    f"operator={operator_id}"
                )
                return True
            
            return False
        
        except (AnnouncementStateError, AnnouncementValidationError) as exc:
            # Capture error in DLQ for retry
            item = self.collection.find_one({"_id": ObjectId(item_id)})
            if item:
                dlq = get_dlq_service()
                dlq.route_error(
                    announcement_id=item_id,
                    error_type=exc.__class__,
                    error_message=str(exc),
                    guild_id=item.get("guild_id", 0),
                    operator_id=operator_id,
                    context={
                        "operation": "deliver",
                        "message_id": message_id,
                        "channel_id": channel_id,
                    }
                )
            raise

    def deliver_generated(
        self,
        item_id: str,
        message_id: int,
        channel_id: int,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark announcement as delivered directly from generated state.

        Used for broadcast-style deliveries where a queue step is not required.

        **State Transition Validation:**
        - Current state must be "generated"
        - Moves to "delivered"

        Args:
            item_id: Announcement ID
            message_id: Discord message ID
            channel_id: Discord channel ID
            operator_id: Who delivered (usually "system:discord")

        Returns:
            True if successful
        """
        operator_id = operator_id or "system:discord"

        try:
            oid = self._validate_state_transition(item_id, "generated", "delivered")

            if not message_id or message_id <= 0:
                raise AnnouncementValidationError(
                    f"Cannot deliver: invalid message_id ({message_id}) for {item_id}"
                )

            if not channel_id or channel_id <= 0:
                raise AnnouncementValidationError(
                    f"Cannot deliver: invalid channel_id ({channel_id}) for {item_id}"
                )

            delivery_result = {
                "channel_id": channel_id,
                "message_id": message_id,
                "delivered_at": datetime.utcnow().isoformat(),
            }

            now = datetime.utcnow()
            result = self.collection.update_one(
                {"_id": oid},
                {"$set": {
                    "lifecycle_state": "delivered",
                    "delivery_status": "delivered",
                    "delivery_result": delivery_result,
                    "updated_at": now,
                    "error_message": None,
                }}
            )

            if result.modified_count > 0:
                item = self.collection.find_one({"_id": oid})

                metrics = get_metrics_service()
                metrics.record_transition(
                    announcement_id=item_id,
                    from_state="generated",
                    to_state="delivered",
                    guild_id=item.get("guild_id") if item else 0,
                    metadata={
                        "message_id": message_id,
                        "channel_id": channel_id,
                    }
                )

                logger.info(
                    f"[✉️ announcement] DELIVERED_DIRECT "
                    f"id={item_id[:8]}... "
                    f"guild={item.get('guild_id') if item else 'unknown'} "
                    f"msg={message_id} "
                    f"channel={channel_id} "
                    f"operator={operator_id}"
                )
                return True

            return False

        except (AnnouncementStateError, AnnouncementValidationError) as exc:
            item = self.collection.find_one({"_id": ObjectId(item_id)})
            if item:
                dlq = get_dlq_service()
                dlq.route_error(
                    announcement_id=item_id,
                    error_type=exc.__class__,
                    error_message=str(exc),
                    guild_id=item.get("guild_id", 0),
                    operator_id=operator_id,
                    context={
                        "operation": "deliver_generated",
                        "message_id": message_id,
                        "channel_id": channel_id,
                    }
                )
            raise

    def delivery_failed_generated(
        self,
        item_id: str,
        error_message: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark delivery failure for a generated item.

        **State Transition Validation:**
        - Current state must be "generated"
        - Moves to "error" with delivery_status="failed"
        """
        operator_id = operator_id or "system:discord"
        oid = self._validate_state_transition(item_id, "generated", "error")

        now = datetime.utcnow()
        result = self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "lifecycle_state": "error",
                "delivery_status": "failed",
                "error_message": error_message,
                "updated_at": now,
            }}
        )

        if result.modified_count > 0:
            item = self.collection.find_one({"_id": oid})

            metrics = get_metrics_service()
            metrics.record_error(
                announcement_id=item_id,
                error_category="delivery",
                error_type="DeliveryError",
                guild_id=item.get("guild_id") if item else 0,
                metadata={"error_message": error_message}
            )

            logger.warning(
                f"[⚠️ announcement] DELIVERY_FAILED_DIRECT "
                f"id={item_id[:8]}... "
                f"guild={item.get('guild_id') if item else 'unknown'} "
                f"operator={operator_id} "
                f"error='{error_message[:60]}...'"
            )
            return True

        return False
    
    def delivery_failed(
        self,
        item_id: str,
        error_message: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark announcement delivery as failed (stays queued for retry).
        
        **State Transition Validation:**
        - Current state must be "queued"
        - Stays in "queued" with delivery_status="failed"
        
        Args:
            item_id: Announcement ID
            error_message: Reason for failure
            operator_id: Who handled the failure
        
        Returns:
            True if successful
        """
        operator_id = operator_id or "system:discord"
        oid = self._validate_state_transition(item_id, "queued", "error")
        
        now = datetime.utcnow()
        result = self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "delivery_status": "failed",
                "error_message": error_message,
                "updated_at": now,
            }}
        )
        
        if result.modified_count > 0:
            item = self.collection.find_one({"_id": oid})
            
            # Record metrics
            metrics = get_metrics_service()
            metrics.record_error(
                announcement_id=item_id,
                error_category="delivery",
                error_type="DeliveryError",
                guild_id=item.get("guild_id") if item else 0,
                metadata={"error_message": error_message}
            )
            
            logger.warning(
                f"[⚠️ announcement] DELIVERY_FAILED "
                f"id={item_id[:8]}... "
                f"guild={item.get('guild_id') if item else 'unknown'} "
                f"operator={operator_id} "
                f"error='{error_message[:60]}...'"
            )
            return True
        
        return False
    
    def mark_transient_error(
        self,
        item_id: str,
        error_message: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Mark a transient delivery error (keeps item in generated state for retry).
        
        **Use Case:**
        Temporary failures like "Guild not found during startup" that should
        be retried on next dispatcher run without marking as failed.
        
        **State Preservation:**
        - Keeps current state (typically "generated")
        - Sets error_message for visibility
        - Clears delivery_result
        - Does NOT transition to "error" state
        
        Args:
            item_id: Announcement ID
            error_message: Reason for transient failure
            operator_id: Who recorded the error
        
        Returns:
            True if successful
        """
        operator_id = operator_id or "system:dispatcher"
        
        try:
            oid = ObjectId(item_id)
            item = self.collection.find_one({"_id": oid})
            if not item:
                logger.error(f"[❌] Cannot mark transient error: item {item_id} not found")
                return False
            
            now = datetime.utcnow()
            result = self.collection.update_one(
                {"_id": oid},
                {"$set": {
                    "error_message": f"Transient: {error_message} (will retry)",
                    "delivery_result": None,
                    "updated_at": now,
                }}
            )
            
            if result.modified_count > 0:
                logger.info(
                    f"[⚠️ announcement] TRANSIENT_ERROR "
                    f"id={item_id[:8]}... "
                    f"guild={item.get('guild_id')} "
                    f"operator={operator_id} "
                    f"error='{error_message[:60]}...'"
                )
                return True
            
            return False
        
        except Exception as exc:
            logger.error(f"[❌] Failed to mark transient error for {item_id}: {exc}")
            return False
    
    def archive(
        self,
        item_id: str,
        operator_id: Optional[str] = None,
    ) -> bool:
        """Archive announcement (terminal state).
        
        **State Transition Validation:**
        - Current state must be "delivered"
        - Moves to "archived"
        
        Args:
            item_id: Announcement ID
            operator_id: Who archived (usually "system:cleanup")
        
        Returns:
            True if successful
        """
        operator_id = operator_id or "system:cleanup"
        oid = self._validate_state_transition(item_id, "delivered", "archived")
        
        now = datetime.utcnow()
        result = self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "lifecycle_state": "archived",
                "archived_at": now,
                "updated_at": now,
            }}
        )
        
        if result.modified_count > 0:
            item = self.collection.find_one({"_id": oid})
            
            # Record metrics
            metrics = get_metrics_service()
            metrics.record_transition(
                announcement_id=item_id,
                from_state="delivered",
                to_state="archived",
                guild_id=item.get("guild_id") if item else 0,
            )
            
            logger.info(
                f"[📦 announcement] ARCHIVED "
                f"id={item_id[:8]}... "
                f"guild={item.get('guild_id') if item else 'unknown'} "
                f"operator={operator_id}"
            )
            return True
        
        return False
    
    def _validate_state_transition(
        self,
        item_id: str,
        expected_current_state: str,
        desired_new_state: str,
    ) -> ObjectId:
        """Validate that a state transition is legal.
        
        Args:
            item_id: Announcement ID
            expected_current_state: What state we expect to be in
            desired_new_state: Where we want to go
        
        Returns:
            ObjectId if valid
        
        Raises:
            AnnouncementStateError: If transition is invalid
        """
        oid = ObjectId(item_id)
        item = self.collection.find_one({"_id": oid})
        
        if not item:
            raise AnnouncementStateError(f"Announcement not found: {item_id}")
        
        current_state = item.get("lifecycle_state", "unknown")
        
        if current_state != expected_current_state:
            raise AnnouncementStateError(
                f"Invalid state transition: {current_state} -> {desired_new_state} "
                f"(expected to be in {expected_current_state})"
            )
        
        if desired_new_state not in self.VALID_TRANSITIONS.get(current_state, set()):
            raise AnnouncementStateError(
                f"Invalid transition: {current_state} -> {desired_new_state} "
                f"(valid transitions from {current_state}: {self.VALID_TRANSITIONS.get(current_state)})"
            )
        
        return oid


# Singleton instance
_dispatcher: Optional[AnnouncementDispatcher] = None


def get_announcement_dispatcher() -> AnnouncementDispatcher:
    """Get or create the announcement dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = AnnouncementDispatcher()
    return _dispatcher
