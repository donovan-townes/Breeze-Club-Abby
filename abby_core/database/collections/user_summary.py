"""
User Summary Collection Module

Purpose: Materialized view of user statistics (computed from XP, economy, etc)
Schema: Denormalized user stats for fast leaderboard queries
Indexes: user_id+guild_id (unique), xp (leaderboard), level

Manages:
- Cached user statistics
- Leaderboard data
- Performance optimization for frequent queries
- Computed summaries (XP, level, balance, etc)
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
    """Get user_summary collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["user_summary"]


def ensure_indexes():
    """Create indexes for user_summary collection."""
    try:
        collection = get_collection()

        collection.create_index([("user_id", 1), ("guild_id", 1)], unique=True)
        collection.create_index([("guild_id", 1), ("xp", -1)])
        collection.create_index([("guild_id", 1), ("level", -1)])
        collection.create_index([("updated_at", -1)])

        logger.debug("[user_summary] Indexes created")

    except Exception as e:
        logger.warning(f"[user_summary] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[user_summary] No defaults to seed (computed on-demand)")
        return True
    except Exception as e:
        logger.error(f"[user_summary] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize user_summary collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[user_summary] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[user_summary] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class UserSummary(CollectionModule):
    """Collection module for user_summary - follows foolproof pattern."""
    
    collection_name = "user_summary"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get user_summary collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not UserSummary.collection_name:
            raise RuntimeError("collection_name not set for UserSummary")
        db = get_database()
        return db[UserSummary.collection_name]
    
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
