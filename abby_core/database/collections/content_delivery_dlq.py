"""
Content Delivery DLQ Collection Module

Purpose: Dead letter queue for failed content deliveries
Schema: Failed delivery records with retry information
Indexes: guild_id, status, created_at

Manages:
- Failed delivery tracking
- Retry queue management
- Delivery failure analysis
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
    return get_database()["content_delivery_dlq"]


def ensure_indexes():
    try:
        collection = get_collection()
        collection.create_index([("guild_id", 1)])
        collection.create_index([("status", 1)])
        collection.create_index([("created_at", -1)])
        logger.debug("[content_delivery_dlq] Indexes created")
    except Exception as e:
        logger.warning(f"[content_delivery_dlq] Error creating indexes: {e}")


def seed_defaults() -> bool:
    try:
        logger.debug("[content_delivery_dlq] No defaults to seed")
        return True
    except Exception as e:
        logger.error(f"[content_delivery_dlq] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[content_delivery_dlq] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[content_delivery_dlq] Error initializing: {e}")
        return False


class ContentDeliveryDLQ(CollectionModule):
    collection_name = "content_delivery_dlq"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not ContentDeliveryDLQ.collection_name:
            raise RuntimeError("collection_name not set for ContentDeliveryDLQ")
        return get_database()[ContentDeliveryDLQ.collection_name]
    
    @staticmethod
    def ensure_indexes():
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        return initialize_collection()
