"""
Unified Content Dispatcher Job Handler

Consolidates ALL announcement lifecycle phases into a single, deterministic job:
- Generation Phase: Pending → Generated (LLM calls for season transitions, system events)
- Delivery Phase: Generated → Delivered (Send to Discord channels)
- Cleanup Phase: Delivered → Archived (Periodic purge of old items)

Key Design Decisions:
1. Single job handler processes both generation and delivery in one run
2. Rate-limited to prevent Discord API throttling
3. Idempotent: safe to run every minute without duplicates
4. Atomic transitions: each item moves through lifecycle atomically
5. Single dispatcher is always active

Architecture:
```
PHASE 1: GENERATION (pending → generated)
- Query: lifecycle_state=draft, generation_status=pending
- For each item:
  - If system/world content: Call LLM (if needed)
  - Mark: lifecycle_state=generated, generation_status=ready
  - Track: generated_at timestamp, retry count

PHASE 2: DELIVERY (generated → delivered)
- Query: lifecycle_state=generated, delivery_status=pending
- Group by guild for consolidation
- For each guild:
  - Build consolidated embed (all pending announcements for guild)
  - Send to announcement channel (with fallback to mod channel)
  - Mark: lifecycle_state=delivered OR delivery_status=partial
  - Track: delivered_at timestamp, delivery result (channel_id, message_id)

PHASE 3: CLEANUP (delivered → archived, optional)
- Query: lifecycle_state=delivered, created_at < (now - 7 days)
- Delete or archive to backup collection
- Can be disabled for retention
```

Idempotency Strategy:
- Each phase checks for items in specific states before processing
- Marking transitions is atomic (MongoDB single-document write)
- Duplicate detection via idempotency_key (optional, for deduplication)
- Safe to run concurrently (no shared state, only database operations)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List
from bson import ObjectId

from abby_core.observability.logging import logging
from abby_core.services.content_delivery import (
    get_content_delivery_collection,
)
from abby_core.services.announcement_dispatcher import get_announcement_dispatcher
from abby_core.services.events_lifecycle import (
    generate_season_announcement,
    prepare_season_transition_announcement,
)
from abby_core.services.conversation_service import get_conversation_service
from abby_core.llm.context_factory import build_conversation_context
from abby_core.personality.manager import get_personality_manager

logger = logging.getLogger(__name__)


# Rate limiting
MAX_GENERATION_PER_RUN = 10
MAX_DELIVERY_PER_RUN = 20
GENERATION_DELAY_SECONDS = 0.5
DELIVERY_DELAY_SECONDS = 0.2

# Retention: archive items older than this
ARCHIVE_AFTER_DAYS = 7


async def execute_unified_content_dispatcher(
    bot: Any = None,
    job_config: Optional[Dict[str, Any]] = None
) -> Tuple[int, int, int]:
    """
    Execute unified content lifecycle: generation → delivery → cleanup.

    This is the PRIMARY job handler for all announcements and content delivery.
    It replaces three separate job handlers with a single, deterministic pipeline.

    Args:
        bot: Discord bot instance (required for delivery phase)
        job_config: Job configuration (optional)

    Returns:
        (generated_count, delivered_count, archived_count)
    """
    try:
        # Phase 1: Generate pending content
        generated_count = await _phase_generate_pending_content()

        # Phase 2: Deliver generated content (requires bot for Discord API)
        delivered_count = 0
        if bot:
            # Check if bot has loaded guilds yet (during early startup, guilds may not be ready)
            if len(bot.guilds) == 0:
                logger.debug(
                    "[📦 Dispatcher] Bot not yet connected to any guilds, deferring delivery until next tick"
                )
            else:
                delivered_count = await _phase_deliver_generated_content(bot)
        else:
            logger.warning("[📦 Dispatcher] No bot instance, skipping delivery phase")

        # Phase 3: Archive old delivered content
        archived_count = await _phase_archive_old_content()

        # Log cycle completion only if there was activity
        if generated_count > 0 or delivered_count > 0 or archived_count > 0:
            logger.info(
                f"[📦 Dispatcher] Cycle complete: "
                f"{generated_count} generated, {delivered_count} delivered, {archived_count} archived"
            )

        return generated_count, delivered_count, archived_count

    except Exception as e:
        logger.error(f"[📦 Dispatcher] Unified dispatch cycle failed: {e}", exc_info=True)
        return 0, 0, 0


# ==================== PHASE 1: GENERATION ====================

async def _phase_generate_pending_content() -> int:
    """
    Phase 1: Generate messages for pending content items.

    Flow:
    1. Query items with lifecycle_state=draft, generation_status=pending
    2. Load persona once (reused for all items in this run)
    3. For each item:
       - If content_type=system (season_transition): Call LLM
       - If content_type=world (operator-provided): Mark ready immediately
       - Handle errors and track retry count
    4. Return count of successfully generated items

    Returns:
        int: Number of successfully generated items
    """
    try:
        collection = get_content_delivery_collection()

        # Query pending items (sort by priority, then created_at)
        pending_items = list(
            collection.find(
                {
                    "lifecycle_state": "draft",
                    "generation_status": "pending",
                }
            )
            .sort([("priority", -1), ("created_at", 1)])
            .limit(MAX_GENERATION_PER_RUN)
        )

        if not pending_items:
            logger.debug("[📦 Generation] No pending items to generate")
            return 0

        logger.info(
            f"[📦 Generation] Processing {len(pending_items)} pending item(s)"
        )

        # Load persona once (reused for all items)
        try:
            manager = get_personality_manager()
            active_persona_name = manager.get_active_persona_name()
            active_persona = manager.get_persona(active_persona_name)
            persona_data = {
                "name": active_persona.name if active_persona else "Abby"
            }
        except Exception as e:
            logger.error(f"[📦 Generation] Failed to load persona: {e}")
            persona_data = {"name": "Abby"}

        generated_count = 0
        failed_count = 0

        for item in pending_items:
            item_id = str(item["_id"])
            content_type = item.get("content_type", "unknown")
            guild_id = item.get("guild_id")
            dispatcher = get_announcement_dispatcher()

            try:
                logger.debug(
                    f"[📦 Generation] Processing {content_type} item {item_id} "
                    f"(guild {guild_id})"
                )
                
                if content_type == "system":
                    # System events require LLM generation (e.g., season transitions)
                    generated_message = await _generate_system_content(
                        item, persona_data
                    )
                    if generated_message:
                        if dispatcher.generate_content(
                            item_id=item_id,
                            generated_message=generated_message,
                            operator_id="system:content-dispatcher"
                        ):
                            generated_count += 1
                            logger.info(
                                f"[📦 Generation] ✅ Generated {content_type}: {item_id} operator=system:content-dispatcher"
                            )
                        else:
                            failed_count += 1
                            logger.error(
                                f"[📦 Generation] Failed to mark generated: {item_id}"
                            )
                    else:
                        failed_count += 1
                        logger.warning(
                            f"[📦 Generation] LLM returned empty message: {item_id}"
                        )
                        dispatcher.generation_failed(
                            item_id, "LLM returned empty message", operator_id="system:content-dispatcher"
                        )

                elif content_type == "world":
                    # World announcements have operator-provided content
                    # Just mark as ready immediately
                    if dispatcher.generate_content(
                        item_id=item_id,
                        generated_message=item.get("description") or item.get("title", ""),
                        operator_id="system:content-dispatcher"
                    ):
                        generated_count += 1
                        logger.debug(
                            f"[📦 Generation] ✅ Marked world content ready: {item_id} operator=system:content-dispatcher"
                        )
                    else:
                        failed_count += 1
                        logger.error(
                            f"[📦 Generation] Failed to mark ready: {item_id}"
                        )

                elif content_type in ["event", "social"]:
                    # Event/social announcements: use provided description as-is
                    if dispatcher.generate_content(
                        item_id=item_id,
                        generated_message=item.get("description", ""),
                        operator_id="system:content-dispatcher"
                    ):
                        generated_count += 1
                        logger.debug(
                            f"[📦 Generation] ✅ Marked {content_type} ready: {item_id} operator=system:content-dispatcher"
                        )
                    else:
                        failed_count += 1

                else:
                    logger.warning(
                        f"[📦 Generation] Unknown content_type: {content_type}"
                    )
                    dispatcher.generation_failed(
                        item_id, f"Unknown content_type: {content_type}", operator_id="system:content-dispatcher"
                    )
                    failed_count += 1

                # Rate limit to avoid overwhelming API
                await asyncio.sleep(GENERATION_DELAY_SECONDS)

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"[📦 Generation] Failed to generate {item_id}: {e}",
                    exc_info=True,
                )
                dispatcher.generation_failed(item_id, f"Generation error: {e}", operator_id="system:content-dispatcher")

        # Only log phase completion if there was activity
        if generated_count > 0 or failed_count > 0:
            logger.info(
                f"[📦 Generation] Phase complete: "
                f"{generated_count} succeeded, {failed_count} failed"
            )

        return generated_count

    except Exception as e:
        logger.error(f"[📦 Generation] Phase failed: {e}", exc_info=True)
        return 0


async def _generate_system_content(
    item: Dict[str, Any], persona_data: Dict[str, Any]
) -> Optional[str]:
    """
    Generate message for a system content item (requires LLM).

    Supports:
    - season_transition: Use LLM with special context
    - world_announcement: Use LLM with broadcast prompt

    Args:
        item: Content delivery item document
        persona_data: Current persona

    Returns:
        Generated message or None if failed
    """
    event_type = item.get("context_refs", {}).get("event_type", "unknown")
    title = item.get("title", "")
    description = item.get("description", "")
    guild_id = item.get("guild_id")

    try:
        if event_type == "season_transition":
            # Season transitions use special generation with canon data
            transition_context = prepare_season_transition_announcement(item)
            message = await generate_season_announcement(
                persona_data, transition_context
            )
            return message

        else:
            # Generic broadcast-style generation for other system events
            prompt = (
                "Take this announcement and enhance it with personality, enthusiasm, and clarity. "
                "Keep it concise (under 200 words), avoid chatty back-and-forth tone, "
                "and preserve key details.\n\n"
                f"Title: {title}\n"
                f"Content: {description}"
            )

            context = build_conversation_context(
                user_id="system:content-dispatcher",
                guild_id=guild_id,
                user_name="System",
                intent="CASUAL_CHAT",  # Safe intent for content generation
                chat_history=[]
            )

            conversation_service = get_conversation_service()
            message, error = await conversation_service.generate_response(
                prompt, context, max_tokens=300, max_retries=2
            )
            if error:
                logger.warning(f"[Content Dispatcher] Generation failed: {error}")
                return None
            return message if message else None

    except Exception as e:
        logger.error(
            f"[📦 Generation] LLM call failed for {event_type}: {e}",
            exc_info=True,
        )
        return None


# ==================== PHASE 2: DELIVERY ====================

async def _phase_deliver_generated_content(bot: Any) -> int:
    """
    Phase 2: Deliver generated content to Discord.

    Flow:
    1. Query items with lifecycle_state=generated, delivery_status=pending
    2. Group by guild for consolidation (one embed per guild)
    3. For each guild:
       - Build consolidated embed
       - Send to configured announcement channel (with fallback to mod channel)
       - Mark delivered or partial
    4. Return count of successfully delivered items

    Args:
        bot: Discord bot instance (required for Discord API calls)

    Returns:
        int: Number of successfully delivered items
    """
    try:
        dispatcher = get_announcement_dispatcher()
        collection = get_content_delivery_collection()

        # Query generated items ready for delivery (only if scheduled_at <= now)
        now = datetime.utcnow()
        query = {
            "lifecycle_state": "generated",
            "delivery_status": "pending",
            "$or": [
                {"scheduled_at": {"$lte": now}},  # Scheduled time has passed
                {"scheduled_at": None},           # No schedule (immediate)
                {"scheduled_at": {"$exists": False}}  # Items without scheduled_at
            ]
        }
        
        # Debug: log query details
        logger.debug(f"[📦 Delivery] Query time: {now.isoformat()}")
        
        pending_delivery = list(
            collection.find(query)
            .sort("priority", -1)
            .limit(MAX_DELIVERY_PER_RUN)
        )
        
        # Debug: log items and their scheduled times
        for item in pending_delivery:
            sched = item.get("scheduled_at")
            logger.debug(
                f"[📦 Delivery] Found item {str(item['_id'])[:12]}... "
                f"scheduled_at={sched} (type={type(sched).__name__})"
            )

        if not pending_delivery:
            logger.debug("[📦 Delivery] No items ready for delivery")
            return 0

        logger.info(
            f"[📦 Delivery] Processing {len(pending_delivery)} item(s) for delivery"
        )

        # Group by guild for consolidation
        by_guild: Dict[int, List[Dict[str, Any]]] = {}
        for item in pending_delivery:
            guild_id = int(item.get("guild_id", 0))
            if guild_id not in by_guild:
                by_guild[guild_id] = []
            by_guild[guild_id].append(item)

        delivered_count = 0
        failed_count = 0

        # Process each guild
        for guild_id, items in by_guild.items():
            try:
                # Build consolidated embed for this guild
                embed = await _build_consolidated_embed(items)
                if not embed:
                    logger.warning(
                        f"[📦 Delivery] Failed to build embed for guild {guild_id}"
                    )
                    failed_count += len(items)
                    continue

                # Send to Discord
                success, channel_id, message_id, error = await _send_to_guild(
                    bot, guild_id, embed
                )

                if success and message_id is not None and channel_id is not None:
                    # Mark all items for this guild as delivered
                    delivered_count += len(items)
                    for item in items:
                        item_id = str(item["_id"])
                        try:
                            if dispatcher.deliver_generated(
                                item_id=item_id,
                                message_id=message_id,
                                channel_id=channel_id,
                                operator_id="system:unified-dispatcher",
                            ):
                                logger.info(
                                    f"[📦 Delivery] ✅ Marked delivered: {item_id} "
                                    f"msg={message_id} channel={channel_id}"
                                )
                            else:
                                logger.warning(
                                    f"[📦 Delivery] No update for {item_id} (already in final state?)"
                                )
                        except Exception as e:
                            logger.error(
                                f"[📦 Delivery] Failed to mark delivered: {item_id}: {e}"
                            )
                else:
                    # Delivery failed for this guild
                    failed_count += len(items)
                    logger.warning(
                        f"[📦 Delivery] Failed to deliver to guild {guild_id}: {error}"
                    )
                    
                    # For transient errors (Guild not found during startup), 
                    # keep status as "pending" so dispatcher retries on next run
                    # For permanent errors, mark as failed
                    is_transient = "Guild not found" in str(error)
                    for item in items:
                        item_id = str(item["_id"])
                        if is_transient:
                            # Use dispatcher API for transient errors (preserves metrics/audit)
                            dispatcher.mark_transient_error(
                                item_id,
                                error or "Unknown error",
                                operator_id="system:unified-dispatcher",
                            )
                            logger.info(f"[📦 Delivery] Item {item_id} marked for retry (transient error)")
                        else:
                            dispatcher.delivery_failed_generated(
                                item_id,
                                error or "Unknown error",
                                operator_id="system:unified-dispatcher",
                            )

                await asyncio.sleep(DELIVERY_DELAY_SECONDS)

            except Exception as e:
                failed_count += len(items)
                logger.error(
                    f"[📦 Delivery] Exception processing guild {guild_id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"[📦 Delivery] Phase complete: "
            f"{delivered_count} delivered, {failed_count} failed ({len(by_guild)} guilds)"
        )

        return delivered_count

    except Exception as e:
        logger.error(f"[📦 Delivery] Phase failed: {e}", exc_info=True)
        return 0


async def _build_consolidated_embed(
    items: List[Dict[str, Any]]
) -> Optional[Any]:
    """
    Build a consolidated Discord embed for multiple content items.

    Consolidation Strategy:
    - Title: Generic "System Announcements"
    - One field per item (with emoji based on content type)
    - Respects Discord's 6000 character limit
    - Truncates gracefully if too large

    Args:
        items: List of content delivery items for a guild

    Returns:
        discord.Embed or None if failed
    """
    try:
        import discord

        # Create base embed
        embed = discord.Embed(
            title="🌍 System Announcements",
            description="Updates from Abby",
            color=discord.Color.blue(),
        )

        # Track character count (Discord limit is 6000)
        title_len = len(embed.title) if embed.title else 0
        desc_len = len(embed.description) if embed.description else 0
        total_chars = title_len + desc_len + 100
        max_chars = 5500

        # Add each item as a field
        for item in items:
            item_id = str(item["_id"])
            content_type = item.get("content_type", "announcement")
            title = item.get("title", "Announcement")
            message = item.get("generated_message") or item.get("description", "")

            if not message:
                continue

            # Map content type to emoji
            emoji_map = {
                "system": "📋",
                "world": "📢",
                "event": "🎉",
                "social": "💬",
            }
            emoji = emoji_map.get(content_type, "📌")

            field_name = f"{emoji} {title}"
            field_value = message[:1024]  # Discord field value limit

            # Check if adding this field would exceed limit
            field_chars = len(field_name) + len(field_value) + 50
            if total_chars + field_chars > max_chars:
                logger.debug(
                    f"[📦 Delivery] Embed character limit reached, stopping at {len(embed.fields)} fields"
                )
                break

            embed.add_field(name=field_name, value=field_value, inline=False)
            total_chars += field_chars

        if len(embed.fields) == 0:
            logger.warning("[📦 Delivery] No fields added to embed")
            return None

        embed.set_footer(text=f"— Abby ({len(embed.fields)} announcement(s))")
        return embed

    except Exception as e:
        logger.error(f"[📦 Delivery] Failed to build embed: {e}", exc_info=True)
        return None


async def _send_to_guild(
    bot: Any, guild_id: int, embed: Any
) -> Tuple[bool, Optional[int], Optional[int], Optional[str]]:
    """
    Send a consolidated embed to a guild's announcement channel.

    Fallback strategy:
    1. Try guild's configured announcement channel (from guild_configuration)
    2. Fall back to server mod channel
    3. Log warning if both fail

    Args:
        bot: Discord bot instance
        guild_id: Target guild ID
        embed: Consolidated announcement embed

    Returns:
        (success: bool, channel_id: int, message_id: int, error: str)
    """
    try:
        from abby_core.database.collections.guild_configuration import get_guild_config

        guild = bot.get_guild(int(guild_id))
        if not guild:
            error = f"Guild not found: {guild_id}"
            logger.warning(f"[📦 Delivery] {error}")
            return False, None, None, error

        # Get configured announcement channel from guild_configuration
        guild_config = get_guild_config(int(guild_id))
        announcement_channel_id = None

        if guild_config:
            channels = guild_config.get("channels", {})
            announcement_channel_obj = channels.get("announcements")
            # Extract ID from nested structure: {"id": {...}, "description": "..."}
            if isinstance(announcement_channel_obj, dict):
                announcement_channel_id = announcement_channel_obj.get("id")
            else:
                announcement_channel_id = announcement_channel_obj

        # Try to send to announcement channel first
        if announcement_channel_id:
            try:
                channel = guild.get_channel(int(announcement_channel_id))
                if channel and channel.permissions_for(guild.me).send_messages:
                    message = await channel.send(embed=embed)
                    logger.info(
                        f"[📦 Delivery] ✅ Sent to announcement channel {announcement_channel_id}"
                    )
                    return True, channel.id, message.id, None
            except Exception as e:
                logger.debug(
                    f"[📦 Delivery] Announcement channel send failed: {e}, trying fallback"
                )

        # Fallback: try server mod channel (configured system channel)
        mod_channel = guild.system_channel
        if mod_channel and mod_channel.permissions_for(guild.me).send_messages:
            try:
                message = await mod_channel.send(embed=embed)
                logger.info(
                    f"[📦 Delivery] ✅ Sent to mod channel {mod_channel.id} (fallback)"
                )
                return True, mod_channel.id, message.id, None
            except Exception as e:
                error = f"Fallback mod channel send failed: {e}"
                logger.error(f"[📦 Delivery] {error}")
                return False, None, None, error

        # All attempts failed
        error = "No valid announcement or mod channel available"
        logger.error(f"[📦 Delivery] {error}")
        return False, None, None, error

    except Exception as e:
        error = f"Failed to send to guild: {e}"
        logger.error(f"[📦 Delivery] {error}", exc_info=True)
        return False, None, None, error


# ==================== PHASE 3: ARCHIVE ====================

async def _phase_archive_old_content() -> int:
    """
    Phase 3: Archive old delivered content (optional cleanup).

    Flow:
    1. Query items with lifecycle_state=delivered, created_at < (now - ARCHIVE_AFTER_DAYS)
    2. Mark as archived (or delete if archiving disabled)
    3. Return count of archived items

    Returns:
        int: Number of archived items
    """
    try:
        collection = get_content_delivery_collection()

        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=ARCHIVE_AFTER_DAYS)

        # Query old delivered items
        old_items = list(
            collection.find(
                {
                    "lifecycle_state": "delivered",
                    "created_at": {"$lt": cutoff_date},
                }
            ).limit(100)
        )

        if not old_items:
            logger.debug("[📦 Cleanup] No old items to archive")
            return 0

        logger.info(f"[📦 Cleanup] Archiving {len(old_items)} old item(s)")

        # Mark as archived via dispatcher (keeps audit trail and metrics)
        from abby_core.services.announcement_dispatcher import AnnouncementDispatcher
        dispatcher = AnnouncementDispatcher()
        
        archived_count = 0
        for item in old_items:
            item_id = str(item["_id"])
            try:
                # Route through dispatcher for metrics/audit consistency
                if dispatcher.archive(
                    item_id,
                    operator_id="system:cleanup",
                ):
                    archived_count += 1
            except Exception as e:
                logger.error(f"[📦 Cleanup] Failed to archive {item_id}: {e}")

        if archived_count > 0:
            logger.info(f"[📦 Cleanup] Archived {archived_count} item(s)")
        return archived_count

    except Exception as e:
        logger.error(f"[📦 Cleanup] Phase failed: {e}", exc_info=True)
        return 0
