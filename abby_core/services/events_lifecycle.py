"""
Announcement lifecycle orchestration on top of the unified content_delivery_items
collection.

Legacy system_events persistence has been removed. All creation, generation, and
delivery tracking now happens through the content_delivery service. This module
keeps the previous API surface (record_season_transition_event, register_delivery,
etc.) but routes storage to content_delivery.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple

from abby_core.observability.logging import logging
from abby_core.services.content_delivery import (
    list_pending_generation_items,
    mark_generated as cd_mark_generated,
    mark_generation_failed as cd_mark_generation_failed,
    mark_delivered as cd_mark_delivered,
    mark_delivery_failed as cd_mark_delivery_failed,
    set_priority as cd_set_priority,
    get_content_delivery_collection,
)

logger = logging.getLogger(__name__)


def _iter_guild_ids() -> List[int]:
    """Return all known guild IDs for fan-out of system/world announcements."""
    try:
        from abby_core.database.collections.guild_configuration import get_all_guild_configs

        guild_configs = get_all_guild_configs()
        guild_ids: List[int] = []
        for cfg in guild_configs:
            guild_id = cfg.get("guild_id")
            if guild_id is None:
                continue
            try:
                guild_ids.append(int(guild_id))
            except Exception:
                continue
        return guild_ids
    except Exception as exc:
        logger.warning(f"[🌍] Failed to load guild ids for announcements: {exc}")
        return []


def _get_daily_world_schedule() -> Tuple[bool, str, str]:
    """Return (enabled, time_str, timezone) for daily world announcements."""
    try:
        from abby_core.database.collections.system_configuration import get_system_config

        system_config = get_system_config()
        system_jobs = system_config.get("system_jobs", {})
        announcements = system_jobs.get("announcements", {})
        daily_job = announcements.get("daily_world_announcements", {})
        schedule = daily_job.get("schedule", {})

        enabled = bool(daily_job.get("enabled", True))
        time_str = schedule.get("time", "08:00")
        timezone = system_config.get("timezone", "UTC")
        return enabled, time_str, timezone
    except Exception as exc:
        logger.warning(f"[🌍] Failed to load daily world schedule: {exc}")
        return True, "08:00", "UTC"


def _next_daily_world_dt(time_str: str, timezone: str) -> datetime:
    """Compute the next scheduled datetime (UTC naive) for the given time/timezone."""
    try:
        import pytz

        try:
            tz = pytz.timezone(timezone)
        except Exception:
            tz = pytz.UTC

        now_local = datetime.now(tz)
        hour, minute = map(int, time_str.split(":")) if ":" in time_str else (8, 0)
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate = candidate + timedelta(days=1)
        return candidate.astimezone(pytz.UTC).replace(tzinfo=None)
    except Exception:
        now = datetime.utcnow()
        return now + timedelta(hours=1)


def _create_content_items_for_all_guilds(
    *,
    content_type: str,
    trigger_type: str,
    title: str,
    description: str,
    priority: int,
    payload: Optional[Dict[str, Any]] = None,
    context_refs: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> List[str]:
    """Create one announcement per guild (fan-out) via unified content delivery pipeline.
    
    Routes all creation through create_announcement_for_delivery to maintain operator
    audit trail and consistent lifecycle management.
    
    ISSUE-006: No longer creates spurious guild_id=0 content when no guilds exist.
    """
    from abby_core.services.content_delivery import create_announcement_for_delivery
    
    guild_ids = _iter_guild_ids()
    # ISSUE-006: If no real guilds exist, return early rather than creating guild_id=0 content
    if not guild_ids:
        logger.debug("[🌍] No guilds configured; skipping content creation (previously created guild_id=0)")
        return []

    enabled, time_str, timezone = _get_daily_world_schedule()
    scheduled_at: Optional[datetime] = None
    if trigger_type == "scheduled":
        if not enabled:
            logger.info("[🌍] Daily world announcements disabled; skipping content creation")
            return []
        scheduled_at = _next_daily_world_dt(time_str, timezone)

    ids: List[str] = []
    for gid in guild_ids:
        try:
            item_id = create_announcement_for_delivery(
                guild_id=gid,
                content_type=content_type,
                trigger_type=trigger_type,
                title=title,
                description=description,
                delivery_channel_id=None,  # Determined at dispatch time
                delivery_roles=None,
                scheduled_at=scheduled_at,
                priority=priority,
                operator_id="system:events_lifecycle",
                context={
                    "content_type": content_type,
                    "trigger_type": trigger_type,
                    "payload": payload,
                    "context_refs": context_refs,
                    "idempotency_key": idempotency_key,
                }
            )
            ids.append(item_id)
        except Exception as exc:
            logger.error(f"[🌍] Failed to create announcement for guild {gid}: {exc}", exc_info=True)

    return ids


# ==================== EVENT RECORDING ====================

def record_season_transition_event(
    old_season_id: str,
    new_season_id: str,
    trigger: str = "automatic",
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Optional[str]:
    """Record a season transition event for later announcement.
    
    Args:
        old_season_id: Previous season (e.g., "winter-2026")
        new_season_id: New season (e.g., "spring-2026")
        trigger: How transition occurred ("automatic", "operator", "recovery")
        operator_id: Discord user ID of operator who triggered this (if manual)
        reason: Reason provided by operator (if manual)
        idempotency_key: Unique key for idempotency (prevents duplicates)
    
    Returns:
        str: Event ID, or None if recording failed
    """
    if not idempotency_key:
        idempotency_key = f"season_transition:{old_season_id}:{new_season_id}:{int(datetime.utcnow().timestamp())}"

    payload = {
        "old_season_id": old_season_id,
        "new_season_id": new_season_id,
        "trigger": trigger,
    }

    context_refs = {
        "operator_id": operator_id,
        "reason": reason,
        "event_type": "season_transition",
    }

    enabled, _time_str, _timezone = _get_daily_world_schedule()
    if not enabled:
        logger.info("[🌍] Season transition recorded but daily announcements are disabled")
        return None

    ids = _create_content_items_for_all_guilds(
        content_type="system",
        trigger_type="scheduled",
        title=f"Season Transition: {old_season_id} → {new_season_id}",
        description="",  # Will be generated by background job
        payload=payload,
        context_refs=context_refs,
        priority=1 if trigger == "operator" else 0,
        idempotency_key=idempotency_key,
    )

    if ids:
        logger.info(f"[🌍] Recorded season transition content for {len(ids)} guild(s)")
        return ids[0]

    logger.error("[🌍] Failed to record season transition event")
    return None


def record_world_announcement_event(
    announcement_content: str,
    operator_id: int,
    immediate: bool = False,
    reason: Optional[str] = None
) -> Optional[str]:
    """Record a world announcement event for distribution.
    
    Args:
        announcement_content: The announcement message content
        operator_id: Discord ID of operator who created it
        immediate: If True, send immediately; else queue for next job
        reason: Optional operator-provided reason/context
    
    Returns:
        str: Event ID, or None if recording failed
    """
    payload = {"trigger": "operator"}
    context_refs = {
        "operator_id": operator_id,
        "reason": reason,
        "event_type": "world_announcement",
    }

    ids = _create_content_items_for_all_guilds(
        content_type="world",
        trigger_type="immediate",
        title="World Announcement",
        description=announcement_content,
        payload=payload,
        context_refs=context_refs,
        priority=1 if immediate else 0,
    )

    for item_id in ids:
        cd_mark_generated(item_id, announcement_content)

    if ids:
        logger.info(f"[📢] Recorded world announcement for {len(ids)} guild(s)")
        return ids[0]

    logger.error("[📢] Failed to record world announcement")
    return None


def record_event_start(
    event_id: str,
    trigger: str = "automatic",
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Optional[str]:
    """Record an event start for later announcement.
    
    Args:
        event_id: Event state ID (e.g., "valentines-2026")
        trigger: How event started ("automatic", "operator")
        operator_id: Discord user ID of operator who triggered this (if manual)
        reason: Reason provided by operator (if manual)
    
    Returns:
        str: Content item ID, or None if recording failed
    """
    enabled, _time_str, _timezone = _get_daily_world_schedule()
    if not enabled:
        logger.info(f"[📅] Event start recorded for {event_id} but daily announcements are disabled")
        return None

    payload = {
        "event_id": event_id,
        "trigger": trigger,
        "event_action": "start",
    }

    context_refs = {
        "operator_id": operator_id,
        "reason": reason,
        "event_type": "event_start",
        "event_id": event_id,
    }

    ids = _create_content_items_for_all_guilds(
        content_type="event",
        trigger_type="scheduled",
        title=f"Event Start: {event_id}",
        description="",  # Will be generated by background job
        payload=payload,
        context_refs=context_refs,
        priority=1 if trigger == "operator" else 0,
        idempotency_key=f"event_start:{event_id}:{int(datetime.utcnow().timestamp())}",
    )

    if ids:
        logger.info(f"[📅] Recorded event start content for {len(ids)} guild(s)")
        return ids[0]

    logger.error(f"[📅] Failed to record event start for {event_id}")
    return None


def record_event_end(
    event_id: str,
    trigger: str = "automatic",
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Optional[str]:
    """Record an event end for later announcement.
    
    Args:
        event_id: Event state ID (e.g., "valentines-2026")
        trigger: How event ended ("automatic", "operator")
        operator_id: Discord user ID of operator who triggered this (if manual)
        reason: Reason provided by operator (if manual)
    
    Returns:
        str: Content item ID, or None if recording failed
    """
    enabled, _time_str, _timezone = _get_daily_world_schedule()
    if not enabled:
        logger.info(f"[📅] Event end recorded for {event_id} but daily announcements are disabled")
        return None

    payload = {
        "event_id": event_id,
        "trigger": trigger,
        "event_action": "end",
    }

    context_refs = {
        "operator_id": operator_id,
        "reason": reason,
        "event_type": "event_end",
        "event_id": event_id,
    }

    ids = _create_content_items_for_all_guilds(
        content_type="event",
        trigger_type="scheduled",
        title=f"Event End: {event_id}",
        description="",  # Will be generated by background job
        payload=payload,
        context_refs=context_refs,
        priority=1 if trigger == "operator" else 0,
        idempotency_key=f"event_end:{event_id}:{int(datetime.utcnow().timestamp())}",
    )

    if ids:
        logger.info(f"[📅] Recorded event end content for {len(ids)} guild(s)")
        return ids[0]

    logger.error(f"[📅] Failed to record event end for {event_id}")
    return None


def get_pending_announcements(event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all events that haven't been announced yet.
    
    Called by daily world announcement job to find things to announce.
    
    Args:
        event_type: Filter to specific type (e.g., "season_transition")
    
    Returns:
        list: Pending event documents
    """
    filter_doc: Dict[str, Any] = {"lifecycle_state": {"$in": ["generated", "queued", "draft"]}}
    if event_type:
        filter_doc["context_refs.event_type"] = event_type

    from abby_core.services.content_delivery import get_content_delivery_collection

    collection = get_content_delivery_collection()
    return list(collection.find(filter_doc).sort("created_at", 1))


def mark_event_announced(
    event_id: str,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
    error: Optional[str] = None
) -> bool:
    """Mark an event as announced (or track delivery failure).
    
    For system-wide events (scope="system"), tracks delivery to each guild
    in the deliveries array. Event is marked announced=True when ALL target
    guilds have been delivered to (or at least attempted).
    
    For guild-specific events (scope="guild"), marks as announced immediately.
    
    Args:
        event_id: Event document ID (string)
        guild_id: Guild where announcement was sent (required for tracking)
        channel_id: Channel ID where sent (None if failed)
        message_id: Discord message ID (None if failed)
        error: Error message if delivery failed
    
    Returns:
        bool: Success
    """
    delivered_at = datetime.utcnow()
    try:
        if error:
            return cd_mark_delivery_failed(event_id, error)

        return cd_mark_delivered(
            event_id,
            delivered_at=delivered_at,
            delivery_result={
                "guild_id": guild_id,
                "channel_id": channel_id,
                "message_id": message_id,
            },
        )
    except Exception as exc:
        logger.error(f"[🌍] Failed to mark announcement delivered: {exc}", exc_info=True)
        return False


# ==================== MESSAGE GENERATION (Background Job) ====================

def get_pending_generation_events(max_events: int = 5) -> List[Dict[str, Any]]:
    """Get events that need message generation (background job).
    
    Priority order: operator-immediate (priority=True) first, then regular pending.
    
    Args:
        max_events: Max events to return per run (rate limiting)
    
    Returns:
        List of event dicts with generation_status == "pending", priority first
    """
    return list_pending_generation_items(max_items=max_events, content_types=["system", "world"])


def mark_generation_complete(
    event_id: str,
    generated_message: str
) -> bool:
    """Mark an event as having its message generated.
    
    Args:
        event_id: Event document ID (string)
        generated_message: The generated announcement message
    
    Returns:
        bool: Success
    """
    try:
        return cd_mark_generated(event_id, generated_message)
    except Exception as exc:
        logger.error(f"[🌍] Failed to mark generation complete: {exc}", exc_info=True)
        return False


def mark_generation_failed(
    event_id: str,
    error: str
) -> bool:
    """Mark an event as having failed message generation.
    
    Args:
        event_id: Event document ID (string)
        error: Description of generation failure
    
    Returns:
        bool: Success
    """
    try:
        return cd_mark_generation_failed(event_id, error)
    except Exception as exc:
        logger.error(f"[🌍] Failed to mark generation failed: {exc}")
        return False


def set_event_priority(event_id: str, priority: bool = True) -> bool:
    """Set an event's priority flag (for operator-immediate announcements).
    
    Priority events are processed by background generation job first.
    
    Args:
        event_id: Event document ID (string)
        priority: Whether this is a priority event
    
    Returns:
        bool: Success
    """
    try:
        return cd_set_priority(event_id, priority=1 if priority else 0)
    except Exception as exc:
        logger.error(f"[🌍] Failed to set event priority: {exc}", exc_info=True)
        return False


# ==================== ANNOUNCEMENT PREPARATION ====================

def prepare_season_transition_announcement(
    event: Dict[str, Any]
) -> Dict[str, str]:
    """Prepare data for LLM to generate a season transition announcement.
    
    Returns a dict with all context needed for the prompt.
    
    Args:
        event: Event document from system_events
    
    Returns:
        dict: Context dict with keys:
            - old_season_name
            - new_season_name
            - old_season_canon_ref
            - new_season_canon_ref
            - trigger_type
            - timestamp
    """
    from abby_core.system.system_state import get_state_by_id
    
    payload = event.get("payload", {})
    old_id = event.get("old_season_id") or payload.get("old_season_id")
    new_id = event.get("new_season_id") or payload.get("new_season_id")
    
    old_season = get_state_by_id(old_id) if old_id else None
    new_season = get_state_by_id(new_id) if new_id else None
    
    return {
        "old_season_name": old_season.get("label", "Unknown") if old_season else "Unknown",
        "new_season_name": new_season.get("label", "Unknown") if new_season else "Unknown",
        "old_season_canon_ref": old_season.get("canon_ref", "") if old_season else "",
        "new_season_canon_ref": new_season.get("canon_ref", "") if new_season else "",
        "trigger_type": payload.get("trigger", event.get("trigger", "unknown")),
        "timestamp": event.get("created_at", datetime.utcnow()).isoformat()
    }


# ==================== ANNOUNCEMENT GENERATION ====================

async def generate_season_announcement(
    persona_data: Dict[str, Any],
    transition_context: Dict[str, str]
) -> str:
    """Generate a season transition announcement using LLM + persona.
    
    Makes a SINGLE LLM call per job execution, NOT per guild.
    This message is then prepended with guild-specific greetings.
    
    Args:
        persona_data: Current persona (e.g., from personas/bunny.json)
        transition_context: Result of prepare_season_transition_announcement()
    
    Returns:
        str: Core announcement message (LLM-generated)
    
    Cost Model:
    - 1 LLM call per daily announcement job run
    - Message reused for ALL guilds (e.g., 100 guilds = 1 LLM call)
    - Guild greetings are deterministic (no LLM needed)
    
    Example output:
        "The frost has melted and new growth emerges. XP resets to 0 (fresh 
        starts!), but your levels are permanent. Let's bloom together! 🌸"
    
    Usage:
        core_message = await generate_season_announcement(persona_data, context)
        
        # Then for each guild, prepend:
        full_message = f"Hello {guild_name}!\n\n{core_message}\n\n— {persona_name}"
    """
    try:
        from abby_core.services.conversation_service import get_conversation_service
        from abby_core.llm.context_factory import build_conversation_context
        
        # Extract transition details for prompt
        old_season_name = transition_context.get("old_season_name", "the previous season")
        new_season_name = transition_context.get("new_season_name", "the new season")
        
        # Build the prompt for LLM
        user_prompt = (
            f"Write a brief, enthusiastic announcement about the seasonal transition "
            f"from {old_season_name} to {new_season_name}. "
            f"Mention that XP resets to 0 (fresh starts!) but levels are permanent. "
            f"Keep it under 150 words and maintain an encouraging, playful tone."
        )
        
        # Build conversation context using factory
        # This automatically loads current persona and injects system prompt
        context = build_conversation_context(
            user_id="system:announcer",
            guild_name="platform",
            user_name="System",
            is_final_turn=False,
            turn_number=1,
        )
        
        # Make ONE LLM call
        conversation_service = get_conversation_service()
        announcement, error = await conversation_service.generate_response(user_prompt, context, max_retries=2, max_tokens=300)
        if error or announcement is None:
            logger.error(f"[🌍 Announcements] Generation failed: {error or 'no response'}")
            return f"Season transition: {old_season_name} → {new_season_name}. XP resets, levels stay!"  # Fallback
        
        logger.info(f"[🌍 Announcements] Generated announcement: {announcement[:100]}...")
        return announcement
        return announcement
    
    except Exception as e:
        logger.error(f"[🌍 Announcements] LLM call failed: {e}", exc_info=True)
        # Fallback to template if LLM fails
        old_season = transition_context.get("old_season_name", "the old season")
        new_season = transition_context.get("new_season_name", "the new season")
        return (
            f"The transition from {old_season} to {new_season} is complete!\n"
            f"XP resets to 0 (fresh starts!), but your levels are permanent."
        )


# ==================== ANNOUNCEMENT DELIVERY CALLBACK ====================

_announcement_delivery_callback: Optional[Callable] = None


def register_announcement_delivery(callback: Callable) -> None:
    """Register announcement delivery callback.
    
    This is called by the Discord adapter at startup to inject platform-specific delivery.
    Enables core to remain platform-agnostic while delegating to adapters.
    
    Callback signature:
        async def deliver(bot, guild_id: int, message: str) -> tuple[bool, Optional[int], Optional[int], Optional[str]]
    
    Args:
        callback: Async function that delivers announcements
    """
    global _announcement_delivery_callback
    _announcement_delivery_callback = callback
    logger.debug("[🌍] Announcement delivery callback registered")


async def send_season_announcement_to_guild(
    bot,
    guild_id: int,
    announcement_message: str
) -> tuple[bool, Optional[int], Optional[int], Optional[str]]:
    """Send announcement to guild's announcement channel.
    
    This remains platform-agnostic by delegating to a registered adapter handler.
    The Discord adapter registers its delivery handler at startup.
    
    Args:
        bot: Bot instance (passed through to callback)
        guild_id: Target guild
        announcement_message: Message to send (plain text or LLM-generated)
    
    Returns:
        tuple: (success, channel_id, message_id, error_msg)
    """
    if _announcement_delivery_callback is None:
        logger.error(f"[🌍] No announcement delivery callback registered for guild {guild_id}")
        return False, None, None, "No delivery callback registered. Is Discord adapter initialized?"
    
    try:
        success, channel_id, message_id, error = await _announcement_delivery_callback(
            bot, guild_id, announcement_message
        )
        
        if success:
            logger.info(f"[🌍] Sent announcement to guild {guild_id}, channel {channel_id}")
            return True, channel_id, message_id, None
        else:
            return False, channel_id, message_id, error
    
    except Exception as e:
        logger.error(f"[🌍] Announcement delivery failed for guild {guild_id}: {e}", exc_info=True)
        return False, None, None, str(e)


# ==================== FAILURE HANDLING ====================

async def send_mod_channel_warning(
    bot,
    guild_id: int,
    error_description: str
) -> bool:
    """Send warning to mod channel when announcement fails.
    
    Alerts mods that a season transition occurred but wasn't announced.
    """
    from abby_core.database.collections.guild_configuration import get_guild_config
    
    try:
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            logger.warning(f"[🌍] No guild config found for {guild_id}")
            return False
        channels = guild_config.get("channels", {})
        mod_channel_id = channels.get("mod", {}).get("id") if channels else None
        
        if not mod_channel_id:
            logger.warning(f"[🌍] No mod channel to send warning for guild {guild_id}")
            return False
        
        channel = bot.get_channel(mod_channel_id)
        if not channel:
            try:
                channel = await bot.fetch_channel(mod_channel_id)
            except Exception as e:
                logger.error(f"[🌍] Failed to fetch mod channel: {e}")
                return False
        
        warning_message = (
            f"⚠️ **Season Transition Announcement Failed**\n"
            f"A season transition occurred, but the public announcement failed:\n"
            f"```\n{error_description}\n```\n"
            f"Please check logs and consider announcing manually."
        )
        
        await channel.send(warning_message)
        logger.info(f"[🌍] Sent mod warning to guild {guild_id}")
        return True
    
    except Exception as e:
        logger.error(f"[🌍] Failed to send mod warning: {e}", exc_info=True)
        return False


# ==================== DEPRECATED: DAILY WORLD ANNOUNCEMENT JOB ====================

async def execute_daily_world_announcements(bot):
    """
    DEPRECATED: Daily world announcements are now handled by unified_content_dispatcher.
    
    This function is kept for backward compatibility but does nothing.
    All announcement generation and delivery is now centralized in the unified dispatcher.
    """
    logger.debug("[🌍] execute_daily_world_announcements deprecated - use unified_content_dispatcher instead")
    return


# ==================== INTEGRATION: CALL FROM SEASON_ROLLOVER ====================

async def on_season_transition_success(
    old_season_id: str,
    new_season_id: str,
    trigger: str = "automatic"
):
    """
    Called by season_rollover.py when transition succeeds.
    
    Records event for later announcement.
    
    Args:
        old_season_id: e.g., "winter-2026"
        new_season_id: e.g., "spring-2026"
        trigger: "automatic", "operator", "recovery"
    """
    event_id = record_season_transition_event(old_season_id, new_season_id, trigger)
    if event_id:
        logger.info(f"[🌍] Season transition event recorded: {event_id}")
    else:
        logger.error("[🌍] Failed to record season transition event")
