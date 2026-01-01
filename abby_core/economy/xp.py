
from pymongo import MongoClient
from datetime import datetime
import discord
from discord.ext import commands
import sys
from pathlib import Path

# Import unified MongoDB client
from abby_core.database.mongodb import connect_to_mongodb
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


# ==================== XP Database Helper Functions ====================
def get_xp_collection():
    """Get the unified XP collection from Abby_Database."""
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    return db["user_xp"]


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
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    xp_collection = get_xp_collection()
    
    # Get current XP or initialize
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        user_data = {
            "user_id": user_id,
            "guild_id": guild_id,
            "points": 0,
            "level": 1,
            "created_at": datetime.utcnow()
        }
        xp_collection.insert_one(user_data)
    
    new_points = max(0, user_data.get("points", 0) + amount)
    new_level = get_level_from_xp(new_points)
    
    query = {"user_id": user_id}
    if guild_id:
        query["guild_id"] = guild_id
    
    xp_collection.update_one(
        query,
        {"$set": {"points": new_points, "level": new_level, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    logger.debug(f"[XP] User {user_id} XP: {new_points} (±{amount}, reason: {reason})")
    return new_points


# ==================== XP Helper Functions ====================


def initialize_xp(user_id, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    logger.info(f"[XP] Initializing XP for user {user_id} in guild {guild_id}")
    # Use unified client to ensure user has XP entry (will create with defaults if not exists)
    add_xp(user_id, 0, guild_id, "initialization")

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
            {"$set": {"level": 1, "points": 0, "updated_at": datetime.utcnow()}}
        )
        logger.info(f"[💰] Level & Experience points RESET for user {user_id}.")


def increment_xp(user_id, increment, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        initialize_xp(user_id, guild_id)
        user_data = get_xp(user_id, guild_id)
    
    # Add XP using unified client
    add_xp(user_id, increment, guild_id, "message")
    
    # Get updated data to check for level up
    updated_data = get_xp(user_id, guild_id)
    new_xp = updated_data.get("points", 0)
    
    return check_thresholds(user_id, new_xp, guild_id)


def decrement_xp(user_id, increment, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data:
        initialize_xp(user_id, guild_id)
        user_data = get_xp(user_id, guild_id)

    current_points = user_data.get("points", 0)
    decrement_amount = -abs(increment)  # Ensure negative
    new_xp = max(0, current_points + decrement_amount)  # Prevent negative XP
    
    # Update using unified client
    add_xp(user_id, decrement_amount, guild_id, "penalty")
    logger.info(f"[💰] User: {user_id} XP decremented to {new_xp}")


def get_level_from_xp(xp):
    # Calculate level from xp
    base_xp = 1000
    factor = 1.5
    level = int((xp / base_xp) ** (1 / factor))
    return level


def get_level(user_id):
    """Get user's current level"""
    user_id = str(user_id)
    user_data = get_xp(user_id)
    if not user_data:
        initialize_xp(user_id)
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
    return user_data.get("points", 0)



def update_old_users():
    """DEPRECATED: This function is for legacy per-user databases only.
    After migration to unified schema, this function is no longer needed."""
    logger.warning("[XP] update_old_users() called but is deprecated - unified schema doesn't need this")


def check_thresholds(user_id, new_xp, guild_id=None):
    user_id = str(user_id)
    guild_id = str(guild_id) if guild_id else None
    user_data = get_xp(user_id, guild_id)
    if not user_data or 'level' not in user_data:
        # Initialize with default level
        xp_collection = get_xp_collection()
        query = {"user_id": user_id}
        if guild_id:
            query["guild_id"] = guild_id
        
        xp_collection.update_one(
            query,
            {"$set": {"level": 1, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        user_data = get_xp(user_id, guild_id)

    current_level = user_data.get("level", 1)

    # Calculate the new level based on the new_xp using the get_level_from_xp function
    new_level = get_level_from_xp(new_xp)

    if new_level > current_level:
        xp_collection = get_xp_collection()
        query = {"user_id": user_id}
        if guild_id:
            query["guild_id"] = guild_id
        
        xp_collection.update_one(
            query,
            {"$set": {"level": new_level, "updated_at": datetime.utcnow()}}
        )
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

def fetch_all_users_exp():
    """
    Fetches the experience points of ALL users from the MongoDB database (global leaderboard).
    Returns all XP records across all tenants.
    
    Returns:
    - dict: A dictionary with user IDs as keys and experience points as values.
    """
    xp_collection = get_xp_collection()
    
    exp_data = {}
    # Query all XP records across all tenants (global leaderboard)
    for user_xp_data in xp_collection.find({}):
        user_id = int(user_xp_data["user_id"])
        if "points" in user_xp_data:
            exp_data[user_id] = user_xp_data["points"]

    return exp_data
