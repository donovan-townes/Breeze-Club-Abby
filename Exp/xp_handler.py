
from pymongo import MongoClient
import discord
from discord.ext import commands
import sys
from pathlib import Path

# Import unified MongoDB client
sys.path.insert(0, str(Path(__file__).parent.parent / 'abby-core'))
from utils.mongo_db import get_xp, add_xp, get_tenant_id, get_xp_collection
from utils.log_config import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


# XP helper functions using unified MongoDB client with tenant scoping
# NOTE: get_user_exp() is replaced by get_xp() from unified client

def initialize_xp(user_id):
    user_id = str(user_id)
    logger.info(f"[XP] Initializing XP for user {user_id} with tenant_id: {get_tenant_id()}")
    # Use unified client to ensure user has XP entry (will create with defaults if not exists)
    add_xp(user_id, 0, "initialization")

def get_user_level(user_id):
    user_data = get_xp(user_id)
    if not user_data or 'level' not in user_data:
        # If the user does not exist or does not have a level field, return a default value
        return 1
    return user_data["level"]

def reset_exp(user_id):
    user_id = str(user_id)
    user_data = get_xp(user_id)
    if not user_data:
        # If there is no experience data for this user, initialize it
        initialize_xp(user_id)
    else:
        # If experience data exists, reset points to zero
        xp_collection = get_xp_collection()
        xp_collection.update_one(
            {"tenant_id": get_tenant_id(), "user_id": user_id}, 
            {"$set": {"level": 1, "points": 0}}
        )
        logger.info(f"[💰] Level & Experience points RESET for user {user_id}.")


def increment_xp(user_id, increment):
    user_id = str(user_id)
    user_data = get_xp(user_id)
    if not user_data:
        initialize_xp(user_id)
        user_data = get_xp(user_id)
    
    # Add XP using unified client
    add_xp(user_id, increment, "message")
    
    # Get updated data to check for level up
    updated_data = get_xp(user_id)
    new_xp = updated_data.get("points", 0)
    
    return check_thresholds(user_id, new_xp)


def decrement_xp(user_id, increment):
    user_id = str(user_id)
    user_data = get_xp(user_id)
    if not user_data:
        initialize_xp(user_id)
        user_data = get_xp(user_id)

    current_points = user_data.get("points", 0)
    decrement_amount = -abs(increment)  # Ensure negative
    new_xp = max(0, current_points + decrement_amount)  # Prevent negative XP
    
    # Update using unified client
    add_xp(user_id, decrement_amount, "penalty")
    logger.info(f"[💰] User: {user_id} XP decremented to {new_xp}")


def get_level_from_xp(xp):
    # Calculate level from xp
    base_xp = 1000
    factor = 1.5
    level = int((xp / base_xp) ** (1 / factor))
    return level


# Legacy function kept for backward compatibility - renamed to avoid conflict with unified client
def get_xp_points(user_id):
    """Get user's XP points (legacy wrapper)"""
    user_id = str(user_id)
    user_data = get_xp(user_id)
    if not user_data:
        initialize_xp(user_id)
        return 0
    return user_data.get("points", 0)


def update_old_users():
    """DEPRECATED: This function is for legacy per-user databases only.
    After migration to unified schema, this function is no longer needed."""
    logger.warning("[XP] update_old_users() called but is deprecated - unified schema doesn't need this")


def check_thresholds(user_id, new_xp):
    user_id = str(user_id)
    user_data = get_xp(user_id)
    if not user_data or 'level' not in user_data:
        # Initialize with default level
        xp_collection = get_xp_collection()
        xp_collection.update_one(
            {"tenant_id": get_tenant_id(), "user_id": user_id},
            {"$set": {"level": 1}},
            upsert=True
        )
        user_data = get_xp(user_id)

    current_level = user_data.get("level", 1)

    # Calculate the new level based on the new_xp using the get_level_from_xp function
    new_level = get_level_from_xp(new_xp)

    if new_level > current_level:
        xp_collection = get_xp_collection()
        xp_collection.update_one(
            {"tenant_id": get_tenant_id(), "user_id": user_id},
            {"$set": {"level": new_level}}
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
    Fetches the experience points of all users from the MongoDB database.
    Uses unified tenant-scoped schema.
    
    Returns:
    - dict: A dictionary with user IDs as keys and experience points as values.
    """
    xp_collection = get_xp_collection()
    tenant_id = get_tenant_id()
    
    exp_data = {}
    # Query all XP records for current tenant
    for user_xp_data in xp_collection.find({"tenant_id": tenant_id}):
        user_id = int(user_xp_data["user_id"])
        if "points" in user_xp_data:
            exp_data[user_id] = user_xp_data["points"]

    return exp_data
