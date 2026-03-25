"""
Content Delivery Metrics Collection Module

Purpose: Metrics for content delivery lifecycle tracking
Schema: Delivery metrics with TTL (90 days)
Indexes: guild_id, timestamp

Manages:
- Delivery performance metrics
- Timing and success tracking
- Historical metric data (auto-expires)
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
    return get_database()["content_delivery_metrics"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("guild_id", 1)])
        collection.create_index([("timestamp", -1)])
        # TTL index: auto-delete metrics after 90 days
        collection.create_index([("timestamp", 1)], expireAfterSeconds=7776000)
        logger.debug("[content_delivery_metrics] Indexes created (with 90-day TTL)")
    except Exception as e:
        logger.warning(f"[content_delivery_metrics] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[content_delivery_metrics] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[content_delivery_metrics] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[content_delivery_metrics] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[content_delivery_metrics] Error initializing: {e}")
        return False


class ContentDeliveryMetrics(CollectionModule):
    collection_name = "content_delivery_metrics"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not ContentDeliveryMetrics.collection_name:
            raise RuntimeError("collection_name not set for ContentDeliveryMetrics")
        return get_database()[ContentDeliveryMetrics.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
