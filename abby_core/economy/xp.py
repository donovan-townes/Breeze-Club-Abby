
from datetime import datetime
import sys
from pathlib import Path

# Import unified MongoDB client
from abby_core.database.mongodb import connect_to_mongodb, get_database
from abby_core.economy.user_levels import ensure_user_level_record, set_user_level
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


# ==================== XP Database Helper Functions ====================
from abby_core.database.collections.xp import get_collection as get_xp_collection_module

def get_xp_collection():
    """Get the unified XP collection from configured database (respects dev/prod)."""
    # Delegate to collection module for consistency - uses db["xp"] not db["user_xp"]
    return get_xp_collection_module()


def get_xp(user_id, guild_id=None):
    """Get user XP data from unified database."""
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    xp_collection = get_xp_collection()
    
    query = {"user_id": user_id}
    if guild_id:
        query["guild_id"] = guild_id
    
    return xp_collection.find_one(query)


def add_xp(user_id, amount, guild_id=None, reason="manual"):
    """Add XP to user (can be negative) in unified database."""
    from abby_core.system.system_state import get_active_state
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    xp_collection = get_xp_collection()
    
    # Get current season
    active_season = get_active_state("season")
    season_id = active_season.get("state_id", "unknown") if active_season else "unknown"
    
    # Get current XP or initialize
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        user_data = {
            "user_id": user_id,
            "guild_id": guild_id,
            "xp": 0,
            "season_id": season_id,
            "created_at": datetime.utcnow()
        }
        xp_collection.insert_one(user_data)
        ensure_user_level_record(user_id, guild_id, level=1)
    
    new_xp = max(0, user_data.get("xp", user_data.get("points", 0)) + amount)
    new_level = get_level_from_xp(new_xp)
    
    query = {"user_id": user_id}
    if guild_id:
        query["guild_id"] = guild_id
    
    xp_collection.update_one(
        query,
        {"$set": {"xp": new_xp, "season_id": season_id, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    set_user_level(user_id, guild_id, new_level)
    logger.debug(f"[XP] User {user_id} XP: {new_xp} (±{amount}, reason: {reason})")
    return new_xp


# ==================== XP Helper Functions ====================


def initialize_xp(user_id, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    logger.info(f"[XP] Initializing XP for user {user_id} in guild {guild_id}")
    # Use unified client to ensure user has XP entry (will create with defaults if not exists)
    add_xp(user_id, 0, guild_id, "initialization")
    ensure_user_level_record(user_id, guild_id, level=1)

def get_user_level(user_id, guild_id=None):
    user_data = get_xp(user_id, guild_id)
    if not user_data or 'level' not in user_data:
        # If the user does not exist or does not have a level field, return a default value
        return 1
    return user_data["level"]

def reset_exp(user_id, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        # If there is no experience data for this user, initialize it
        initialize_xp(user_id, guild_id)
    else:
        # If experience data exists, reset points to zero
        xp_collection = get_xp_collection()
        query = {"user_id": user_id}
        if guild_id:
            query["guild_id"] = guild_id
        
        xp_collection.update_one(
            query, 
            {"$set": {"xp": 0, "updated_at": datetime.utcnow()}}
        )
        logger.info(f"[💰] Experience points RESET for user {user_id}.")
        set_user_level(user_id, guild_id, 1)


def reset_seasonal_xp(guild_id, new_season_id="unknown"):
    """Reset XP for all users in a guild (for seasonal rollover).
    
    Seasonal resets:
    - Reset xp to 0 (seasonal XP)
    - Update season_id
    - Keep levels intact (tracked in user_levels)
    
    Args:
        guild_id: Guild ID to reset XP for
        new_season_id: New season ID to stamp on records
    
    Returns:
        int: Number of users affected
    """
    from abby_core.system.system_state import get_active_state
    guild_id = str(guild_id)
    xp_collection = get_xp_collection()
    
    # Get current season if not provided
    if new_season_id == "unknown":
        active_season = get_active_state("season")
        new_season_id = active_season.get("state_id", "unknown") if active_season else "unknown"
    
    try:
        # Reset xp to 0 and update season_id
        result = xp_collection.update_many(
            {"guild_id": guild_id},
            {"$set": {"xp": 0, "season_id": new_season_id, "updated_at": datetime.utcnow()}}
        )
        
        affected = result.modified_count
        # Ensure level records exist (read from xp collection for backward compat with old level field)
        for doc in xp_collection.find({"guild_id": guild_id}, {"user_id": 1, "level": 1}):
            # Use level from doc if exists (backward compat), else default to 1
            level = doc.get("level", 1)
            set_user_level(doc.get("user_id"), guild_id, level)

        logger.info(f"[⚡] Seasonal XP reset for guild {guild_id}: {affected} users, season={new_season_id}")
        return affected
    
    except Exception as e:
        logger.error(f"[⚡] Failed to reset seasonal XP for guild {guild_id}: {e}")
        return 0


def increment_xp(user_id, increment, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        initialize_xp(user_id, guild_id)
        user_data = get_xp(user_id, guild_id)
    user_data = user_data or {}
    
    # Add XP using unified client
    add_xp(user_id, increment, guild_id, "message")
    
    # Get updated data to check for level up
    updated_data = get_xp(user_id, guild_id) or {}
    new_xp = updated_data.get("xp", updated_data.get("points", 0))
    
    return check_thresholds(user_id, new_xp, guild_id)


def decrement_xp(user_id, increment, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id) or {}
    if not user_data:
        initialize_xp(user_id, guild_id)
        user_data = get_xp(user_id, guild_id) or {}

    current_xp = user_data.get("xp", user_data.get("points", 0))
    decrement_amount = -abs(increment)  # Ensure negative
    new_xp = max(0, current_xp + decrement_amount)  # Prevent negative XP
    
    # Update using unified client
    add_xp(user_id, decrement_amount, guild_id, "penalty")
    logger.info(f"[💰] User: {user_id} XP decremented to {new_xp}")


def get_level_from_xp(xp):
    # Calculate level from xp
    base_xp = 1000
    factor = 1.5
    level = int((xp / base_xp) ** (1 / factor))
    return level


def get_level(user_id, guild_id=None):
    """Get user's current level, optionally guild-scoped."""
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        initialize_xp(user_id, guild_id)
        return 1
    return user_data.get("level", 1)


# Alias for backward compatibility
get_user_level = get_level


# Legacy function kept for backward compatibility - renamed to avoid conflict with unified client
def get_xp_points(user_id, guild_id=None):
    """Get user's XP points (legacy wrapper)"""
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        initialize_xp(user_id, guild_id)
        return 0
    return user_data.get("xp", user_data.get("points", 0))



def update_old_users():
    """DEPRECATED: This function is for legacy per-user databases only.
    After migration to unified schema, this function is no longer needed."""
    logger.warning("[XP] update_old_users() called but is deprecated - unified schema doesn't need this")


def check_thresholds(user_id, new_xp, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id) or {}
    
    # Get current level from user_levels collection (or default to 1)
    from abby_core.economy.user_levels import get_user_levels_collection
    levels_coll = get_user_levels_collection()
    level_doc = levels_coll.find_one({"user_id": user_id, "guild_id": guild_id})
    current_level = level_doc.get("level", 1) if level_doc else 1

    # Calculate the new level based on the new_xp using the get_level_from_xp function
    new_level = get_level_from_xp(new_xp)

    if new_level > current_level:
        # Update level in user_levels collection only
        set_user_level(user_id, guild_id, new_level)
        logger.info(f"[💰] User {user_id} leveled up to level {new_level}!")
        return True  # Indicate that the user leveled up

    return False  # Indicate that the user didn't level up


def get_xp_required(level):
    base_xp = 1000
    factor = 1.5

    xp_required = round(base_xp * (level ** factor))
    prev_xp_required = round(base_xp * ((level - 1) ** factor))

    relative_xp_required = xp_required - prev_xp_required
    relative_xp_required = 0 if relative_xp_required != relative_xp_required else relative_xp_required

    return {
        "level": level,
        "xp_required": xp_required,
        "relative_xp_required": relative_xp_required
    }

def fetch_all_users_exp(guild_id=None):
    """
    Fetch XP records.

    If guild_id is provided, only returns XP for that guild. Otherwise returns a
    merged view across all tenants, keeping the highest points seen per user to
    avoid overwriting with lower values from other guilds.

    Returns:
    - dict: user_id -> experience points
    """
    xp_collection = get_xp_collection()

    query = {}
    if guild_id is not None:
        query["guild_id"] = str(guild_id)

    exp_data = {}
    for user_xp_data in xp_collection.find(query):
        try:
            user_id = int(user_xp_data["user_id"])
        except (KeyError, ValueError, TypeError):
            continue

        xp = user_xp_data.get("xp", user_xp_data.get("points"))
        if xp is None:
            continue

        if guild_id is not None:
            exp_data[user_id] = xp
        else:
            # When aggregating globally, keep the max value per user.
            exp_data[user_id] = max(exp_data.get(user_id, 0), xp)

    return exp_data
