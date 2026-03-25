"""
Season Rollover Job Handler

System job that handles platform-wide season transitions.

Triggered by: scheduler (daily check for season boundary crossing)
Controlled by: operators via /operator economy commands
Effect: Resets seasonal XP for all users in all guilds while preserving levels

This is the canonical place where seasons change. When triggered, it:
1. Checks if current date crosses a season boundary
2. Activates the new season in system_state
3. Triggers XP reset for all guilds
4. Emits audit events
"""

from datetime import datetime
from typing import Dict, Any, Optional
from abby_core.observability.logging import logging
from abby_core.system.system_state import (
    get_active_state,
    get_season_for_date,
    activate_state
)
from abby_core.economy.leveling import reset_seasonal_xp
from abby_core.services.events_lifecycle import on_season_transition_success
from abby_core.database.collections.guild_configuration import get_all_guild_configs

logger = logging.getLogger(__name__)


async def execute_season_rollover(bot, guild_id: int, job_config: Dict[str, Any]):
    """Execute platform-wide season rollover.
    
    Note: This is a system job, so it runs once globally, not per-guild.
    The guild_id parameter is for consistency but may be ignored.
    
    Job Flow:
    1. Get current active season
    2. Check if today's date falls outside that season's boundaries
    3. If yes, find the season for today's date
    4. Activate the new season (deactivates old one)
    5. For each guild, reset seasonal XP
    6. Log audit trail
    """
    logger.info("[🌍] [SYSTEM] Executing platform-wide season rollover check...")
    
    try:
        # Get current active season
        active_season = get_active_state("season")
        if not active_season:
            logger.error("[❌] No active season found in system_state")
            return
        
        active_id = active_season.get("state_id")
        now = datetime.utcnow()
        
        # Check if today falls outside current season boundaries
        current_start = active_season.get("start_at")
        current_end = active_season.get("end_at")
        
        # Type guard
        if not isinstance(current_start, datetime) or not isinstance(current_end, datetime):
            logger.error(f"[❌] Invalid season boundaries for {active_id}")
            return
        
        if current_start <= now <= current_end:
            logger.debug(f"[✅] Active season {active_id} is still current (boundary check passed)")
            return  # No transition needed
        
        logger.info(f"[📋] Season boundary crossed! Current season {active_id} is expired")
        
        # Find the season for today's date
        next_season = get_season_for_date(now)
        if not next_season:
            logger.error(f"[❌] No season found for date {now.date()}")
            return
        
        next_id: Optional[str] = next_season.get("state_id")
        if not isinstance(next_id, str):
            logger.error(f"[❌] Invalid season ID: {next_id}")
            return
        
        if next_id == active_id:
            logger.warning(f"[⚠️] Next season is same as active: {next_id} (boundary logic issue)")
            return
        
        logger.info(f"[🌍] Transitioning: {active_id} → {next_id}")
        
        # Activate new season
        if not activate_state(next_id):
            logger.error(f"[❌] Failed to activate season {next_id}")
            return
        
        logger.info(f"[✅] Season activated: {next_id}")
        
        # Reset XP for all guilds
        logger.info("[💰] Starting seasonal XP reset for all guilds...")
        
        all_configs = get_all_guild_configs()
        reset_count = 0
        
        for config in all_configs:
            guild_id_key = config.get("guild_id")
            if not guild_id_key:
                continue
            
            users_affected = reset_seasonal_xp(guild_id_key)
            reset_count += users_affected
            logger.debug(f"[💰] Guild {guild_id_key}: {users_affected} users reset")
        
        logger.info(f"[✅] Season rollover complete: {reset_count} total users affected across all guilds")
        logger.info(f"[🌍] Platform is now in: {next_season.get('label')}")
        
        # Record event for announcement (picked up by daily_world_announcements job)
        old_season_id = str(active_season.get("state_id", "unknown")) if active_season else "unknown"
        new_season_id = str(next_season.get("state_id", "unknown")) if next_season else "unknown"
        await on_season_transition_success(old_season_id, new_season_id, trigger="automatic")
        
    except Exception as e:
        logger.error(f"[❌] Season rollover failed: {e}", exc_info=True)
        raise


# Metadata for UI display
SEASON_ROLLOVER_METADATA = {
    "category": "System Jobs",
    "label": "Season Rollover",
    "icon": "🌍",
    "editable": False,  # Do not allow users to edit season job
    "description": "Platform-wide seasonal transitions (XP resets, canon changes)"
}
