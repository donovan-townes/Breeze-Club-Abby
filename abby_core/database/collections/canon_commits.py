"""
Canon Commits Collection Module

Purpose: History of approved canonical changes (immutable audit trail)
Schema: Change records with versions and timestamps
Indexes: type, created_at, version

Manages:
- Canon change history
- Version tracking
- Rollback support
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    return get_database()["canon_commits"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("type", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("version", -1)])
        logger.debug("[canon_commits] Indexes created")
    except Exception as e:
        logger.warning(f"[canon_commits] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[canon_commits] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[canon_commits] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[canon_commits] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[canon_commits] Error initializing: {e}")
        return False


class CanonCommits(CollectionModule):
    collection_name = "canon_commits"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not CanonCommits.collection_name:
            raise RuntimeError("collection_name not set for CanonCommits")
        return get_database()[CanonCommits.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
