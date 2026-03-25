"""
System State Collection Module

Purpose: Global system state and configuration
Schema: See schemas.py (SystemStateSchema)
Indexes: key, state_type, updated_at

Manages:
- Global system settings
- Runtime state variables
- Feature flags
- System health metrics
"""

from typing import Optional, Dict, Any, TYPE_CHECKING, List
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get system_state collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["system_state"]


def ensure_indexes():
    """Create indexes for system_state collection."""
    try:
        collection = get_collection()

        collection.create_index([("key", 1)], unique=True)
        collection.create_index([("state_type", 1)])
        collection.create_index([("updated_at", -1)])
        collection.create_index([("is_active", 1)])

        logger.debug("[system_state] Indexes created")

    except Exception as e:
        logger.warning(f"[system_state] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default system state."""
    try:
        collection = get_collection()
        
        # Check if already seeded
        existing = collection.count_documents({})
        if existing > 0:
            logger.debug("[system_state] Defaults already seeded")
            return True

        defaults = [
            {
                "key": "system_status",
                "state_type": "status",
                "value": "running",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            {
                "key": "maintenance_mode",
                "state_type": "feature_flag",
                "value": False,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        ]
        
        collection.insert_many(defaults)
        logger.debug("[system_state] Default state seeded")
        return True
        
    except Exception as e:
        logger.error(f"[system_state] Error seeding defaults: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize system_state collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[system_state] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[system_state] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def get_state(key: str) -> Optional[Dict[str, Any]]:
    """Get system state by key."""
    try:
        collection = get_collection()
        return collection.find_one({"key": key})
    except Exception as e:
        logger.error(f"[system_state] Error getting state: {e}")
        return None


def get_state_value(key: str, default: Any = None) -> Any:
    """Get state value directly."""
    try:
        state = get_state(key)
        return state.get("value", default) if state else default
    except Exception as e:
        logger.error(f"[system_state] Error getting value: {e}")
        return default


def set_state(
    key: str,
    value: Any,
    state_type: str = "custom"
) -> bool:
    """Set or update system state."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"key": key},
            {
                "$set": {
                    "value": value,
                    "state_type": state_type,
                    "is_active": True,
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True
        )
        
        logger.debug(f"[system_state] Set state {key}={value}")
        return True
        
    except Exception as e:
        logger.error(f"[system_state] Error setting state: {e}")
        return False


def delete_state(key: str) -> bool:
    """Delete system state."""
    try:
        collection = get_collection()
        
        result = collection.delete_one({"key": key})
        
        if result.deleted_count == 0:
            logger.warning(f"[system_state] State {key} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[system_state] Error deleting state: {e}")
        return False


def is_maintenance_mode() -> bool:
    """Check if system is in maintenance mode."""
    return get_state_value("maintenance_mode", False)


def set_maintenance_mode(enabled: bool) -> bool:
    """Set maintenance mode."""
    return set_state("maintenance_mode", enabled, "feature_flag")


def get_system_status() -> str:
    """Get overall system status."""
    return get_state_value("system_status", "unknown")


def set_system_status(status: str) -> bool:
    """Set system status."""
    return set_state("system_status", status, "status")


# ═══════════════════════════════════════════════════════════════
# STATE RESOLVER HELPERS (for llm/system_state_resolver.py)
# ═══════════════════════════════════════════════════════════════

def get_active_states(
    now: Optional[datetime] = None,
    scope: str = "global"
) -> List[Dict[str, Any]]:
    """Get active states at a given time.
    
    Args:
        now: Timestamp to check (default: now)
        scope: State scope filter (default: global)
    
    Returns:
        List of active state documents
    """
    try:
        collection = get_collection()
        ts = now or datetime.utcnow()
        
        query = {
            "active": True,
            "scope": scope,
            "start_at": {"$lte": ts},
            "end_at": {"$gte": ts},
        }
        
        return list(collection.find(query))
    except Exception as e:
        logger.error(f"[system_state] Error getting active states: {e}")
        return []


def get_states_by_ids(state_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Get state definitions by IDs.
    
    Args:
        state_ids: List of state IDs to fetch
    
    Returns:
        Dict mapping state_id to state document
    """
    if not state_ids:
        return {}
    
    try:
        collection = get_collection()
        docs = list(collection.find({"state_id": {"$in": state_ids}}))
        return {doc.get("state_id"): doc for doc in docs if doc.get("state_id")}
    except Exception as e:
        logger.error(f"[system_state] Error getting states by IDs: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class SystemState(CollectionModule):
    """Collection module for system_state - follows foolproof pattern."""
    
    collection_name = "system_state"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get system_state collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not SystemState.collection_name:
            raise RuntimeError("collection_name not set for SystemState")
        db = get_database()
        return db[SystemState.collection_name]
    
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
