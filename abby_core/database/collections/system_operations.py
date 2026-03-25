"""
System Operations Collection Module

Purpose: Track all system operations and state changes
Schema: See schemas.py (SystemOperationSchema)
Indexes: operation_id, operation_type, created_at, status

Manages:
- State activation operations
- XP reset operations
- System maintenance operations
- Operation audit trail
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class OperationStatus(str, Enum):
    """Operation status types."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get system_operations collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["system_operations"]


def ensure_indexes():
    """Create indexes for system_operations collection."""
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
            "operation_id_1",
            [("operation_id", 1)],
            {"operation_id": {"$type": "string"}},
        )
        collection.create_index([("operation_type", 1)])
        collection.create_index([("status", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("guild_id", 1), ("created_at", -1)])
        collection.create_index([("initiated_by", 1)])

        logger.debug("[system_operations] Indexes created")

    except Exception as e:
        logger.warning(f"[system_operations] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[system_operations] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[system_operations] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize system_operations collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[system_operations] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[system_operations] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_operation(
    operation_id: str,
    operation_type: str,
    guild_id: Optional[int] = None,
    initiated_by: Optional[str] = None,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create a new system operation."""
    try:
        collection = get_collection()
        
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "guild_id": guild_id,
            "initiated_by": initiated_by,
            "description": description,
            "status": OperationStatus.PENDING,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
        }
        
        collection.insert_one(operation)
        logger.debug(f"[system_operations] Created operation {operation_id}")
        return True
        
    except Exception as e:
        logger.error(f"[system_operations] Error creating operation: {e}")
        return False


def get_operation(operation_id: str) -> Optional[Dict[str, Any]]:
    """Get operation by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"operation_id": operation_id})
    except Exception as e:
        logger.error(f"[system_operations] Error getting operation: {e}")
        return None


def get_operations_by_type(
    operation_type: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get operations by type."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"operation_type": operation_type}
        ).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[system_operations] Error getting operations: {e}")
        return []


def get_guild_operations(
    guild_id: int,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get operations for a specific guild."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"guild_id": guild_id}
        ).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[system_operations] Error getting guild operations: {e}")
        return []


def update_operation_status(
    operation_id: str,
    status: str,
    error_message: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None
) -> bool:
    """Update operation status."""
    try:
        collection = get_collection()
        
        update_dict: Dict[str, Any] = {
            "status": status,
            "updated_at": datetime.utcnow(),
        }
        
        if status == OperationStatus.IN_PROGRESS and not error_message:
            update_dict["started_at"] = datetime.utcnow()
        elif status == OperationStatus.COMPLETED:
            update_dict["completed_at"] = datetime.utcnow()
        elif status == OperationStatus.FAILED and error_message:
            update_dict["error_message"] = error_message
        
        if metadata_updates:
            for key, value in metadata_updates.items():
                update_dict[f"metadata.{key}"] = value
        
        result = collection.update_one(
            {"operation_id": operation_id},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[system_operations] Operation {operation_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[system_operations] Error updating operation: {e}")
        return False


def mark_operation_completed(
    operation_id: str,
    metadata_updates: Optional[Dict[str, Any]] = None
) -> bool:
    """Mark operation as completed."""
    return update_operation_status(
        operation_id,
        OperationStatus.COMPLETED,
        metadata_updates=metadata_updates
    )


def mark_operation_failed(
    operation_id: str,
    error: str,
    metadata_updates: Optional[Dict[str, Any]] = None
) -> bool:
    """Mark operation as failed."""
    return update_operation_status(
        operation_id,
        OperationStatus.FAILED,
        error_message=error,
        metadata_updates=metadata_updates
    )


def get_pending_operations() -> List[Dict[str, Any]]:
    """Get all pending operations."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"status": OperationStatus.PENDING}
        ).sort("created_at", 1))
    except Exception as e:
        logger.error(f"[system_operations] Error getting pending operations: {e}")
        return []


def get_failed_operations(limit: int = 50) -> List[Dict[str, Any]]:
    """Get failed operations for investigation."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"status": OperationStatus.FAILED}
        ).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[system_operations] Error getting failed operations: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class SystemOperations(CollectionModule):
    """Collection module for system_operations - follows foolproof pattern."""
    
    collection_name = "system_operations"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get system_operations collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not SystemOperations.collection_name:
            raise RuntimeError("collection_name not set for SystemOperations")
        db = get_database()
        return db[SystemOperations.collection_name]
    
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
