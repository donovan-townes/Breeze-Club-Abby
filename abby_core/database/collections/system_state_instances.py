"""
System State Instances Collection Module

Purpose: Runtime instances of system state objects
Schema: State snapshots with version tracking
Indexes: state_id (unique), state_type, created_at

Manages:
- Active state instances
- State version tracking
- Instance lifecycle
- Concurrent state management
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
    """Get system_state_instances collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["system_state_instances"]


def ensure_indexes():
    """Create indexes for system_state_instances collection."""
    try:
        collection = get_collection()

        collection.create_index([("state_id", 1)], unique=True)
        collection.create_index([("state_type", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("version", -1)])

        logger.debug("[system_state_instances] Indexes created")

    except Exception as e:
        logger.warning(f"[system_state_instances] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[system_state_instances] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[system_state_instances] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize system_state_instances collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[system_state_instances] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[system_state_instances] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class SystemStateInstances(CollectionModule):
    """Collection module for system_state_instances - follows foolproof pattern."""
    
    collection_name = "system_state_instances"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get system_state_instances collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not SystemStateInstances.collection_name:
            raise RuntimeError("collection_name not set for SystemStateInstances")
        db = get_database()
        return db[SystemStateInstances.collection_name]
    
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
