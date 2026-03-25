"""
Lore Documents Collection Module

Purpose: Canonical lore and worldbuilding documents
Schema: Lore entries and metadata
Indexes: lore_id (unique), category, created_at

Manages:
- Lore document storage
- Worldbuilding information
- Lore versioning
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
    return get_database()["lore_documents"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index(
            [("lore_id", 1)],
            unique=True,
            sparse=True,
        )
        collection.create_index([("category", 1)])
        collection.create_index([("created_at", -1)])
        logger.debug("[lore_documents] Indexes created")
    except Exception as e:
        logger.warning(f"[lore_documents] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[lore_documents] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[lore_documents] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[lore_documents] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[lore_documents] Error initializing: {e}")
        return False


class LoreDocuments(CollectionModule):
    collection_name = "lore_documents"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not LoreDocuments.collection_name:
            raise RuntimeError("collection_name not set for LoreDocuments")
        return get_database()[LoreDocuments.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
