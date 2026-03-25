"""
Random Content Items Database - Dedicated collection for random message content.

This module manages the `random_content_items` collection, separating content
from configuration. Supports system-wide and guild-specific random content.

Follows the CollectionModule pattern for foolproof database architecture.
"""

from typing import Optional, Dict, Any, TYPE_CHECKING, List
from datetime import datetime
from dataclasses import dataclass

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


@dataclass
class RandomContentItem:
    """Typed representation of a random content item."""
    _id: Optional[str] = None
    scope: str = "guild"
    guild_id: Optional[int] = None
    source_type: str = "manual"
    category: str = "general"
    content_text: str = ""
    content_prompt: Optional[str] = None
    status: str = "active"
    weight: float = 1.0
    created_by: str = "system"
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    approved: bool = True
    approved_by: Optional[str] = None


class RandomContentItems(CollectionModule):
    """Collection module for random_content_items - follows foolproof pattern."""
    
    collection_name = "random_content_items"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get random_content_items collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not RandomContentItems.collection_name:
            raise RuntimeError("collection_name not set for RandomContentItems")
        db = get_database()
        return db[RandomContentItems.collection_name]
    
    @staticmethod
    def ensure_indexes():
        """Create all indexes for efficient querying."""
        try:
            collection = RandomContentItems.get_collection()
            
            # Guild-based queries (most common)
            collection.create_index([("guild_id", 1), ("scope", 1), ("status", 1)])
            
            # System content queries
            collection.create_index([("scope", 1), ("status", 1)])
            
            # Category filtering
            collection.create_index([("category", 1)])
            
            # Source type filtering
            collection.create_index([("source_type", 1)])
            
            # Creation time (for sorting/analytics)
            collection.create_index([("created_at", -1)])
            
            if logger:
                logger.debug("[RandomContentItems] Indexes created")
            
        except Exception as e:
            if logger:
                logger.warning(f"[RandomContentItems] Error creating indexes: {e}")
    
    @staticmethod
    def seed_defaults() -> bool:
        """Seed the collection with system-wide default random content."""
        try:
            collection = RandomContentItems.get_collection()
            
            # Check if system defaults already exist
            existing_count = collection.count_documents({"scope": "system"})
            if existing_count > 0:
                if logger:
                    logger.debug(f"[RandomContentItems] System defaults already seeded ({existing_count} items)")
                return True
            
            # System default messages
            system_defaults = [
                {
                    "scope": "system",
                    "guild_id": None,
                    "source_type": "system",
                    "category": "inspiration",
                    "content": {
                        "text": "🌟 Keep creating! Every idea you share adds color to the world.",
                        "prompt": None
                    },
                    "status": "active",
                    "weight": 1.0,
                    "created_by": "system",
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "usage_count": 0,
                    "audit": {"approved": True, "approved_by": "system"}
                },
                {
                    "scope": "system",
                    "guild_id": None,
                    "source_type": "system",
                    "category": "inspiration",
                    "content": {
                        "text": "✨ Every masterpiece starts with a single stroke. What will yours be today?",
                        "prompt": None
                    },
                    "status": "active",
                    "weight": 1.0,
                    "created_by": "system",
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "usage_count": 0,
                    "audit": {"approved": True, "approved_by": "system"}
                },
                {
                    "scope": "system",
                    "guild_id": None,
                    "source_type": "system",
                    "category": "creative",
                    "content": {
                        "text": "🎨 Your unique voice matters. Don't let anyone silence your creativity!",
                        "prompt": None
                    },
                    "status": "active",
                    "weight": 1.0,
                    "created_by": "system",
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "usage_count": 0,
                    "audit": {"approved": True, "approved_by": "system"}
                },
                {
                    "scope": "system",
                    "guild_id": None,
                    "source_type": "system",
                    "category": "fun_fact",
                    "content": {
                        "text": "💡 Fun fact: The average person spends 6 months waiting for red lights!",
                        "prompt": None
                    },
                    "status": "active",
                    "weight": 1.0,
                    "created_by": "system",
                    "created_at": datetime.utcnow(),
                    "last_used_at": None,
                    "usage_count": 0,
                    "audit": {"approved": True, "approved_by": "system"}
                }
            ]
            
            collection.insert_many(system_defaults)
            
            if logger:
                logger.info(f"[RandomContentItems] ✓ Seeded {len(system_defaults)} system defaults")
            
            return True
            
        except Exception as e:
            if logger:
                logger.error(f"[RandomContentItems] Error seeding defaults: {e}")
            return False
    
    @staticmethod
    def initialize_collection() -> bool:
        """Initialize the random_content_items collection for use."""
        try:
            RandomContentItems.ensure_indexes()
            RandomContentItems.seed_defaults()
            
            if logger:
                logger.debug("[RandomContentItems] Collection initialized")
            
            return True
            
        except Exception as e:
            if logger:
                logger.error(f"[RandomContentItems] Error initializing collection: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_item(
    guild_id: int,
    source_type: str,
    category: str,
    content_text: str = "",
    content_prompt: Optional[str] = None,
    created_by: str = "system",
    weight: float = 1.0,
    scope: str = "guild"
) -> Optional[str]:
    """Create a new random content item."""
    try:
        collection = RandomContentItems.get_collection()
        
        doc = {
            "scope": scope,
            "guild_id": guild_id if scope in ("guild", "user") else None,
            "source_type": source_type,
            "category": category,
            "content": {"text": content_text, "prompt": content_prompt},
            "status": "active",
            "weight": weight,
            "created_by": created_by,
            "created_at": datetime.utcnow(),
            "last_used_at": None,
            "usage_count": 0,
            "audit": {"approved": True, "approved_by": created_by}
        }
        
        result = collection.insert_one(doc)
        return str(result.inserted_id)
        
    except Exception as e:
        if logger:
            logger.error(f"[RandomContentItems] Error creating item: {e}")
        return None


def get_guild_content_pool(
    guild_id: int,
    include_system: bool = True,
    enabled_only: bool = True,
    source_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Get content pool for a guild."""
    try:
        collection = RandomContentItems.get_collection()
        
        filters = []
        filters.append({"guild_id": guild_id, "scope": "guild"})
        
        if include_system:
            filters.append({"scope": "system"})
        
        query: Dict[str, Any] = {"$or": filters}
        
        if enabled_only:
            query["status"] = "active"
        
        if source_types:
            query["source_type"] = {"$in": source_types}
        
        items = list(collection.find(query))
        
        if logger:
            logger.debug(f"[RandomContentItems] Retrieved {len(items)} items for guild {guild_id}")
        
        return items
        
    except Exception as e:
        if logger:
            logger.error(f"[RandomContentItems] Error getting pool: {e}")
        return []


def get_item_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    """Get a single content item by ID."""
    try:
        from bson import ObjectId
        collection = RandomContentItems.get_collection()
        
        item = collection.find_one({"_id": ObjectId(item_id)})
        return item
        
    except Exception as e:
        if logger:
            logger.error(f"[RandomContentItems] Error getting item {item_id}: {e}")
        return None


def update_item(item_id: str, updates: Dict[str, Any]) -> bool:
    """Update a content item."""
    try:
        from bson import ObjectId
        collection = RandomContentItems.get_collection()
        
        updates["updated_at"] = datetime.utcnow()
        
        result = collection.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": updates}
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        if logger:
            logger.error(f"[RandomContentItems] Error updating item {item_id}: {e}")
        return False


def delete_item(item_id: str) -> bool:
    """Delete a content item."""
    try:
        from bson import ObjectId
        collection = RandomContentItems.get_collection()
        
        result = collection.delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0
        
    except Exception as e:
        if logger:
            logger.error(f"[RandomContentItems] Error deleting item {item_id}: {e}")
        return False


def record_usage(item_id: str) -> bool:
    """Record that an item was used."""
    try:
        from bson import ObjectId
        collection = RandomContentItems.get_collection()
        
        result = collection.update_one(
            {"_id": ObjectId(item_id)},
            {
                "$set": {"last_used_at": datetime.utcnow()},
                "$inc": {"usage_count": 1}
            }
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        if logger:
            logger.error(f"[RandomContentItems] Error recording usage: {e}")
        return False
