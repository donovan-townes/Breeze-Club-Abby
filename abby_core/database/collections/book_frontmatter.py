"""
Book Frontmatter Collection Module

Purpose: Canonical book/frontmatter documents
Schema: Book metadata and content
Indexes: book_id (unique), created_at

Manages:
- Book information
- Frontmatter documents
- Book content
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
    return get_database()["book_frontmatter"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("book_id", 1)], unique=True)
        collection.create_index([("created_at", -1)])
        logger.debug("[book_frontmatter] Indexes created")
    except Exception as e:
        logger.warning(f"[book_frontmatter] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[book_frontmatter] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[book_frontmatter] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[book_frontmatter] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[book_frontmatter] Error initializing: {e}")
        return False


class BookFrontmatter(CollectionModule):
    collection_name = "book_frontmatter"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not BookFrontmatter.collection_name:
            raise RuntimeError("collection_name not set for BookFrontmatter")
        return get_database()[BookFrontmatter.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
