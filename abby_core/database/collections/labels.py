"""
Labels Collection - Dynamic Label/Distributor Management

PURPOSE: Maintain dynamic list of accepted labels and distributors for music releases.
Label admins can add new labels without code changes.

STRUCTURE:
{
  "_id": ObjectId,
  "label_id": str,              # Unique identifier (cool_breeze, silk_music, etc.)
  "display_name": str,          # "🎵 Cool Breeze"
  "description": str,           # "Primary label"
  "is_active": bool,            # Enable/disable without deletion
  "created_by": str,            # Admin user_id who created it
  "created_at": datetime,
  "updated_at": datetime
}

BUILTIN LABELS (Seeds):
- cool_breeze: Cool Breeze (primary)
- self_released: Self-Released (artist independent)
- royalty_free: Royalty-free tracks
- wip: Work in progress / upcoming
- other: Other distributors (catch-all)

ADMIN OPERATIONS:
- add_label(label_id, display_name, description)
- update_label(label_id, **updates)
- deactivate_label(label_id)  # Soft delete
- get_active_labels()
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get labels collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["labels"]


def ensure_indexes():
    """Create indexes for labels collection."""
    try:
        collection = get_collection()
        
        # Unique label IDs
        try:
            collection.create_index([("label_id", 1)], unique=True)
        except Exception as e:
            if "already exists" not in str(e):
                logger.debug(f"[labels] label_id index: {e}")
        
        # Query by active status
        collection.create_index([("is_active", 1)])
        
        # Temporal queries
        collection.create_index([("created_at", -1)])
        
        logger.debug("[labels] Indexes created")
        
    except Exception as e:
        logger.warning(f"[labels] Error creating indexes: {e}")


def seed_builtin_labels() -> bool:
    """Seed default labels if collection is empty."""
    try:
        collection = get_collection()
        
        # Only seed if empty
        if collection.count_documents({}) > 0:
            logger.debug("[labels] Collection already seeded")
            return True
        
        builtin_labels = [
            {
                "label_id": "cool_breeze",
                "display_name": "🎵 Cool Breeze",
                "description": "Primary label",
                "is_active": True,
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "label_id": "self_released",
                "display_name": "👤 Self-Released",
                "description": "Independent artist release",
                "is_active": True,
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "label_id": "royalty_free",
                "display_name": "🆓 Royalty Free",
                "description": "Royalty-free music",
                "is_active": True,
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "label_id": "wip",
                "display_name": "🚧 Work in Progress",
                "description": "Upcoming or work in progress track",
                "is_active": True,
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "label_id": "other",
                "display_name": "📌 Other Distributor",
                "description": "Any other label or distributor",
                "is_active": True,
                "created_by": "system",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        result = collection.insert_many(builtin_labels)
        logger.info(f"[labels] Seeded {len(result.inserted_ids)} builtin labels")
        return True
        
    except Exception as e:
        logger.error(f"[labels] Error seeding builtin labels: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize labels collection."""
    try:
        ensure_indexes()
        seed_builtin_labels()
        logger.debug("[labels] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[labels] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# LABEL OPERATIONS
# ═══════════════════════════════════════════════════════════════

def get_active_labels() -> List[Dict[str, Any]]:
    """Get all active labels for selection in release manager."""
    try:
        collection = get_collection()
        labels = list(collection.find(
            {"is_active": True},
            sort=[("created_at", 1)]
        ))
        return labels
    except Exception as e:
        logger.error(f"[labels] Error getting active labels: {e}")
        return []


def get_label(label_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific label by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"label_id": label_id})
    except Exception as e:
        logger.error(f"[labels] Error getting label {label_id}: {e}")
        return None


def add_label(label_id: str, display_name: str, description: str, 
              created_by: str = "admin") -> bool:
    """Add a new label - ADMIN ONLY.
    
    Args:
        label_id: Unique identifier (e.g., "silk_music")
        display_name: Display name with emoji (e.g., "🎧 Silk Music")
        description: Short description
        created_by: Admin user who added this label
        
    Returns:
        True if successful
    """
    try:
        collection = get_collection()
        
        # Check if already exists
        if collection.find_one({"label_id": label_id}):
            logger.warning(f"[labels] Label {label_id} already exists")
            return False
        
        label_doc = {
            "label_id": label_id,
            "display_name": display_name,
            "description": description,
            "is_active": True,
            "created_by": created_by,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = collection.insert_one(label_doc)
        logger.info(f"[labels] Added label: {label_id}")
        return True
        
    except Exception as e:
        logger.error(f"[labels] Error adding label {label_id}: {e}")
        return False


def update_label(label_id: str, **updates) -> bool:
    """Update label metadata - ADMIN ONLY.
    
    Args:
        label_id: Label to update
        **updates: Fields to update (display_name, description, is_active)
        
    Returns:
        True if successful
    """
    try:
        collection = get_collection()
        
        updates["updated_at"] = datetime.utcnow()
        
        result = collection.update_one(
            {"label_id": label_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            logger.info(f"[labels] Updated label: {label_id}")
            return True
        else:
            logger.warning(f"[labels] Label not found: {label_id}")
            return False
            
    except Exception as e:
        logger.error(f"[labels] Error updating label {label_id}: {e}")
        return False


def deactivate_label(label_id: str) -> bool:
    """Deactivate label (soft delete) - ADMIN ONLY.
    
    Prevents new releases from using this label, but doesn't delete existing ones.
    """
    return update_label(label_id, is_active=False)


def reactivate_label(label_id: str) -> bool:
    """Reactivate a deactivated label - ADMIN ONLY."""
    return update_label(label_id, is_active=True)
