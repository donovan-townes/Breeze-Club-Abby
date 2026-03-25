"""
Unified content delivery service for announcements, world updates, and social posts.

This module provides a single persistence and lifecycle model for all content
items that need generation and delivery. It replaces fragmented announcement
collections by standardizing on the following axes:

- content_type: system | world | event | social
- trigger_type: scheduled | event_start | manual | immediate
- lifecycle_state: draft -> generated -> queued -> delivered -> archived
- generation_status: pending | ready | error
- delivery_status: pending | partial | delivered | failed

For now we implement the minimal surface needed to support scheduled
announcements, with room to extend to other triggers and destinations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from bson import ObjectId

from abby_core.database.mongodb import get_database

try:
    from tdos_intelligence.observability import logging
    logger = logging.getLogger(__name__)
except Exception:  # pragma: no cover - logging optional
    logger = None

# Canonical enums (stringly typed for easy storage)
CONTENT_TYPES = {"system", "world", "event", "social"}
TRIGGER_TYPES = {"scheduled", "event_start", "manual", "immediate"}
LIFECYCLE_STATES = {"draft", "generated", "queued", "delivered", "archived"}
GENERATION_STATUSES = {"pending", "ready", "error"}
DELIVERY_STATUSES = {"pending", "partial", "delivered", "failed"}


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def get_content_delivery_collection():
    """Return the MongoDB collection for content delivery items."""
    db = get_database()
    collection = db["content_delivery_items"]

    # Indexes to support scheduled dispatch and guild scoping
    try:
        collection.create_index([("guild_id", 1), ("trigger_type", 1), ("scheduled_at", 1)])
        collection.create_index([("lifecycle_state", 1), ("generation_status", 1)])
    except Exception as exc:  # pragma: no cover - best-effort index creation
        if logger:
            logger.debug(f"[content_delivery] index creation skipped: {exc}")

    return collection


def _coerce_object_id(item_id: str) -> ObjectId:
    try:
        return ObjectId(item_id)
    except Exception as exc:
        raise ValueError(f"Invalid content_delivery item id: {item_id}") from exc


# ---------------------------------------------------------------------------
# Creation / Query
# ---------------------------------------------------------------------------

def _create_content_item(
    *,
    guild_id: int,
    content_type: str,
    trigger_type: str,
    title: str,
    description: str,
    scheduled_at: Optional[datetime] = None,
    delivery_channel_id: Optional[int] = None,
    delivery_roles: Optional[Sequence[int]] = None,
    priority: int = 0,
    payload: Optional[Dict[str, Any]] = None,
    context_refs: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> str:
    """Internal: Create a new content delivery item.
    
    **Do not call directly.** Use create_announcement_for_delivery()
    for operator audit trail and standard announcement creation, or _create_content_item() for system use.

    Defaults to draft lifecycle with pending generation.
    """
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {sorted(CONTENT_TYPES)}")
    if trigger_type not in TRIGGER_TYPES:
        raise ValueError(f"trigger_type must be one of {sorted(TRIGGER_TYPES)}")

    now = datetime.utcnow()
    doc = {
        "guild_id": int(guild_id),
        "content_type": content_type,
        "trigger_type": trigger_type,
        "title": title,
        "description": description,
        "payload": payload or {},
        "context_refs": context_refs or {},
        "idempotency_key": idempotency_key,
        "scheduled_at": scheduled_at,
        "priority": priority,
        "delivery_channel_id": delivery_channel_id,
        "delivery_roles": list(delivery_roles) if delivery_roles else [],
        "lifecycle_state": "draft",
        "generation_status": "pending",
        "delivery_status": "pending",
        "generated_message": None,
        "error_message": None,
        "delivery_result": None,
        "created_at": now,
        "updated_at": now,
    }

    collection = get_content_delivery_collection()
    result = collection.insert_one(doc)
    return str(result.inserted_id)


def list_scheduled_due_items(
    guild_id: int,
    *,
    scheduled_date: Optional[str] = None,
    scheduled_time: Optional[str] = None,
    lifecycle_states: Optional[Sequence[str]] = None,
    content_types: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Return scheduled items due for delivery for a guild.

    - Filters trigger_type="scheduled" and scheduled_at <= boundary
    - Boundary is derived from scheduled_date/time; if not provided, uses now
    - Lifecycle filter defaults to draft/generated/queued
    - Optional content_types filter
    """
    boundary: datetime
    now = datetime.utcnow()

    if scheduled_date:
        if scheduled_time:
            # Build YYYY-MM-DDTHH:MM boundary (naive UTC)
            boundary = datetime.fromisoformat(f"{scheduled_date}T{scheduled_time}")
        else:
            boundary = datetime.fromisoformat(f"{scheduled_date}T23:59:59")
    else:
        boundary = now

    states = list(lifecycle_states) if lifecycle_states else ["draft", "generated", "queued"]

    filter_doc: Dict[str, Any] = {
        "guild_id": int(guild_id),
        "trigger_type": "scheduled",
        "scheduled_at": {"$lte": boundary},
        "lifecycle_state": {"$in": states},
    }

    if content_types:
        filter_doc["content_type"] = {"$in": list(content_types)}

    collection = get_content_delivery_collection()
    cursor = collection.find(filter_doc).sort([("priority", -1), ("scheduled_at", 1)])

    return list(cursor)


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

def mark_generated(item_id: str, generated_message: str, operator_id: Optional[str] = None) -> bool:
    """Mark content item as generated (LLM message created).
    
    **State Validation (Phase 1):**
    Enforces valid transition: draft/pending → generated/ready
    Raises ValueError if current state is invalid for this transition.
    
    Args:
        item_id: Content item ID (ObjectId as string)
        generated_message: Generated LLM message content
        operator_id: User/system ID performing this operation (for audit trail)
    
    Returns:
        True if item was updated
    
    Raises:
        ValueError: If state transition is invalid
    """
    oid = _coerce_object_id(item_id)
    operator_id = operator_id or "system:llm"
    now = datetime.utcnow()
    collection = get_content_delivery_collection()
    
    # Fetch current state for validation
    item_before = collection.find_one({"_id": oid})
    
    if not item_before:
        raise ValueError(f"Content item not found: {item_id}")
    
    # State validation: Must be in draft state before generating
    current_lifecycle = item_before.get("lifecycle_state", "unknown")
    current_generation = item_before.get("generation_status", "unknown")
    
    if current_lifecycle != "draft" or current_generation != "pending":
        raise ValueError(
            f"Invalid state transition for mark_generated: "
            f"current={current_lifecycle}/{current_generation}, "
            f"valid=draft/pending. "
            f"Item {item_id} cannot be marked as generated in its current state."
        )
    
    result = collection.update_one(
        {"_id": oid},
        {"$set": {
            "generated_message": generated_message,
            "generation_status": "ready",
            "lifecycle_state": "generated",
            "updated_at": now,
            "error_message": None,
        }}
    )
    
    if result.modified_count > 0 and logger:
        guild_id = item_before.get("guild_id")
        content_type = item_before.get("content_type", "unknown")
        trigger_type = item_before.get("trigger_type", "unknown")
        title = item_before.get("title", "")[:50]
        logger.info(
            f"[✅ content_generated] {item_id[:8]}... "
            f"guild={guild_id} type={content_type}/{trigger_type} "
            f"title='{title}...' "
            f"operator={operator_id} "
            f"msg_len={len(generated_message)}"
        )
    
    return result.modified_count > 0


def mark_generation_failed(item_id: str, error_message: str) -> bool:
    """Mark content item as generation failed (LLM error or timeout).
    
    Transition: draft/pending → draft/error
    Item remains in draft for potential retry.
    
    Args:
        item_id: Content item ID (ObjectId as string)
        error_message: Reason for generation failure
    
    Returns:
        True if item was updated
    """
    oid = _coerce_object_id(item_id)
    now = datetime.utcnow()
    collection = get_content_delivery_collection()
    
    # Fetch current state for logging
    item_before = collection.find_one({"_id": oid})
    
    result = collection.update_one(
        {"_id": oid},
        {"$set": {
            "generation_status": "error",
            "lifecycle_state": "draft",
            "error_message": error_message,
            "updated_at": now,
        }}
    )
    
    if result.modified_count > 0 and logger and item_before:
        guild_id = item_before.get("guild_id")
        content_type = item_before.get("content_type", "unknown")
        logger.warning(
            f"[📝 Lifecycle] {item_id[:8]}... GENERATION_FAILED "
            f"guild={guild_id} type={content_type} "
            f"error='{error_message[:60]}...'"
        )
    
    return result.modified_count > 0


def mark_delivered(item_id: str, delivered_at: Optional[datetime] = None, delivery_result: Optional[Dict[str, Any]] = None, operator_id: Optional[str] = None) -> bool:
    """Mark content item as delivered (sent to Discord).
    
    **State Validation (Phase 1):**
    Enforces valid transition: queued → delivered
    Raises ValueError if current state is invalid for this transition.
    
    Args:
        item_id: Content item ID (ObjectId as string)
        delivered_at: Timestamp of delivery (defaults to now)
        delivery_result: Dict with delivery metadata (guild_id, channel_id, message_id)
        operator_id: User/system ID performing this operation (for audit trail)
    
    Returns:
        True if item was updated
    
    Raises:
        ValueError: If state transition is invalid
    """
    oid = _coerce_object_id(item_id)
    operator_id = operator_id or "system:discord"
    ts = delivered_at or datetime.utcnow()
    collection = get_content_delivery_collection()
    
    # Fetch current state for validation
    item_before = collection.find_one({"_id": oid})
    
    if not item_before:
        raise ValueError(f"Content item not found: {item_id}")
    
    # State validation: Must be in queued state before delivering
    current_lifecycle = item_before.get("lifecycle_state", "unknown")
    
    if current_lifecycle != "queued":
        raise ValueError(
            f"Invalid state transition for mark_delivered: "
            f"current={current_lifecycle}, "
            f"valid=queued. "
            f"Item {item_id} cannot be marked as delivered in its current state."
        )
    
    result = collection.update_one(
        {"_id": oid},
        {"$set": {
            "lifecycle_state": "delivered",
            "delivery_status": "delivered",
            "delivered_at": ts,
            "delivery_result": delivery_result,
            "updated_at": ts,
        }}
    )
    
    if result.modified_count > 0 and logger and item_before:
        guild_id = item_before.get("guild_id")
        channel_id = delivery_result.get("channel_id") if delivery_result else None
        message_id = delivery_result.get("message_id") if delivery_result else None
        logger.info(
            f"[✅ content_delivered] {item_id[:8]}... "
            f"guild={guild_id} channel={channel_id} msg={message_id} "
            f"operator={operator_id}"
        )
    
    return result.modified_count > 0


def mark_delivery_failed(item_id: str, error_message: str) -> bool:
    """Mark content item as delivery failed (Discord error, channel not found, etc).
    
    Transition: queued → queued (stays queued for retry)
    Sets delivery_status=failed for monitoring/alerting.
    
    Args:
        item_id: Content item ID (ObjectId as string)
        error_message: Reason for delivery failure
    
    Returns:
        True if item was updated
    """
    oid = _coerce_object_id(item_id)
    now = datetime.utcnow()
    collection = get_content_delivery_collection()
    
    # Fetch current state for logging
    item_before = collection.find_one({"_id": oid})
    
    result = collection.update_one(
        {"_id": oid},
        {"$set": {
            "delivery_status": "failed",
            "lifecycle_state": "queued",
            "error_message": error_message,
            "updated_at": now,
        }}
    )
    
    if result.modified_count > 0 and logger and item_before:
        guild_id = item_before.get("guild_id")
        logger.warning(
            f"[📝 Lifecycle] {item_id[:8]}... DELIVERY_FAILED "
            f"guild={guild_id} "
            f"error='{error_message[:60]}...'"
        )
    
    return result.modified_count > 0


def bulk_update_lifecycle(
    item_ids: Sequence[str],
    *,
    lifecycle_state: Optional[str] = None,
    generation_status: Optional[str] = None,
    delivery_status: Optional[str] = None,
) -> int:
    """Bulk update lifecycle/generation/delivery fields for items."""
    if lifecycle_state and lifecycle_state not in LIFECYCLE_STATES:
        raise ValueError(f"lifecycle_state must be one of {sorted(LIFECYCLE_STATES)}")
    if generation_status and generation_status not in GENERATION_STATUSES:
        raise ValueError(f"generation_status must be one of {sorted(GENERATION_STATUSES)}")
    if delivery_status and delivery_status not in DELIVERY_STATUSES:
        raise ValueError(f"delivery_status must be one of {sorted(DELIVERY_STATUSES)}")

    oids = [_coerce_object_id(i) for i in item_ids]
    updates: Dict[str, Any] = {"updated_at": datetime.utcnow()}
    if lifecycle_state:
        updates["lifecycle_state"] = lifecycle_state
    if generation_status:
        updates["generation_status"] = generation_status
    if delivery_status:
        updates["delivery_status"] = delivery_status

    collection = get_content_delivery_collection()
    result = collection.update_many({"_id": {"$in": oids}}, {"$set": updates})
    return result.modified_count


# ---------------------------------------------------------------------------
# Global queries (system/daily delivery)
# ---------------------------------------------------------------------------

def list_due_items_for_delivery_global(
    *,
    before: Optional[datetime] = None,
    content_types: Optional[Sequence[str]] = None,
    trigger_types: Optional[Sequence[str]] = None,
    lifecycle_states: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Return all items due for delivery across guilds.

    Args:
        before: Cutoff datetime (defaults to now)
        content_types: Optional filter of content types
        trigger_types: Optional filter of trigger types (defaults scheduled + immediate)
        lifecycle_states: Optional filter (defaults draft/generated/queued)
    """
    cutoff = before or datetime.utcnow()
    filter_doc: Dict[str, Any] = {
        "scheduled_at": {"$lte": cutoff},
    }

    if content_types:
        filter_doc["content_type"] = {"$in": list(content_types)}
    if trigger_types:
        filter_doc["trigger_type"] = {"$in": list(trigger_types)}
    else:
        filter_doc["trigger_type"] = {"$in": ["scheduled", "immediate"]}

    states = list(lifecycle_states) if lifecycle_states else ["draft", "generated", "queued"]
    filter_doc["lifecycle_state"] = {"$in": states}

    collection = get_content_delivery_collection()
    cursor = collection.find(filter_doc).sort([("priority", -1), ("scheduled_at", 1)])
    return list(cursor)


# ---------------------------------------------------------------------------
# Generation queue helpers
# ---------------------------------------------------------------------------

def list_pending_generation_items(
    *,
    max_items: int = 10,
    content_types: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Return items awaiting generation.

    Orders by priority desc, created_at asc to mirror announcement behavior.
    """
    filter_doc: Dict[str, Any] = {"generation_status": "pending"}
    if content_types:
        filter_doc["content_type"] = {"$in": list(content_types)}

    collection = get_content_delivery_collection()
    cursor = collection.find(filter_doc).sort([("priority", -1), ("created_at", 1)])
    return list(cursor.limit(max_items))


def get_pending_generation_events(max_events: int = 5) -> List[Dict[str, Any]]:
    """Return system events awaiting generation.
    
    Used by background generation job to find events that need LLM generation.
    
    Args:
        max_events: Maximum number of events to return
    
    Returns:
        List of events pending generation, ordered by priority then creation time
    """
    return list_pending_generation_items(
        max_items=max_events,
        content_types=["system", "world"]
    )


def set_priority(item_id: str, *, priority: int = 0) -> bool:
    """Update priority for a content item."""
    oid = _coerce_object_id(item_id)
    collection = get_content_delivery_collection()
    result = collection.update_one({"_id": oid}, {"$set": {"priority": priority}})
    return result.modified_count > 0


def mark_item_failed(item_id: str, *, reason: str = "Unknown error") -> bool:
    """Mark a content item as failed (for rollback scenarios).
    
    Sets lifecycle_state=failed, generation_status=error, delivery_status=failed.
    Used when atomic operations fail and need to rollback created items.
    
    Args:
        item_id: Content item ID
        reason: Failure reason for audit trail
        
    Returns:
        True if item was marked as failed
    """
    oid = _coerce_object_id(item_id)
    collection = get_content_delivery_collection()
    result = collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "lifecycle_state": "failed",
                "generation_status": "error",
                "delivery_status": "failed",
                "error_message": reason,
                "failed_at": datetime.utcnow(),
            }
        }
    )
    return result.modified_count > 0


# ---------------------------------------------------------------------------
# Compatibility aliases
# ---------------------------------------------------------------------------

def mark_generated_as_content_item(item_id: str, message: str) -> bool:
    """Alias: mark_generated. For compatibility with events_lifecycle."""
    return mark_generated(item_id, message)


def mark_generation_complete(item_id: str, message: str) -> bool:
    """Alias: mark_generated."""
    return mark_generated(item_id, message)


def create_content_item(
    *,
    guild_id: int,
    content_type: str,
    trigger_type: str,
    title: str,
    description: str,
    scheduled_at: Optional[datetime] = None,
    delivery_channel_id: Optional[int] = None,
    delivery_roles: Optional[Sequence[int]] = None,
    priority: int = 0,
    payload: Optional[Dict[str, Any]] = None,
    context_refs: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> str:
    """Create a content item without operator audit trail.
    
    Use create_announcement_for_delivery() for operator-initiated announcements
    to maintain audit compliance and operator tracking.
    """
    return _create_content_item(
        guild_id=guild_id,
        content_type=content_type,
        trigger_type=trigger_type,
        title=title,
        description=description,
        scheduled_at=scheduled_at,
        delivery_channel_id=delivery_channel_id,
        delivery_roles=delivery_roles,
        priority=priority,
        payload=payload,
        context_refs=context_refs,
        idempotency_key=idempotency_key,
    )


# ============================================================================
# PUBLIC CANONICAL ENTRY POINT FOR ANNOUNCEMENTS
# ============================================================================

def create_announcement_for_delivery(
    *,
    guild_id: int,
    title: str,
    description: str,
    content_type: str = "world",
    trigger_type: str = "manual",
    delivery_channel_id: Optional[int] = None,
    delivery_roles: Optional[Sequence[int]] = None,
    scheduled_at: Optional[datetime] = None,
    priority: int = 0,
    operator_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    context_refs: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> str:
    """PUBLIC: Create an announcement for delivery (canonical entry point).
    
    **RECOMMENDED:** Use this function to create all announcements in Abby.
    This replaces AnnouncementDispatcher.create_announcement() with a simpler,
    more direct API that flows through the unified content delivery pipeline.
    
    The unified pipeline handles:
    1. Creation (this function)
    2. Generation (LLM generation for system events)
    3. Delivery (unified_content_dispatcher job)
    4. Archive (cleanup after retention period)
    
    Args:
        guild_id: Discord guild ID
        title: Announcement title
        description: Announcement description/body
        content_type: 'system' (LLM-generated), 'world' (operator-provided), etc.
        trigger_type: 'manual' (user command), 'scheduled', 'event_start', etc.
        delivery_channel_id: Discord channel to send to (optional for broadcast)
        delivery_roles: List of role IDs to mention (optional)
        scheduled_at: When to deliver (if None, ASAP)
        priority: Priority level (higher = earlier)
        operator_id: User/system ID creating this (for audit trail)
        context: Additional context dict
        payload: Additional payload dict
        context_refs: Context references for downstream handlers
        idempotency_key: Prevent duplicates (optional)
    
    Returns:
        Announcement/content item ID (ObjectId as string)
    
    Example:
        item_id = create_announcement_for_delivery(
            guild_id=123456789,
            title="Server Announcement",
            description="This is the announcement content",
            delivery_channel_id=987654321,
            operator_id="user:alice",
        )
    """
    item_id = _create_content_item(
        guild_id=guild_id,
        content_type=content_type,
        trigger_type=trigger_type,
        title=title,
        description=description,
        scheduled_at=scheduled_at,
        delivery_channel_id=delivery_channel_id,
        delivery_roles=delivery_roles,
        priority=priority,
        payload=payload or {},
        context_refs=context_refs or {},
        idempotency_key=idempotency_key,
    )
    
    # Log announcement creation with operator info
    if logger:
        operator = operator_id or "system:auto"
        logger.info(
            f"[📝 announcement] CREATED {item_id[:8]}... "
            f"guild={guild_id} type={content_type}/{trigger_type} "
            f"title='{title[:50]}...' "
            f"operator={operator} "
            f"channel={delivery_channel_id or 'broadcast'}"
        )
    
    return item_id

# ==================== LIFECYCLE MANAGEMENT (Public API) ====================
# These are the canonical lifecycle functions for all announcements.
# Use these instead of dispatcher methods.

def mark_announcement_generated(
    item_id: str,
    generated_message: str,
    operator_id: Optional[str] = None,
) -> bool:
    """PUBLIC: Mark announcement as generated (LLM content created).
    
    Routes through AnnouncementDispatcher for state validation and audit trail.
    
    Args:
        item_id: Announcement ID
        generated_message: LLM-generated message content
        operator_id: Who performed generation (default: "system:llm")
    
    Returns:
        True if state transition successful
    
    Raises:
        AnnouncementStateError: If state transition is invalid
    """
    from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
    dispatcher = get_announcement_dispatcher()
    return dispatcher.generate_content(
        item_id=item_id,
        generated_message=generated_message,
        operator_id=operator_id or "system:llm"
    )


def mark_announcement_generation_failed(
    item_id: str,
    error_message: str,
    operator_id: Optional[str] = None,
) -> bool:
    """PUBLIC: Mark announcement generation as failed.
    
    Routes through AnnouncementDispatcher for state validation and DLQ routing.
    
    Args:
        item_id: Announcement ID
        error_message: Reason for failure
        operator_id: Who handled the failure (default: "system:llm")
    
    Returns:
        True if marked as failed
    """
    from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
    dispatcher = get_announcement_dispatcher()
    return dispatcher.generation_failed(
        item_id=item_id,
        error_message=error_message,
        operator_id=operator_id or "system:llm"
    )


def queue_announcement_for_delivery(
    item_id: str,
    operator_id: Optional[str] = None,
) -> bool:
    """PUBLIC: Queue announcement for Discord delivery.
    
    Validates preconditions (message exists, channel set, etc.) and transitions
    from "generated" to "queued" state.
    
    Args:
        item_id: Announcement ID
        operator_id: Who queued it (default: "system:scheduler")
    
    Returns:
        True if successfully queued
    
    Raises:
        AnnouncementStateError: If not in "generated" state
        AnnouncementValidationError: If preconditions fail
    """
    from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
    dispatcher = get_announcement_dispatcher()
    return dispatcher.queue_for_delivery(
        item_id=item_id,
        operator_id=operator_id or "system:scheduler"
    )


def deliver_announcement_to_discord(
    item_id: str,
    message_id: int,
    channel_id: int,
    operator_id: Optional[str] = None,
) -> bool:
    """PUBLIC: Mark announcement as delivered to Discord.
    
    Validates Discord IDs and transitions from "queued" to "delivered" state.
    
    Args:
        item_id: Announcement ID
        message_id: Discord message ID (from message.id)
        channel_id: Discord channel ID (from channel.id)
        operator_id: Who delivered (default: "system:discord")
    
    Returns:
        True if successfully marked as delivered
    
    Raises:
        AnnouncementStateError: If not in "queued" state
        AnnouncementValidationError: If IDs invalid or preconditions fail
    """
    from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
    dispatcher = get_announcement_dispatcher()
    return dispatcher.deliver(
        item_id=item_id,
        message_id=message_id,
        channel_id=channel_id,
        operator_id=operator_id or "system:discord"
    )