"""
Game Stats Collection Module

Purpose: Track game performance per user/guild/game_type
Schema: user_id, guild_id, game_type, games_played, games_won, games_lost,
        win_rate, created_at, updated_at
Indexes: user_id+guild_id+game_type (unique), guild_id+game_type+games_won+win_rate
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get game_stats collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["game_stats"]


def ensure_indexes() -> None:
    """Create indexes for game_stats collection."""
    try:
        collection = get_collection()
        collection.create_index(
            [("user_id", 1), ("guild_id", 1), ("game_type", 1)], unique=True
        )
        collection.create_index(
            [("guild_id", 1), ("game_type", 1), ("games_won", -1), ("win_rate", -1)]
        )
        collection.create_index([("updated_at", -1)])
        logger.debug("[game_stats] Indexes created")
    except Exception as e:  # pragma: no cover
        logger.debug(f"[game_stats] index creation skipped: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    return False


def initialize_collection() -> bool:
    """Initialize game_stats collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[game_stats] Collection initialized")
        return True
    except Exception as e:  # pragma: no cover
        logger.error(f"[game_stats] Error initializing: {e}")
        return False


class GameStats(CollectionModule):
    """Collection module for game_stats - follows foolproof pattern."""

    collection_name = "game_stats"

    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get game_stats collection."""
        return get_collection()

    @staticmethod
    def ensure_indexes() -> None:
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
