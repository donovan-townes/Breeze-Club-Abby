"""
User Levels Collection Module

Purpose: Permanent user level tracking (separate from seasonal XP)
Schema: User level progression, independent of seasonal resets
Indexes: user_id+guild_id (unique), earned_at

Manages:
- Permanent level records (not reset seasonally)
- Level achievement tracking
- Level earned timestamps
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
    """Get user_levels collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["user_levels"]


def ensure_indexes():
    """Create indexes for user_levels collection."""
    try:
        collection = get_collection()

        collection.create_index([("user_id", 1), ("guild_id", 1)], unique=True)
        collection.create_index([("level", -1)])
        collection.create_index([("earned_at", -1)])

        logger.debug("[user_levels] Indexes created")

    except Exception as e:
        logger.warning(f"[user_levels] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[user_levels] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[user_levels] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize user_levels collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[user_levels] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[user_levels] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def get_level(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get user's level record."""
    try:
        collection = get_collection()
        return collection.find_one({"user_id": str(user_id), "guild_id": str(guild_id)})
    except Exception as e:
        logger.error(f"[user_levels] Error getting level for user {user_id}: {e}")
        return None


def set_level(user_id: int, guild_id: int, level: int, force: bool = False) -> bool:
    """Set user's level (never downgrades by default)."""
    try:
        collection = get_collection()
        user_id_str = str(user_id)
        guild_id_str = str(guild_id)
        
        existing = collection.find_one({"user_id": user_id_str, "guild_id": guild_id_str})
        
        # Don't downgrade unless forced
        if existing and existing.get("level", 1) > level and not force:
            return True
        
        collection.update_one(
            {"user_id": user_id_str, "guild_id": guild_id_str},
            {
                "$setOnInsert": {
                    "user_id": user_id_str,
                    "guild_id": guild_id_str,
                    "earned_at": datetime.utcnow(),
                },
                "$set": {"level": level, "updated_at": datetime.utcnow()},
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"[user_levels] Error setting level for user {user_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class UserLevels(CollectionModule):
    """Collection module for user_levels - follows foolproof pattern."""
    
    collection_name = "user_levels"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get user_levels collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not UserLevels.collection_name:
            raise RuntimeError("collection_name not set for UserLevels")
        db = get_database()
        return db[UserLevels.collection_name]
    
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
