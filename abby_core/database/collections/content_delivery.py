"""
Content Delivery Collection Module

Purpose: Scheduled announcements and content delivery
Schema: See schemas.py (ContentDeliverySchema)
Indexes: guild_id, status, scheduled_at

Manages:
- Scheduled announcements
- Content delivery lifecycle
- Execution history
- Retry logic for failed deliveries
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get content_delivery_items collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["content_delivery_items"]


def ensure_indexes():
    """Create indexes for content_delivery_items collection."""
    try:
        collection = get_collection()

        def _ensure_unique_partial_index(name: str, key: list[tuple[str, int]], filter_expr: Dict[str, Any]) -> None:
            existing = next((idx for idx in collection.list_indexes() if idx.get("name") == name), None)
            if existing:
                existing_key = dict(existing.get("key", {}))
                if existing_key == dict(key):
                    if existing.get("partialFilterExpression") != filter_expr:
                        collection.drop_index(name)
            collection.create_index(
                key,
                unique=True,
                partialFilterExpression=filter_expr,
                name=name,
            )

        _ensure_unique_partial_index(
            "delivery_id_1",
            [("delivery_id", 1)],
            {"delivery_id": {"$type": "string"}},
        )
        collection.create_index([("guild_id", 1), ("status", 1)])
        collection.create_index([("scheduled_at", 1)])
        collection.create_index([("status", 1), ("scheduled_at", 1)])
        collection.create_index([("created_at", -1)])

        logger.debug("[content_delivery] Indexes created")

    except Exception as e:
        logger.warning(f"[content_delivery] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[content_delivery] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[content_delivery] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize content_delivery_items collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[content_delivery] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[content_delivery] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_delivery(
    delivery_id: str,
    guild_id: int,
    content: str,
    scheduled_at: datetime,
    channel_id: Optional[int] = None
) -> bool:
    """Create scheduled content delivery."""
    try:
        collection = get_collection()
        
        delivery = {
            "delivery_id": delivery_id,
            "guild_id": guild_id,
            "content": content,
            "scheduled_at": scheduled_at,
            "channel_id": channel_id,
            "status": "scheduled",
            "attempts": 0,
            "last_attempt": None,
            "error_message": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        collection.insert_one(delivery)
        logger.debug(f"[content_delivery] Created delivery {delivery_id}")
        return True
        
    except Exception as e:
        logger.error(f"[content_delivery] Error creating delivery: {e}")
        return False


def get_delivery(delivery_id: str) -> Optional[Dict[str, Any]]:
    """Get delivery by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"delivery_id": delivery_id})
    except Exception as e:
        logger.error(f"[content_delivery] Error getting delivery: {e}")
        return None


def get_pending_deliveries(guild_id: int) -> List[Dict[str, Any]]:
    """Get pending deliveries for guild."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"guild_id": guild_id, "status": "scheduled"},
            sort=[("scheduled_at", 1)]
        ))
    except Exception as e:
        logger.error(f"[content_delivery] Error getting pending deliveries: {e}")
        return []


def mark_delivered(delivery_id: str) -> bool:
    """Mark delivery as sent."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"delivery_id": delivery_id},
            {
                "$set": {
                    "status": "delivered",
                    "last_attempt": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[content_delivery] Delivery {delivery_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[content_delivery] Error marking delivered: {e}")
        return False


def mark_failed(delivery_id: str, error: str) -> bool:
    """Mark delivery as failed."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"delivery_id": delivery_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": error,
                    "last_attempt": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                "$inc": {"attempts": 1}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[content_delivery] Delivery {delivery_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[content_delivery] Error marking failed: {e}")
        return False


def delete_delivery(delivery_id: str) -> bool:
    """Delete delivery."""
    try:
        collection = get_collection()
        
        result = collection.delete_one({"delivery_id": delivery_id})
        
        if result.deleted_count == 0:
            logger.warning(f"[content_delivery] Delivery {delivery_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[content_delivery] Error deleting delivery: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class ContentDelivery(CollectionModule):
    """Collection module for content_delivery_items - follows foolproof pattern."""
    
    collection_name = "content_delivery_items"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get content_delivery_items collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not ContentDelivery.collection_name:
            raise RuntimeError("collection_name not set for ContentDelivery")
        db = get_database()
        return db[ContentDelivery.collection_name]
    
    @staticmethod
    def ensure_indexes():
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
