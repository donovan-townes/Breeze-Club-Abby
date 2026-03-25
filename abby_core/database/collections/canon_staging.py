"""
Canon Staging Collection Module

Purpose: Staged canonical changes (persona, lore, etc) awaiting approval
Schema: Pending canon updates with versioning
Indexes: status, created_at, type

Manages:
- Staged persona changes
- Pending lore updates
- Canon approval workflow
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
    return get_database()["canon_staging"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("status", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("type", 1)])
        logger.debug("[canon_staging] Indexes created")
    except Exception as e:
        logger.warning(f"[canon_staging] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[canon_staging] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[canon_staging] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[canon_staging] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[canon_staging] Error initializing: {e}")
        return False


class CanonStaging(CollectionModule):
    collection_name = "canon_staging"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not CanonStaging.collection_name:
            raise RuntimeError("collection_name not set for CanonStaging")
        return get_database()[CanonStaging.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
