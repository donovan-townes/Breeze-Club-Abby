"""
Operation Snapshots Collection Module

Purpose: Store snapshots of state before and after operations
Schema: See schemas.py (OperationSnapshotSchema)
Indexes: operation_id, snapshot_type, created_at

Manages:
- Pre-operation snapshots (before state)
- Post-operation snapshots (after state)
- Operation rollback support
- State reconstruction for debugging
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


class SnapshotType(str, Enum):
    """Snapshot types."""
    PRE_OPERATION = "pre_operation"
    POST_OPERATION = "post_operation"
    ROLLBACK_TARGET = "rollback_target"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get operation_snapshots collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["operation_snapshots"]


def ensure_indexes():
    """Create indexes for operation_snapshots collection."""
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
            "snapshot_id_1",
            [("snapshot_id", 1)],
            {"snapshot_id": {"$type": "string"}},
        )
        collection.create_index([("operation_id", 1)])
        collection.create_index([("snapshot_type", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("collection_name", 1)])

        logger.debug("[operation_snapshots] Indexes created")

    except Exception as e:
        logger.warning(f"[operation_snapshots] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[operation_snapshots] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[operation_snapshots] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize operation_snapshots collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[operation_snapshots] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[operation_snapshots] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_snapshot(
    snapshot_id: str,
    operation_id: str,
    snapshot_type: str,
    collection_name: str,
    document_id: Any,
    document_state: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create operation snapshot."""
    try:
        collection = get_collection()
        
        snapshot = {
            "snapshot_id": snapshot_id,
            "operation_id": operation_id,
            "snapshot_type": snapshot_type,
            "collection_name": collection_name,
            "document_id": document_id,
            "document_state": document_state,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
        }
        
        collection.insert_one(snapshot)
        logger.debug(f"[operation_snapshots] Created snapshot {snapshot_id}")
        return True
        
    except Exception as e:
        logger.error(f"[operation_snapshots] Error creating snapshot: {e}")
        return False


def get_snapshot(snapshot_id: str) -> Optional[Dict[str, Any]]:
    """Get snapshot by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"snapshot_id": snapshot_id})
    except Exception as e:
        logger.error(f"[operation_snapshots] Error getting snapshot: {e}")
        return None


def get_operation_snapshots(operation_id: str) -> List[Dict[str, Any]]:
    """Get all snapshots for an operation."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"operation_id": operation_id}
        ).sort("created_at", 1))
    except Exception as e:
        logger.error(f"[operation_snapshots] Error getting operation snapshots: {e}")
        return []


def get_pre_operation_snapshot(operation_id: str) -> Optional[Dict[str, Any]]:
    """Get pre-operation snapshot."""
    try:
        collection = get_collection()
        return collection.find_one({
            "operation_id": operation_id,
            "snapshot_type": SnapshotType.PRE_OPERATION
        })
    except Exception as e:
        logger.error(f"[operation_snapshots] Error getting pre-operation snapshot: {e}")
        return None


def get_post_operation_snapshot(operation_id: str) -> Optional[Dict[str, Any]]:
    """Get post-operation snapshot."""
    try:
        collection = get_collection()
        return collection.find_one({
            "operation_id": operation_id,
            "snapshot_type": SnapshotType.POST_OPERATION
        })
    except Exception as e:
        logger.error(f"[operation_snapshots] Error getting post-operation snapshot: {e}")
        return None


def get_document_history(
    collection_name: str,
    document_id: Any,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get snapshot history for a specific document."""
    try:
        collection = get_collection()
        return list(collection.find({
            "collection_name": collection_name,
            "document_id": document_id
        }).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[operation_snapshots] Error getting document history: {e}")
        return []


def delete_old_snapshots(days_old: int = 30) -> int:
    """Delete snapshots older than specified days."""
    try:
        collection = get_collection()
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        result = collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })
        
        logger.debug(f"[operation_snapshots] Deleted {result.deleted_count} old snapshots")
        return result.deleted_count
        
    except Exception as e:
        logger.error(f"[operation_snapshots] Error deleting old snapshots: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class OperationSnapshots(CollectionModule):
    """Collection module for operation_snapshots - follows foolproof pattern."""
    
    collection_name = "operation_snapshots"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get operation_snapshots collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not OperationSnapshots.collection_name:
            raise RuntimeError("collection_name not set for OperationSnapshots")
        db = get_database()
        return db[OperationSnapshots.collection_name]
    
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
