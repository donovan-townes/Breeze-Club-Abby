"""
Users Collection Module

Purpose: User profiles and Discord account information
Schema: See schemas.py (UserProfileSchema)
Indexes: user_id (unique), discord_id, created_at

Manages:
- User profiles and metadata
- Discord account information
- Guild memberships
- User settings and preferences
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get users collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    # Use discord_profiles collection name for backward compatibility with existing code
    return db["discord_profiles"]


def ensure_indexes():
    """Create indexes for users collection."""
    try:
        collection = get_collection()

        collection.create_index([("user_id", 1)], unique=True)
        collection.create_index([("discord_id", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("guilds", 1)])

        logger.debug("[users] Indexes created")

    except Exception as e:
        logger.warning(f"[users] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[users] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[users] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize users collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[users] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[users] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user profile."""
    try:
        collection = get_collection()
        return collection.find_one({"user_id": user_id})
    except Exception as e:
        logger.error(f"[users] Error getting user {user_id}: {e}")
        return None


def upsert_user(user_id: int, user_data: Dict[str, Any]) -> bool:
    """Create or update user profile."""
    try:
        collection = get_collection()
        
        default_user = {
            "user_id": user_id,
            "discord_id": user_data.get("discord_id", user_id),
            "username": user_data.get("username", f"User{user_id}"),
            "avatar_url": user_data.get("avatar_url"),
            "guilds": user_data.get("guilds", []),
            "created_at": user_data.get("created_at", datetime.utcnow()),
            "updated_at": datetime.utcnow(),
        }
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$set": default_user},
            upsert=True
        )
        
        logger.debug(f"[users] Upserted user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[users] Error upserting user {user_id}: {e}")
        return False


def add_guild_to_user(user_id: int, guild_id: int) -> bool:
    """Add guild to user's guild list."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"guilds": guild_id}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[users] User {user_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[users] Error adding guild: {e}")
        return False


def get_user_guilds(user_id: int) -> List[int]:
    """Get list of guilds user is in."""
    try:
        user = get_user(user_id)
        return user.get("guilds", []) if user else []
    except Exception as e:
        logger.error(f"[users] Error getting guilds for user {user_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class Users(CollectionModule):
    """Collection module for users - follows foolproof pattern."""
    
    collection_name = "discord_profiles"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get users collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not Users.collection_name:
            raise RuntimeError("collection_name not set for Users")
        db = get_database()
        return db[Users.collection_name]
    
    @staticmethod
    def ensure_indexes():
        """Create all indexes for efficient querying."""
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        """Seed default data if needed."""
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        """Orchestrate initialization."""
        return initialize_collection()
