"""
RAG Metrics Collection Module

Purpose: Track RAG query performance, retrieval quality, and embedding metrics
Schema: Query metrics with timestamps and TTL
Indexes: created_at (TTL=30days), query_id, guild_id

Manages:
- RAG query performance metrics
- Retrieval quality tracking
- Embedding effectiveness
- Query latency and accuracy
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
    return get_database()["rag_metrics"]


def ensure_indexes():
    try:
        collection = get_collection()
        # TTL index: documents expire after 30 days
        collection.create_index([("created_at", 1)], expireAfterSeconds=2592000)
        collection.create_index([("query_id", 1)])
        collection.create_index([("guild_id", 1)])
        logger.debug("[rag_metrics] Indexes created with TTL")
    except Exception as e:
        logger.warning(f"[rag_metrics] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[rag_metrics] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[rag_metrics] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[rag_metrics] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[rag_metrics] Error initializing: {e}")
        return False


class RAGMetrics(CollectionModule):
    collection_name = "rag_metrics"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not RAGMetrics.collection_name:
            raise RuntimeError("collection_name not set for RAGMetrics")
        return get_database()[RAGMetrics.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
