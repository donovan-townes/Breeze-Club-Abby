"""
Giveaways Collection Module

Purpose: Track giveaway lifecycle, entries, and winners
Schema: prize, description, channel_id, guild_id, host_id, start_time, end_time,
        duration_minutes, winner_count, participants[], winners[], active, message_id
Indexes: guild_id+active+end_time, message_id (sparse), end_time
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
    """Get giveaways collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["giveaways"]


def ensure_indexes() -> None:
    """Create indexes for giveaways collection."""
    try:
        collection = get_collection()
        collection.create_index([("guild_id", 1), ("active", 1), ("end_time", 1)])
        collection.create_index([("end_time", 1)])
        collection.create_index([("message_id", 1)], sparse=True)
        collection.create_index([("guild_id", 1), ("host_id", 1), ("start_time", -1)])
        logger.debug("[giveaways] Indexes created")
    except Exception as e:  # pragma: no cover
        logger.debug(f"[giveaways] index creation skipped: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    return False


def initialize_collection() -> bool:
    """Initialize giveaways collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[giveaways] Collection initialized")
        return True
    except Exception as e:  # pragma: no cover
        logger.error(f"[giveaways] Error initializing: {e}")
        return False


class Giveaways(CollectionModule):
    """Collection module for giveaways - follows foolproof pattern."""

    collection_name = "giveaways"

    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get giveaways collection."""
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
