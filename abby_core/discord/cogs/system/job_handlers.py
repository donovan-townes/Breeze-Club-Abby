"""
Job Handler Registrations

This file registers all scheduled job handlers with the centralized scheduler.
Each handler is responsible for executing a specific job type.

Handler Contract:
    async def handler(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
        # Execute job
        # Update last_run_at via set_guild_config
        pass

Job handlers should:
1. Validate job_config has required fields
2. Execute the job logic
3. Update job's last_run_at timestamp
4. Handle their own errors (don't raise to scheduler)
"""

import discord
from discord.ext import commands
from typing import Dict, Any
from datetime import datetime

from abby_core.discord.cogs.system.registry import register_job_handler, JOB_HANDLERS
from abby_core.database.collections.guild_configuration import set_guild_config
from abby_core.discord.cogs.events.valentine_hearts import handle_valentine_hearts_job
from abby_core.discord.cogs.events.easter_eggs import handle_easter_eggs_job

try:
    from tdos_intelligence.observability import logging
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None


# ════════════════════════════════════════════════════════════════════════════════
# SEASON ROLLOVER HANDLER (SYSTEM GLOBAL JOB)
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.season_rollover")  # Matches scheduling.jobs.system.season_rollover
async def handle_season_rollover(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Execute platform-wide season rollover (global system job).
    
    This job runs daily to check if a season boundary has been crossed.
    When crossed, it transitions to the new season and resets XP for all guilds.
    
    Note: This is a SYSTEM job, not per-guild. The guild_id parameter is ignored.
    
    Job config fields:
        - enabled: Whether the job is active
        - time: HH:MM check time (when to evaluate season boundary)
        - last_executed_at: Last execution timestamp
    """
    try:
        from abby_core.discord.cogs.system.jobs.season_rollover import execute_season_rollover
        
        # Execute the rollover logic
        await execute_season_rollover(bot, guild_id, job_config)
        
        # Update last_executed_at for idempotency tracking
        # Since this is a system job, we update it globally (not guild-specific)
        # This is handled in a separate system config location
        now_timestamp = datetime.utcnow().isoformat()
        if logger:
            logger.debug(f"[🌍] Season rollover job last executed at {now_timestamp}")
        
    except Exception as e:
        if logger:
            logger.error(f"[🌍] Season rollover handler failed: {e}", exc_info=True)
        if logger:
            logger.error(f"[📝 Generation] Background generation job failed: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# WORLD ANNOUNCEMENTS (LEGACY - NO-OP HANDLER)
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.announcements.daily_world_announcements")
async def handle_daily_world_announcements(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    DEPRECATED: Daily world announcements are now handled by unified_content_dispatcher.
    
    This handler exists only to prevent "no handler registered" warnings.
    The actual announcement system works as follows:
    
    ARCHITECTURE:
    1. Season rollover (system.season_rollover) detects season transitions
    2. on_season_transition_success() records events in content_delivery_items
    3. unified_content_dispatcher processes content_delivery_items:
       - Generation phase: LLM generates announcement text
       - Delivery phase: Sends to Discord channels
       - Cleanup phase: Archives old delivered items
    
    FLOW:
    ┌─────────────────────────────────────────────────────┐
    │ Season Rollover (automatic daily check)            │
    │ ↓                                                   │
    │ Detect transition (winter → spring)                │
    │ ↓                                                   │
    │ record_season_transition_event()                   │
    │   → Creates entries in content_delivery_items      │
    │      (one per guild, type="system")                │
    │ ↓                                                   │
    │ unified_content_dispatcher (runs every 60s)        │
    │   → Phase 1: Generate (LLM call)                   │
    │   → Phase 2: Deliver (Discord channels)            │
    │   → Phase 3: Cleanup (archive old items)           │
    └─────────────────────────────────────────────────────┘
    
    This no-op handler prevents scheduler warnings when legacy job configs
    still reference "system.announcements.daily_world_announcements".
    """
    if logger:
        logger.debug(
            "[🌍] daily_world_announcements job called (no-op) - "
            "unified_content_dispatcher handles all announcements"
        )


# ════════════════════════════════════════════════════════════════════════════════
# EVENT LIFECYCLE HANDLER (SYSTEM GLOBAL JOB)
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.event_lifecycle")
async def handle_event_lifecycle(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Execute platform-wide event lifecycle checks (global system job).
    
    This job runs daily to check if event boundaries have been crossed:
    - Auto-activates events when start_at is reached
    - Auto-deactivates events when end_at is passed
    - Records event start/end for announcements
    
    Events handled:
    - Valentine's Day (Feb 1-14): crush_system_enabled
    - Easter (Good Friday-Easter Sunday): egg_hunt_enabled
    - 21 Days of the Breeze (Dec 1-21): breeze_event_enabled
    - Any custom operator-created events with date boundaries
    
    Note: This is a SYSTEM job, not per-guild. The guild_id parameter is ignored.
    
    Flow:
    1. Get all event states from system_state
    2. For each event, check if current date is within [start_at, end_at]
    3. Activate if should be active but isn't, deactivate if should be inactive but is
    4. Record event start/end via events_lifecycle.record_event_start/end()
    5. Announcements are queued for daily scheduled time
    """
    from abby_core.discord.cogs.system.jobs.event_lifecycle import execute_event_lifecycle
    
    if logger:
        logger.info(f"[📅] Executing platform-wide event lifecycle (system job)")
    
    try:
        await execute_event_lifecycle(bot, guild_id, job_config)
        
        if logger:
            logger.info(f"[✅] Event lifecycle check completed successfully")
    
    except Exception as e:
        if logger:
            logger.error(f"[❌] Event lifecycle check failed: {e}", exc_info=True)
        # Don't raise - let scheduler continue with other jobs


# ════════════════════════════════════════════════════════════════════════════════
# EMOJI GAME HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("games.emoji")  # Matches scheduling.jobs.games.emoji
async def handle_emoji_game(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Execute scheduled emoji game.
    
    Job config fields:
        - time: HH:MM start time
        - duration_minutes: Game duration
        - last_executed_at: Last execution timestamp (updated by handler)
    """
    try:
        # Import here to avoid circular dependencies
        from abby_core.discord.cogs.entertainment.games import GamesManager
        
        # Get duration from job config
        duration_minutes = job_config.get("duration_minutes", 5)
        
        # Get channel from guild config
        from abby_core.database.collections.guild_configuration import get_guild_config
        guild_config = get_guild_config(guild_id)
        channels = guild_config.get("channels", {})
        game_channel_id = channels.get("auto_game", {}).get("id")
        
        if not game_channel_id:
            if logger:
                logger.warning(f"[🎮] No game channel configured for guild {guild_id}")
            return
        
        # Get channel
        channel = bot.get_channel(game_channel_id)
        if not channel:
            if logger:
                logger.warning(f"[🎮] Game channel {game_channel_id} not found for guild {guild_id}")
            return
        
        # Get the games cog
        games_cog = bot.get_cog("GamesManager")
        if not games_cog or not hasattr(games_cog, '_run_game'):
            if logger:
                logger.error(f"[🎮] GamesManager cog not loaded or missing _run_game method")
            return

        if getattr(games_cog, "active_game", False):
            if logger:
                logger.info(f"[🎮] Skipping scheduled emoji game for guild {guild_id}: game already active")
            return
        
        # Start the game
        if logger:
            logger.info(f"[🎮] Starting scheduled emoji game in guild {guild_id}, duration {duration_minutes}m")
        
        await games_cog._run_game(channel, starter=None, duration_minutes=duration_minutes)  # type: ignore
        
        # Update last_executed_at
        now_timestamp = datetime.now().isoformat()
        set_guild_config(
            guild_id,
            {"scheduling": {"jobs": {"games": {"emoji": {"last_executed_at": now_timestamp}}}}},
            audit_user_id="scheduler"
        )
        
    except Exception as e:
        if logger:
            logger.error(f"[🎮] Emoji game handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# RANDOM MESSAGES HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("community.random_messages")  # Matches scheduling.jobs.community.random_messages
async def handle_random_messages(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Execute scheduled random messages with deduplication.
    
    Job config fields:
        - time: HH:MM start time (for daily schedule)
        - interval_hours: Interval between messages (for interval schedule)
        - last_executed_at: Last execution timestamp (updated by handler)
    
    Deduplication:
    - Checks if the last message in the channel was already a random message
    - If yes, skips sending to avoid spam
    - Manual trigger via /random-messages bypasses this check
    """
    try:
        # Skip if bot not fully connected yet
        if not bot.is_ready():
            if logger:
                logger.info(f"[✨] Bot not ready; skipping random messages job for guild {guild_id}")
            return

        # Get channel from guild config
        from abby_core.database.collections.guild_configuration import get_guild_config
        guild_config = get_guild_config(guild_id)
        if not guild_config:
            if logger:
                logger.warning(f"[✨] Guild {guild_id} config not found")
            return
        
        channels = guild_config.get("channels", {})
        channel_id = channels.get("random_messages", {}).get("id")
        
        if not channel_id:
            if logger:
                logger.warning(f"[✨] No random messages channel configured for guild {guild_id}")
            return
        
        # Handle MongoDB NumberLong format
        try:
            if isinstance(channel_id, dict):
                channel_id = int(channel_id.get("$numberLong", 0))
            else:
                channel_id = int(channel_id)
        except (TypeError, ValueError):
            if logger:
                logger.error(f"[✨] Invalid channel ID format for guild {guild_id}")
            return

        channel = bot.get_channel(channel_id)
        if not channel:
            if logger:
                logger.info(
                    f"[✨] Random messages channel {channel_id} not cached yet for guild {guild_id}; skipping"
                )
            return
        
        # Get the RandomMessages cog
        random_cog = bot.get_cog("RandomMessages")
        if not random_cog:
            if logger:
                logger.error(
                    f"[✨] RandomMessages cog not loaded - job scheduled but cog doesn't exist. "
                    f"Either create the cog at abby_core/discord/cogs/community/random_messages.py or disable this job."
                )
            return
        
        if not hasattr(random_cog, 'send_random_message_to_channel'):
            if logger:
                logger.error(
                    f"[✨] RandomMessages cog loaded but missing 'send_random_message_to_channel' method. "
                    f"Check cog implementation."
                )
            return
        
        # Send random message (with dedup check)
        # Type guard: ensure channel is TextChannel with guild attribute
        guild_name = "Community"
        if isinstance(channel, discord.TextChannel) and channel.guild:
            guild_name = channel.guild.name
        
        if logger:
            logger.info(f"[✨] Attempting scheduled random message in guild {guild_id}")
        
        # Type ignore: RandomMessages cog has the method even though base Cog doesn't
        success = await random_cog.send_random_message_to_channel(  # type: ignore[attr-defined]
            guild_id, 
            channel_id, 
            guild_name,
            check_dedup=True  # Enable dedup for scheduled sends
        )
        
        # Only update last_executed_at if we actually sent something
        if success:
            now_timestamp = datetime.now().isoformat()
            set_guild_config(
                guild_id,
                {"scheduling": {"jobs": {"community": {"random_messages": {"last_executed_at": now_timestamp}}}}},
                audit_user_id="scheduler"
            )
            if logger:
                logger.info(f"[✨] Updated last_executed_at to {now_timestamp} for guild {guild_id}")
        else:
            if logger:
                logger.debug(f"[✨] Message not sent (dedup skip or other reason) for guild {guild_id}")
        
    except Exception as e:
        if logger:
            logger.error(f"[✨] Random messages handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# NUDGE HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("community.nudge")  # Matches scheduling.jobs.community.nudge
async def handle_nudge(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Execute scheduled user nudge (engagement reminder).
    
    Job config fields:
        - time: HH:MM start time
        - interval_hours: Interval between nudges
        - last_executed_at: Last execution timestamp (updated by handler)
    """
    try:
        # Get the NudgeHandler cog
        nudge_cog = bot.get_cog("NudgeHandler")
        if not nudge_cog:
            if logger:
                logger.warning(f"[👈] NudgeHandler cog not loaded")
            return
        
        if logger:
            logger.info(f"[👈] Running scheduled nudge check in guild {guild_id}")
        
        # Trigger nudge logic (delegate to cog's nudge_users method)
        if hasattr(nudge_cog, 'nudge_users') and hasattr(nudge_cog.nudge_users, 'callback'):  # type: ignore[attr-defined]
            # Call the callback directly to trigger nudge logic
            await nudge_cog.nudge_users()  # type: ignore[attr-defined]
        
        # Update last_executed_at
        now_timestamp = datetime.now().isoformat()
        set_guild_config(
            guild_id,
            {"scheduling": {"jobs": {"community": {"nudge": {"last_executed_at": now_timestamp}}}}},
            audit_user_id="scheduler"
        )
        
    except Exception as e:
        if logger:
            logger.error(f"[👈] Nudge handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# MOTD HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.motd")  # Matches scheduling.jobs.system.motd
async def handle_motd(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """Execute scheduled MOTD."""
    try:
        # Get the MOTD cog
        motd_cog = bot.get_cog("MOTD")
        if not motd_cog or not hasattr(motd_cog, 'send_scheduled_motd'):
            if logger:
                logger.error(f"[📅] MOTD cog not loaded or missing send_scheduled_motd method")
            return
        
        if logger:
            logger.info(f"[📅] Sending scheduled MOTD in guild {guild_id}")
        
        # Send MOTD (method handles channel lookup internally)
        await motd_cog.send_scheduled_motd(guild_id)  # type: ignore
        
        # Update last_executed_at
        now_timestamp = datetime.now().isoformat()
        set_guild_config(
            guild_id,
            {"scheduling": {"jobs": {"system": {"motd": {"last_executed_at": now_timestamp}}}}},
            audit_user_id="scheduler"
        )
        
    except Exception as e:
        if logger:
            logger.error(f"[📅] MOTD handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# SYSTEM MAINTENANCE HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.maintenance.memory_decay")
async def handle_system_maintenance(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """Execute scheduled guild maintenance (memory decay)."""
    try:
        try:
            guild_id = int(guild_id)
        except (TypeError, ValueError):
            if logger:
                logger.warning(f"[🤖] Invalid guild id for maintenance: {guild_id}")
            return
        if guild_id <= 0:
            if logger:
                logger.warning(f"[🤖] Skipping maintenance for invalid guild id {guild_id}")
            return
        assistant_cog = bot.get_cog("GuildAssistant")
        if not assistant_cog or not hasattr(assistant_cog, 'run_guild_maintenance'):
            if logger:
                logger.error("[🤖] GuildAssistant cog not loaded or missing run_guild_maintenance")
            return
        if logger:
            logger.info(f"[🤖] Running scheduled maintenance for guild {guild_id}")
        await assistant_cog.run_guild_maintenance(guild_id)  # type: ignore
        now_timestamp = datetime.now().isoformat()
        set_guild_config(
            guild_id,
            {"scheduling": {"jobs": {"system": {"maintenance": {"memory_decay": {"last_executed_at": now_timestamp}}}}}},
            audit_user_id="scheduler",
        )
    except Exception as e:
        if logger:
            logger.error(f"[🤖] Maintenance handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# XP DAILY BONUS HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.xp_rewards.daily_bonus")
async def handle_xp_daily_bonus(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """Send daily XP bonus message via scheduler."""
    try:
        xp_cog = bot.get_cog("XPRewardManager")
        if not xp_cog or not hasattr(xp_cog, 'send_daily_bonus_message'):
            if logger:
                logger.error("[💰] XPRewardManager cog not loaded or missing send_daily_bonus_message")
            return
        if logger:
            logger.info(f"[💰] Sending scheduled XP daily bonus for guild {guild_id}")
        await xp_cog.send_daily_bonus_message(guild_id)  # type: ignore
        now_timestamp = datetime.now().isoformat()
        set_guild_config(
            guild_id,
            {"scheduling": {"jobs": {"system": {"xp_rewards": {"daily_bonus": {"last_executed_at": now_timestamp}}}}}},
            audit_user_id="scheduler",
        )
    except Exception as e:
        if logger:
            logger.error(f"[💰] XP daily bonus handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# GIVEAWAYS HANDLER
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("system.giveaways")  # Matches scheduling.jobs.system.giveaways
async def handle_giveaways(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Execute giveaway checks and cleanup.
    
    Job config fields:
        - check_interval_minutes: How often to check giveaways
        - last_executed_at: Last execution timestamp (updated by handler)
    """
    try:
        # Get the GiveawayManager cog
        giveaway_cog = bot.get_cog("GiveawayManager")
        if not giveaway_cog:
            if logger:
                logger.debug(f"[🎁] GiveawayManager cog not loaded")
            return
        
        if logger:
            logger.info(f"[🎁] Running scheduled giveaway check in guild {guild_id}")
        
        # Trigger giveaway check logic (delegate to cog's check_giveaways method)
        if hasattr(giveaway_cog, 'check_giveaways') and hasattr(giveaway_cog.check_giveaways, 'callback'):  # type: ignore[attr-defined]
            await giveaway_cog.check_giveaways()  # type: ignore[attr-defined]
        
        # Update last_executed_at
        now_timestamp = datetime.now().isoformat()
        set_guild_config(
            guild_id,
            {"scheduling": {"jobs": {"system": {"giveaways": {"last_executed_at": now_timestamp}}}}},
            audit_user_id="scheduler"
        )
        
    except Exception as e:
        if logger:
            logger.error(f"[🎁] Giveaways handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# EVENT HANDLERS - VALENTINE'S DAY HEARTS
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("events.valentine_hearts")
async def handle_valentine_hearts_registration(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Event handler for Valentine's Day hearts.
    
    When the Valentine's Day event is active and this job runs:
    - Checks if crush_system_enabled effect is active
    - Spawns heart reaction messages on random channels
    - Players click to gain +5 XP (with multipliers) and +1 crush score
    - Messages auto-delete after 60 seconds or first click
    
    Job config fields:
        - enabled: Whether the job is active
        - interval_minutes: How often to check for spawns (default 60)
        - jitter_minutes: Random variation on interval (default 15)
        - spawn_chance: Probability of spawning each run (default 0.3)
        - max_spawns_per_run: Max hearts to spawn in one execution (default 1)
    """
    try:
        await handle_valentine_hearts_job(bot, guild_id, job_config)
    except Exception as e:
        if logger:
            logger.error(f"[💗] Valentine's hearts handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# EVENT HANDLERS - EASTER EGG HUNT
# ════════════════════════════════════════════════════════════════════════════════

@register_job_handler("events.easter_eggs")
async def handle_easter_eggs_registration(bot: commands.Bot, guild_id: int, job_config: Dict[str, Any]):
    """
    Event handler for Easter egg hunt.
    
    When the Easter event is active and this job runs:
    - Checks if egg_hunt_enabled effect is active
    - Spawns egg reaction messages on random channels
    - Players click to gain +5 XP and optional coins
    - On actual Easter day: enhanced spawn rate and special effects
    - Messages auto-delete after 60 seconds or first click
    
    Job config fields:
        - enabled: Whether the job is active
        - interval_minutes: How often to check for spawns (default 60)
        - jitter_minutes: Random variation on interval (default 15)
        - spawn_chance: Probability of spawning each run (default 0.25)
        - reward_type: "xp" (XP only), "coins" (coins only), or "both" (default "xp")
        - max_spawns_per_run: Max eggs to spawn in one execution (default 1)
    """
    try:
        await handle_easter_eggs_job(bot, guild_id, job_config)
    except Exception as e:
        if logger:
            logger.error(f"[🥚] Easter eggs handler failed for guild {guild_id}: {e}", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════════
# INITIALIZATION
# ════════════════════════════════════════════════════════════════════════════════

def setup_handlers():
    """
    Initialize all job handlers.
    
    This function is called during bot startup to register all handlers
    with the scheduler. Handlers are registered via decorators above.
    """
    # Silenced - decorators already registered handlers


# Import to trigger decorator registration
setup_handlers()
# Log registry contents for debugging
try:
    from abby_core.discord.cogs.system.registry import JOB_HANDLERS as _REG
    if logger:
        logger.debug(f"[⏰] Registered {len(_REG)} guild job handlers: {sorted(list(_REG.keys()))}")
except Exception:
    pass
