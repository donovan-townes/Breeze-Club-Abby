"""
Leveling system architecture for Abby.

Design Philosophy:
- Levels are permanent and guild-scoped (never reset)
- XP is seasonal and guild-scoped (reset every season)
- All users start at Level 1 (implicit, now explicit)
- Experience required per level increases with a curve
- Levels affect player interactions with Abby
- Seasons are system-wide canon events (not guild-configurable)

Season Schedule:
Seasons are predefined astronomical boundaries (see system_state for details):
- Winter: Dec 21 – Mar 19
- Spring: Mar 20 – Jun 20
- Summer: Jun 21 – Sep 21
- Fall: Sep 22 – Dec 20

Resets are triggered by system.season_rollover job (scheduler-driven).
Operators control seasonal transitions through /operator economy commands.

Leveling Formula:
- XP Required for Level N = base_xp * (N ^ factor)
- base_xp = 1000 (XP to reach level 2)
- factor = 1.5 (exponential curve)
- Examples:
  - Level 1->2: 1,000 XP
  - Level 2->3: ~2,828 XP
  - Level 3->4: ~5,196 XP
  - Level 10->11: ~57,665 XP
  - Level 20->21: ~1,858,482 XP
"""

from datetime import datetime
from abby_core.database.collections.game_stats import GameStats
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


# ==================== CONSTANTS ====================

LEVEL_BASE_XP = 1000       # XP required to reach level 2
LEVEL_FACTOR = 1.5        # Exponential curve factor
MIN_LEVEL = 1             # Starting level for all users


# ==================== GAME STATS COLLECTION ====================

def get_game_stats_collection():
    """Get the game_stats collection from configured database (respects dev/prod)."""
    return GameStats.get_collection()


def get_game_stats(user_id, guild_id, game_type: str = "emoji"):
    """Get user's game stats for a specific game type in a guild.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        game_type: Game type (e.g., "emoji")
    
    Returns:
        dict: Game stats or None if not found
    """
    user_id = str(user_id)
    guild_id = str(guild_id)
    
    collection = get_game_stats_collection()
    return collection.find_one({
        "user_id": user_id,
        "guild_id": guild_id,
        "game_type": game_type
    })


def initialize_game_stats(user_id, guild_id, game_type: str = "emoji"):
    """Initialize game stats for a user.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        game_type: Game type (e.g., "emoji")
    
    Returns:
        dict: Initialized stats document
    """
    user_id = str(user_id)
    guild_id = str(guild_id)
    
    collection = get_game_stats_collection()
    
    stats = {
        "user_id": user_id,
        "guild_id": guild_id,
        "game_type": game_type,
        "games_played": 0,
        "games_won": 0,
        "games_lost": 0,
        "win_rate": 0.0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    collection.insert_one(stats)
    logger.debug(f"[🎮] Initialized game stats for user {user_id} in guild {guild_id}")
    return stats


def record_game_result(user_id, guild_id, won: bool, game_type: str = "emoji"):
    """Record a game result (win or loss).
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        won: True if user won, False if lost
        game_type: Game type (e.g., "emoji")
    """
    user_id = str(user_id)
    guild_id = str(guild_id)
    
    collection = get_game_stats_collection()
    
    # Get or initialize stats
    stats = get_game_stats(user_id, guild_id, game_type)
    if not stats:
        stats = initialize_game_stats(user_id, guild_id, game_type)
    
    # Update stats
    games_played = stats.get("games_played", 0) + 1
    games_won = stats.get("games_won", 0) + (1 if won else 0)
    games_lost = stats.get("games_lost", 0) + (0 if won else 1)
    win_rate = (games_won / games_played * 100) if games_played > 0 else 0.0
    
    collection.update_one(
        {
            "user_id": user_id,
            "guild_id": guild_id,
            "game_type": game_type
        },
        {"$set": {
            "games_played": games_played,
            "games_won": games_won,
            "games_lost": games_lost,
            "win_rate": round(win_rate, 1),
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )
    
    logger.debug(f"[🎮] Recorded {'win' if won else 'loss'} for user {user_id}")


def get_game_leaderboard(guild_id, game_type: str = "emoji", limit: int = 10):
    """Get top game players by win count.
    
    Args:
        guild_id: Discord guild ID
        game_type: Game type (e.g., "emoji")
        limit: Number of top players to return
    
    Returns:
        list: List of top players with stats
    """
    guild_id = str(guild_id)
    collection = get_game_stats_collection()
    
    return list(collection.find({
        "guild_id": guild_id,
        "game_type": game_type,
        "games_played": {"$gt": 0}
    }).sort([("games_won", -1), ("win_rate", -1)]).limit(limit))


# ==================== LEVELING HELPERS ====================

def get_xp_for_level(level: int) -> int:
    """Get total XP required to reach a specific level.
    
    Args:
        level: Target level (1-indexed, so level 2 is the first level with XP cost)
    
    Returns:
        int: Total XP required from level 1
    
    Examples:
        get_xp_for_level(1) = 0        (starting level)
        get_xp_for_level(2) = 1000     (1000 XP to go from 1->2)
        get_xp_for_level(3) ≈ 3828    (total XP to reach level 3)
    """
    if level <= 1:
        return 0
    return round(LEVEL_BASE_XP * (level ** LEVEL_FACTOR))


def get_level_from_xp(xp: int) -> int:
    """Calculate player level from total XP.
    
    Args:
        xp: Total experience points
    
    Returns:
        int: Player level (minimum 1)
    
    Examples:
        get_level_from_xp(0) = 1
        get_level_from_xp(999) = 1
        get_level_from_xp(1000) = 2
        get_level_from_xp(10000) ≈ 4
    """
    if xp <= 0:
        return MIN_LEVEL
    level = int((xp / LEVEL_BASE_XP) ** (1 / LEVEL_FACTOR))
    return max(MIN_LEVEL, level)


def get_xp_progress_to_next_level(current_xp: int) -> dict:
    """Get progress toward next level.
    
    Args:
        current_xp: Current total XP
    
    Returns:
        dict: Contains level, current_xp, xp_for_level, xp_for_next_level, 
              xp_needed, xp_progress, percent_to_next
    
    Example:
        {
            "level": 2,
            "current_xp": 1500,
            "xp_for_level": 1000,
            "xp_for_next_level": 3828,
            "xp_needed": 2328,
            "xp_progress": 500,
            "percent_to_next": 21.5
        }
    """
    level = get_level_from_xp(current_xp)
    xp_for_level = get_xp_for_level(level)
    xp_for_next_level = get_xp_for_level(level + 1)
    
    xp_in_level = current_xp - xp_for_level
    xp_needed_for_level = xp_for_next_level - xp_for_level
    percent_to_next = (xp_in_level / xp_needed_for_level * 100) if xp_needed_for_level > 0 else 0
    
    return {
        "level": level,
        "current_xp": current_xp,
        "xp_for_level": xp_for_level,
        "xp_for_next_level": xp_for_next_level,
        "xp_needed": xp_needed_for_level,
        "xp_progress": xp_in_level,
        "percent_to_next": round(percent_to_next, 1)
    }


# ==================== SEASON MANAGEMENT ====================

def get_current_season() -> str:
    """Get current active season identifier from canonical system state.
    
    Returns:
        str: Season ID (e.g., "winter-2026", "spring-2026", etc.)
        
    Note: This reads from system_state collection, which is the authoritative truth.
    Never calculate seasons; always query the canonical source.
    """
    from abby_core.system.system_state import get_active_season
    
    active = get_active_season()
    if not active:
        logger.warning("[⚠️] No active season found in system_state")
        return "unknown"
    
    return active.get("state_id", "unknown")


def reset_seasonal_xp(guild_id):
    """Reset all users' seasonal XP in a guild (operator only).
    
    This is called by the system.season_rollover scheduler job when seasons change.
    Preserves levels (which are permanent).
    
    Args:
        guild_id: Discord guild ID
        
    Returns:
        int: Number of users affected
    """
    from abby_core.economy.xp import get_xp_collection
    
    guild_id = str(guild_id)
    xp_collection = get_xp_collection()
    
    result = xp_collection.update_many(
        {"guild_id": guild_id},
        {
            "$set": {
                "points": 0,
                "season_reset_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"[💰] Season reset for guild {guild_id}: {result.modified_count} users affected")
    return result.modified_count
