"""
XP Collection Module

Purpose: User experience points and level tracking
Schema: See schemas.py (XPSchema)
Indexes: user_id+guild_id, guild_id+xp (leaderboard)

Manages:
- User XP accumulation
- Level progression
- Guild leaderboards
- XP transaction history
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
    """Get xp collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["xp"]


def ensure_indexes():
    """Create indexes for xp collection."""
    try:
        collection = get_collection()

        collection.create_index([("user_id", 1), ("guild_id", 1)], unique=True)
        collection.create_index([("guild_id", 1), ("xp", -1)])
        collection.create_index([("guild_id", 1), ("level", -1)])
        collection.create_index([("created_at", -1)])

        logger.debug("[xp] Indexes created")

    except Exception as e:
        logger.warning(f"[xp] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[xp] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[xp] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize xp collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[xp] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[xp] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def get_xp(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get XP data for user in guild."""
    try:
        collection = get_collection()
        return collection.find_one({"user_id": user_id, "guild_id": guild_id})
    except Exception as e:
        logger.error(f"[xp] Error getting XP for user {user_id}: {e}")
        return None


def initialize_xp(user_id: int, guild_id: int) -> bool:
    """Initialize XP record for user in guild."""
    try:
        collection = get_collection()
        
        xp_data = {
            "user_id": user_id,
            "guild_id": guild_id,
            "xp": 0,
            "level": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        collection.insert_one(xp_data)
        logger.debug(f"[xp] Initialized XP for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[xp] Error initializing XP: {e}")
        return False


def add_xp(user_id: int, guild_id: int, amount: int) -> bool:
    """Add XP to user."""
    try:
        if amount < 0:
            logger.warning(f"[xp] Negative XP amount: {amount}")
            return False
            
        collection = get_collection()
        
        result = collection.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {
                "$inc": {"xp": amount},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[xp] User {user_id} not found in {guild_id}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[xp] Error adding XP: {e}")
        return False


def set_level(user_id: int, guild_id: int, level: int) -> bool:
    """Set user's level."""
    try:
        if level < 1:
            logger.warning(f"[xp] Invalid level: {level}")
            return False
            
        collection = get_collection()
        
        result = collection.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {"$set": {"level": level, "updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[xp] User {user_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[xp] Error setting level: {e}")
        return False


def get_guild_leaderboard(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get XP leaderboard for guild."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"guild_id": guild_id},
            sort=[("xp", -1)],
            limit=limit
        ))
    except Exception as e:
        logger.error(f"[xp] Error getting leaderboard: {e}")
        return []



# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class XP(CollectionModule):
    """Collection module for xp - follows foolproof pattern."""
    
    collection_name = "xp"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get xp collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not XP.collection_name:
            raise RuntimeError("collection_name not set for XP")
        db = get_database()
        return db[XP.collection_name]
    
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
