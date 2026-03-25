"""
State-Instance Synchronization & Validation

Ensures system_state (definitions) and system_state_instances (activations)
stay in sync. Provides idempotent creation and validation helpers.

**Phase 5 Hardening:**
- Unique constraint on system_state_instances(state_id, state_type) prevents duplicate instances
- Prevents orphaned instances that could never be properly deactivated
- Ensures each state type has at most one instance definition
- Constraint is created via abby_core/database/indexes.py on database initialization
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from abby_core.database.mongodb import get_database

try:
    from abby_core.observability.logging import logging
    logger = logging.getLogger(__name__)
except Exception:
    logger = None


def validate_state_instance_pair(state_id: str) -> Tuple[bool, str]:
    """Validate that a state has a corresponding instance.
    
    Returns: (is_valid, error_message)
    """
    db = get_database()
    
    # Check definition exists
    definition = db["system_state"].find_one({"state_id": state_id})
    if not definition:
        return False, f"No state definition found for '{state_id}'"
    
    # Check instance exists
    instance = db["system_state_instances"].find_one({"state_id": state_id})
    if not instance:
        return False, f"No state instance found for '{state_id}' (definition exists but instance missing)"
    
    return True, "OK"


def ensure_instance_for_state(
    state_id: str,
    state_type: str,
    priority: int = 10,
    scope: str = "global",
) -> Tuple[bool, str]:
    """Idempotently create an instance for a state definition.
    
    If instance already exists, returns success without modification.
    If instance missing, creates it with defaults from definition.
    
    Returns: (success, message)
    """
    db = get_database()
    definitions = db["system_state"]
    instances = db["system_state_instances"]
    
    # Check if instance already exists
    existing = instances.find_one({"state_id": state_id})
    if existing:
        if logger:
            logger.debug(f"[sync] Instance already exists for '{state_id}'")
        return True, f"Instance already exists for '{state_id}'"
    
    # Get definition to extract dates
    definition = definitions.find_one({"state_id": state_id})
    if not definition:
        return False, f"Cannot create instance: state definition not found for '{state_id}'"
    
    # Create instance
    instance = {
        "state_id": state_id,
        "state_type": state_type,
        "scope": scope,
        "priority": priority,
        "active": False,
        "activated_at": None,
        "activated_by": None,
        "start_at": definition.get("start_at"),
        "end_at": definition.get("end_at"),
        "effects_overrides": {},
        "default_start_at": definition.get("start_at"),
        "default_end_at": definition.get("end_at"),
        "date_override_applied": False,
        "created_at": datetime.utcnow(),
    }
    
    try:
        result = instances.insert_one(instance)
        if logger:
            logger.info(f"[sync] Created instance for '{state_id}': {result.inserted_id}")
        return True, f"Created instance for '{state_id}'"
    except Exception as exc:
        if logger:
            logger.error(f"[sync] Failed to create instance for '{state_id}': {exc}")
        return False, f"Failed to create instance: {exc}"


def audit_state_instance_sync() -> Dict[str, Any]:
    """Audit all state-instance pairs and report issues.
    
    Returns dict with:
    - total_definitions: Count of state definitions
    - total_instances: Count of instances
    - orphaned_definitions: Definitions without instances
    - orphaned_instances: Instances without definitions
    - synced_pairs: Valid state-instance pairs
    """
    db = get_database()
    definitions = list(db["system_state"].find({}))
    instances = list(db["system_state_instances"].find({}))
    
    def_ids = {doc["state_id"] for doc in definitions}
    inst_ids = {doc["state_id"] for doc in instances}
    
    orphaned_defs = def_ids - inst_ids
    orphaned_insts = inst_ids - def_ids
    synced = def_ids & inst_ids
    
    report = {
        "total_definitions": len(definitions),
        "total_instances": len(instances),
        "synced_pairs": len(synced),
        "orphaned_definitions": list(orphaned_defs),
        "orphaned_instances": list(orphaned_insts),
        "issues": [],
    }
    
    if orphaned_defs:
        report["issues"].append(
            f"Orphaned definitions (no instance): {', '.join(orphaned_defs)}"
        )
    
    if orphaned_insts:
        report["issues"].append(
            f"Orphaned instances (no definition): {', '.join(orphaned_insts)}"
        )
    
    return report


def repair_state_instance_sync(auto_fix: bool = False) -> Dict[str, Any]:
    """Repair orphaned state-instance pairs.
    
    Args:
        auto_fix: If True, automatically create missing instances.
                  If False, just report issues.
    
    Returns: Audit report with actions taken
    """
    db = get_database()
    definitions = list(db["system_state"].find({}))
    instances_coll = db["system_state_instances"]
    instances = list(instances_coll.find({}))
    
    def_ids = {doc["state_id"]: doc for doc in definitions}
    inst_ids = {doc["state_id"] for doc in instances}
    
    report = {
        "checked_definitions": len(definitions),
        "instances_created": 0,
        "instances_deleted": 0,
        "errors": [],
    }
    
    # Find orphaned definitions (missing instances)
    orphaned_defs = set(def_ids.keys()) - inst_ids
    
    if orphaned_defs and auto_fix:
        for state_id in orphaned_defs:
            definition = def_ids[state_id]
            try:
                result = instances_coll.insert_one({
                    "state_id": state_id,
                    "state_type": definition.get("state_type"),
                    "scope": "global",
                    "priority": definition.get("priority", 10),
                    "active": False,
                    "activated_at": None,
                    "activated_by": None,
                    "start_at": definition.get("start_at"),
                    "end_at": definition.get("end_at"),
                    "effects_overrides": {},
                    "default_start_at": definition.get("start_at"),
                    "default_end_at": definition.get("end_at"),
                    "date_override_applied": False,
                    "created_at": datetime.utcnow(),
                })
                report["instances_created"] += 1
                if logger:
                    logger.info(f"[repair] Created instance for orphaned definition: {state_id}")
            except Exception as exc:
                report["errors"].append(f"Failed to create instance for {state_id}: {exc}")
                if logger:
                    logger.error(f"[repair] Error creating instance: {exc}")
    
    return report
