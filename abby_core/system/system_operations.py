"""
System Operations: Durable state mutations with rollback support.

This layer manages all destructive operations (XP resets, level adjustments, etc.)
with full audit trail, dry-run support, and rollback capability.

Design:
- All mutations create an operation record FIRST
- Mutations are idempotent (checked via last_applied_event_id)
- Snapshots capture "before" state for rollback
- Status machine: prepared → applied → rolled_back
- Effects are tracked in effects_ref (points to snapshot or delta docs)

Key Concepts:
- op_key: Idempotency key (unique operation identifier)
- effects_applied: Boolean flag (prevents double-fire)
- dry_run: Boolean flag (records intent, doesn't mutate)
- snapshot_id: Reference to pre-mutation snapshot (for rollback)
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import uuid
from bson import ObjectId
from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


class OperationStatus(str, Enum):
    """Operation lifecycle states"""
    PREPARED = "prepared"      # Intent recorded, nothing mutated yet
    APPLIED = "applied"        # Mutations completed
    ROLLED_BACK = "rolled_back"  # Mutations reversed
    FAILED = "failed"          # Mutations failed, needs manual review
    PARTIAL = "partial"        # Some mutations succeeded, some failed


class OperationType(str, Enum):
    """Types of operations that can be performed"""
    XP_SEASON_RESET = "xp_season_reset"
    XP_ADJUSTMENT = "xp_adjustment"
    LEVEL_RESET = "level_reset"
    LEVEL_ADJUSTMENT = "level_adjustment"


# ==================== COLLECTION ACCESS ====================

def get_system_operations_collection():
    """Get the system_operations collection from configured database."""
    db = get_database()
    return db["system_operations"]


def get_operation_snapshots_collection():
    """Get the operation_snapshots collection (pre-mutation state)."""
    db = get_database()
    return db["operation_snapshots"]


# ==================== OPERATION CREATION ====================

def create_operation(
    op_type: str,
    op_key: str,
    scope: str,  # "system" | "guild" | "user"
    scope_id: Optional[str] = None,  # guild_id | user_id (if not system)
    affected_count: int = 0,
    dry_run: bool = False,
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Create a new operation record (Phase A: Freeze Intent).
    
    This records the intent to perform an operation BEFORE any mutations occur.
    Multiple calls with the same op_key are idempotent.
    
    Args:
        op_type: Operation type (xp_season_reset, etc.)
        op_key: Unique idempotency key (e.g., "season_reset:winter-2026:1234567890")
        scope: Operation scope (system | guild | user)
        scope_id: Guild ID or user ID (if applicable)
        affected_count: Estimated number of users affected
        dry_run: If True, record intent but don't mutate
        operator_id: Discord user ID who triggered this
        reason: Operator-provided reason
        metadata: Additional operation context
    
    Returns:
        str: Operation ID, or None if creation failed
    """
    collection = get_system_operations_collection()
    
    # Check for existing operation with same key
    existing = collection.find_one({"op_key": op_key})
    if existing:
        logger.info(f"[🔄] Operation already exists: {op_key}, returning existing ID")
        return str(existing["_id"])
    
    operation = {
        "op_type": op_type,
        "op_key": op_key,
        "scope": scope,
        "scope_id": scope_id,
        
        # Tracking
        "status": OperationStatus.PREPARED.value,
        "dry_run": dry_run,
        "operator_id": operator_id,
        "reason": reason,
        
        # Intent
        "created_at": datetime.utcnow(),
        "prepared_at": datetime.utcnow(),
        "affected_count": affected_count,
        
        # Lifecycle
        "applied_at": None,
        "rolled_back_at": None,
        
        # References
        "snapshot_id": None,  # Set in Phase B
        "event_id": None,  # system_events reference
        "effects_applied": False,  # Prevents double-fire
        "last_mutation_job_id": None,
        
        # Results
        "success_count": 0,
        "failure_count": 0,
        "errors": [],
        
        # Metadata
        "metadata": metadata or {},
    }
    
    try:
        result = collection.insert_one(operation)
        op_id = str(result.inserted_id)
        logger.info(f"[📋] Created operation: {op_type} (ID: {op_id}, key: {op_key}, dry_run={dry_run})")
        return op_id
    except Exception as e:
        logger.error(f"[❌] Failed to create operation: {e}")
        return None


# ==================== SNAPSHOT CREATION (Phase B) ====================

def create_snapshot(
    operation_id: str,
    snapshot_type: str,  # "pre_xp_reset", "pre_level_adjustment", etc.
    collections_to_snapshot: List[str],  # ["user_xp", "user_level", etc.]
    query_filter: Optional[Dict[str, Any]] = None,  # Filter for what to snapshot
) -> Optional[str]:
    """Create a pre-mutation snapshot (Phase B: Snapshot Anchor).
    
    This captures the "before" state of affected data for rollback capability.
    Snapshots are immutable once created.
    
    Args:
        operation_id: The operation this snapshot belongs to
        snapshot_type: Type of snapshot (e.g., "pre_xp_reset")
        collections_to_snapshot: List of collection names to snapshot
        query_filter: MongoDB query to filter what gets snapshotted
    
    Returns:
        str: Snapshot ID, or None if creation failed
    """
    db = get_database()
    snapshot_collection = get_operation_snapshots_collection()
    
    if not query_filter:
        query_filter = {}
    
    snapshot_data = {
        "operation_id": ObjectId(operation_id) if isinstance(operation_id, str) else operation_id,
        "snapshot_type": snapshot_type,
        "created_at": datetime.utcnow(),
        "data": {},
    }
    
    try:
        # Snapshot each collection
        for collection_name in collections_to_snapshot:
            collection = db[collection_name]
            docs = list(collection.find(query_filter))
            snapshot_data["data"][collection_name] = docs
            logger.debug(f"[📸] Snapshotted {len(docs)} documents from {collection_name}")
        
        # Store snapshot
        result = snapshot_collection.insert_one(snapshot_data)
        snapshot_id = str(result.inserted_id)
        
        # Link snapshot to operation
        ops_collection = get_system_operations_collection()
        ops_collection.update_one(
            {"_id": ObjectId(operation_id) if isinstance(operation_id, str) else operation_id},
            {"$set": {"snapshot_id": snapshot_id}}
        )
        
        logger.info(f"[📸] Created snapshot: {snapshot_id} for operation {operation_id}")
        return snapshot_id
    
    except Exception as e:
        logger.error(f"[❌] Failed to create snapshot: {e}")
        return None


# ==================== MUTATION APPLICATION (Phase C) ====================

def apply_operation(
    operation_id: str,
    mutation_job_id: Optional[str] = None,
) -> bool:
    """Apply operation mutations idempotently (Phase C).
    
    This executes the actual state mutations, but only if:
    1. Operation exists and is PREPARED
    2. effects_applied is False
    3. Caller has correct mutation_job_id
    
    Returns:
        bool: True if applied successfully
    """
    ops_collection = get_system_operations_collection()
    
    op_id = ObjectId(operation_id) if isinstance(operation_id, str) else operation_id
    operation = ops_collection.find_one({"_id": op_id})
    
    if not operation:
        logger.error(f"[❌] Operation not found: {operation_id}")
        return False
    
    # Idempotency check: already applied?
    if operation.get("effects_applied"):
        logger.warning(f"[⚠️] Operation already applied, skipping: {operation_id}")
        return True
    
    # Status check: must be PREPARED or PARTIAL (allowing retries)
    if operation["status"] not in [OperationStatus.PREPARED.value, OperationStatus.PARTIAL.value]:
        logger.error(f"[❌] Operation not in PREPARED state: {operation_id} (status: {operation['status']})")
        return False
    
    # Update mutation job ID
    if mutation_job_id:
        ops_collection.update_one(
            {"_id": op_id},
            {"$set": {"last_mutation_job_id": mutation_job_id}}
        )
    
    try:
        # Mark as applied (prevents double-fire even if mutation fails)
        ops_collection.update_one(
            {"_id": op_id},
            {
                "$set": {
                    "effects_applied": True,
                    "status": OperationStatus.APPLIED.value,
                    "applied_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"[✅] Applied operation: {operation_id}")
        return True
    
    except Exception as e:
        logger.error(f"[❌] Failed to mark operation as applied: {e}")
        return False


def mark_operation_failed(
    operation_id: str,
    error_message: str,
    affected: Optional[Dict[str, int]] = None,  # {success: 5, failure: 3}
) -> bool:
    """Mark operation as FAILED with error details.
    
    Args:
        operation_id: The operation that failed
        error_message: Description of the error
        affected: Counts of successful/failed mutations
    
    Returns:
        bool: True if updated
    """
    ops_collection = get_system_operations_collection()
    op_id = ObjectId(operation_id) if isinstance(operation_id, str) else operation_id
    
    update_data = {
        "status": OperationStatus.FAILED.value,
        "$push": {"errors": {
            "message": error_message,
            "timestamp": datetime.utcnow(),
        }},
    }
    
    if affected:
        update_data["success_count"] = affected.get("success", 0)
        update_data["failure_count"] = affected.get("failure", 0)
    
    try:
        ops_collection.update_one(
            {"_id": op_id},
            {"$set": update_data}
        )
        logger.error(f"[❌] Operation marked as FAILED: {operation_id}")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to mark operation as failed: {e}")
        return False


# ==================== ROLLBACK (Phase E) ====================

def rollback_operation(operation_id: str) -> bool:
    """Rollback an operation to its pre-mutation state.
    
    This restores data from the snapshot created in Phase B.
    
    Args:
        operation_id: The operation to rollback
    
    Returns:
        bool: True if rollback successful
    """
    ops_collection = get_system_operations_collection()
    snapshot_collection = get_operation_snapshots_collection()
    db = get_database()
    
    op_id = ObjectId(operation_id) if isinstance(operation_id, str) else operation_id
    operation = ops_collection.find_one({"_id": op_id})
    
    if not operation:
        logger.error(f"[❌] Operation not found: {operation_id}")
        return False
    
    if operation["status"] == OperationStatus.ROLLED_BACK.value:
        logger.warning(f"[⚠️] Operation already rolled back: {operation_id}")
        return True
    
    snapshot_id = operation.get("snapshot_id")
    if not snapshot_id:
        logger.error(f"[❌] No snapshot for operation: {operation_id}")
        return False
    
    snapshot = snapshot_collection.find_one({"_id": ObjectId(snapshot_id)})
    if not snapshot:
        logger.error(f"[❌] Snapshot not found: {snapshot_id}")
        return False
    
    try:
        # Restore all snapshotted collections
        for collection_name, docs in snapshot.get("data", {}).items():
            collection = db[collection_name]
            
            # Replace/restore documents
            if docs:
                for doc in docs:
                    doc_id = doc.get("_id")
                    if doc_id:
                        collection.replace_one({"_id": doc_id}, doc, upsert=True)
                logger.info(f"[🔄] Restored {len(docs)} documents in {collection_name}")
        
        # Mark operation as rolled back
        ops_collection.update_one(
            {"_id": op_id},
            {
                "$set": {
                    "status": OperationStatus.ROLLED_BACK.value,
                    "rolled_back_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"[✅] Rolled back operation: {operation_id}")
        return True
    
    except Exception as e:
        logger.error(f"[❌] Failed to rollback operation: {e}")
        mark_operation_failed(operation_id, f"Rollback failed: {str(e)}")
        return False


# ==================== OPERATION QUERIES ====================

def get_operation(operation_id: str) -> Optional[Dict[str, Any]]:
    """Get operation details by ID."""
    ops_collection = get_system_operations_collection()
    op_id = ObjectId(operation_id) if isinstance(operation_id, str) else operation_id
    operation = ops_collection.find_one({"_id": op_id})
    
    if operation:
        operation["id"] = str(operation["_id"])
    
    return operation


def get_operation_by_key(op_key: str) -> Optional[Dict[str, Any]]:
    """Get operation by idempotency key."""
    ops_collection = get_system_operations_collection()
    operation = ops_collection.find_one({"op_key": op_key})
    
    if operation:
        operation["id"] = str(operation["_id"])
    
    return operation


def list_operations(
    op_type: Optional[str] = None,
    status: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List operations with optional filters."""
    ops_collection = get_system_operations_collection()
    
    query = {}
    if op_type:
        query["op_type"] = op_type
    if status:
        query["status"] = status
    if scope:
        query["scope"] = scope
    
    operations = list(
        ops_collection.find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    
    for op in operations:
        op["id"] = str(op["_id"])
    
    return operations


# ==================== OPERATION HELPERS ====================

def generate_op_key(op_type: str, scope: str, scope_id: Optional[str] = None) -> str:
    """Generate a unique, deterministic operation key.
    
    Format: {op_type}:{scope}:{scope_id}:{timestamp_nonce}
    
    Args:
        op_type: Operation type (e.g., "xp_season_reset")
        scope: Operation scope (e.g., "system")
        scope_id: Scope identifier (e.g., guild_id, user_id)
    
    Returns:
        str: Unique operation key
    """
    timestamp = datetime.utcnow().timestamp()
    nonce = uuid.uuid4().hex[:8]
    
    parts = [op_type, scope]
    if scope_id:
        parts.append(str(scope_id))
    parts.append(f"{timestamp:.0f}")
    parts.append(nonce)
    
    return ":".join(parts)


def is_operation_complete(operation_id: str) -> bool:
    """Check if operation is in a terminal state."""
    operation = get_operation(operation_id)
    if not operation:
        return False
    
    terminal_states = [
        OperationStatus.APPLIED.value,
        OperationStatus.ROLLED_BACK.value,
        OperationStatus.FAILED.value,
    ]
    
    return operation["status"] in terminal_states
