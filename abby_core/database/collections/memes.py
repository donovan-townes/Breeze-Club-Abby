"""
Memes Collection Module

Purpose: Track meme assets and voting metadata
Schema: _id (meme_url), url, upvotes, downvotes, score, timestamp
Indexes: score, timestamp

Note: This collection resides in the unified Abby database.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)

MEMES_COLLECTION_NAME = "Memes"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get Memes collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db[MEMES_COLLECTION_NAME]


def ensure_indexes() -> None:
    """Create indexes for Memes collection."""
    try:
        collection = get_collection()
        collection.create_index([("score", -1)])
        collection.create_index([("timestamp", -1)])
        logger.debug("[memes] Indexes created")
    except Exception as e:  # pragma: no cover
        logger.debug(f"[memes] index creation skipped: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    return False


def initialize_collection() -> bool:
    """Initialize Memes collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[memes] Collection initialized")
        return True
    except Exception as e:  # pragma: no cover
        logger.error(f"[memes] Error initializing: {e}")
        return False


class Memes(CollectionModule):
    """Collection module for Memes - follows foolproof pattern."""

    collection_name = MEMES_COLLECTION_NAME

    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get Memes collection."""
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
