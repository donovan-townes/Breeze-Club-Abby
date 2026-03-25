"""
Season Reset Operations: Safe, audited, rollback-capable XP resets (system namespace).

Implements XP reset flow across phases:
- Phase A: Freeze intent (create_xp_season_reset)
- Phase B: Snapshot anchor (snapshot_before_xp_reset)
- Phase C: Apply mutation (apply_xp_season_reset)
- Phase D: Update summaries (recompute_summaries_after_reset)
- Phase E: Announce (via system_events + delivery job)
"""

from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from abby_core.database.mongodb import get_database
from abby_core.system.system_operations import (
    create_operation,
    create_snapshot,
    apply_operation,
    mark_operation_failed,
    OperationType,
    generate_op_key,
    get_system_operations_collection,
)
from abby_core.economy.user_summary import (
    rebuild_user_summary,
    compute_guild_summaries,
    invalidate_guild_summaries,
)
from abby_core.economy.xp import reset_seasonal_xp, get_xp_collection
from abby_core.services.events_lifecycle import record_season_transition_event
from abby_core.system.system_state import get_active_state
from abby_core.observability.logging import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


# ==================== XP RESET OPERATION FLOW ====================

def create_xp_season_reset(
    guild_ids: List[int],
    new_season_id: str,
    dry_run: bool = False,
    operator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Phase A: Freeze intent for XP season reset."""
    db = get_database()
    xp_collection = get_xp_collection()
    
    affected_count = 0
    scope_id = None
    scope = "system"  # Default: all guilds
    resolved_guild_ids = guild_ids.copy() if guild_ids else []
    
    if not guild_ids:
        resolved_guild_ids = [int(g) for g in xp_collection.distinct("guild_id", {}) if g]
        affected_count = xp_collection.count_documents({})
    else:
        scope = "guild"
        scope_id = "|".join(str(g) for g in guild_ids)
        
        for guild_id in guild_ids:
            count = xp_collection.count_documents({"guild_id": str(guild_id)})
            affected_count += count
    
    op_key = generate_op_key(
        OperationType.XP_SEASON_RESET.value,
        scope,
        scope_id,
    )
    
    operation_id = create_operation(
        op_type=OperationType.XP_SEASON_RESET.value,
        op_key=op_key,
        scope=scope,
        scope_id=scope_id,
        affected_count=affected_count,
        dry_run=dry_run,
        operator_id=operator_id,
        reason=reason,
        metadata={
            "guild_ids": resolved_guild_ids,
            "new_season_id": new_season_id,
        },
    )
    
    if not operation_id:
        return None
    
    if dry_run:
        logger.info(f"[🧪] DRY RUN XP reset: {affected_count} users, operation_id={operation_id}")
        return {
            "operation_id": operation_id,
            "affected_count": affected_count,
            "dry_run": True,
            "scope": scope,
            "scope_id": scope_id,
        }
    
    query_filter = {}
    if guild_ids:
        query_filter = {"guild_id": {"$in": [str(g) for g in guild_ids]}}
    
    snapshot_id = create_snapshot(
        operation_id=operation_id,
        snapshot_type="pre_xp_season_reset",
        collections_to_snapshot=["user_xp"],
        query_filter=query_filter,
    )
    
    if not snapshot_id:
        logger.error(f"[❌] Failed to create snapshot for operation {operation_id}")
        mark_operation_failed(operation_id, "Snapshot creation failed")
        return None
    
    logger.info(f"[✅] Phase A+B complete: operation_id={operation_id}, snapshot_id={snapshot_id}, affected={affected_count}")
    
    return {
        "operation_id": operation_id,
        "snapshot_id": snapshot_id,
        "affected_count": affected_count,
        "dry_run": False,
        "scope": scope,
        "scope_id": scope_id,
    }


def preview_xp_season_reset(
    guild_ids: List[int],
    sample_size: int = 10,
) -> Dict[str, Any]:
    """Generate preview data for XP reset (for operator confirmation)."""
    xp_collection = get_xp_collection()
    
    query = {}
    if guild_ids:
        query = {"guild_id": {"$in": [str(g) for g in guild_ids]}}
    
    total_users = xp_collection.count_documents(query)
    
    sample_users = []
    for doc in xp_collection.find(query).limit(sample_size):
        current_xp = doc.get("xp", doc.get("points", 0))
        current_level = doc.get("level", 1)
        sample_users.append({
            "user_id": doc.get("user_id"),
            "current_xp": current_xp,
            "current_level": current_level,
            "guild_id": doc.get("guild_id"),
        })
    
    return {
        "total_users": total_users,
        "sample_count": len(sample_users),
        "sample_users": sample_users,
        "estimated_cost": "~2-5s for mutation",
        "scope": "system" if not guild_ids else "guild",
        "scope_count": len(guild_ids) if guild_ids else "N/A",
    }


def apply_xp_season_reset(
    operation_id: str,
    guild_ids: List[int],
) -> Tuple[bool, Dict[str, Any]]:
    """Phase C: Apply XP reset mutation idempotently."""
    xp_collection = get_xp_collection()
    ops_collection = get_system_operations_collection()
    op_oid = ObjectId(operation_id) if isinstance(operation_id, str) else operation_id
    operation = ops_collection.find_one({"_id": op_oid}) or {}
    
    if not apply_operation(operation_id):
        return False, {"error": "Failed to mark operation as applied"}
    
    success_count = 0
    failure_count = 0
    errors = []
    
    try:
        new_season_id = (operation.get("metadata", {}) or {}).get("new_season_id", "unknown")
        
        if guild_ids:
            for guild_id in guild_ids:
                count = reset_seasonal_xp(guild_id, new_season_id=new_season_id)
                success_count += count
                logger.info(f"[✅] Reset XP for {count} users in guild {guild_id}")
        else:
            all_guilds = xp_collection.distinct("guild_id", {})
            for guild_id in all_guilds:
                if guild_id:
                    count = reset_seasonal_xp(guild_id, new_season_id=new_season_id)
                    success_count += count
        
        logger.info(f"[📊] Recomputing user summaries after reset...")
        if guild_ids:
            for guild_id in guild_ids:
                compute_guild_summaries(guild_id)
        else:
            all_guilds = xp_collection.distinct("guild_id", {})
            for guild_id in all_guilds:
                if guild_id:
                    compute_guild_summaries(guild_id)
        
        logger.info(f"[✅] Phase C+D complete: {success_count} users reset")

        ops_collection.update_one(
            {"_id": op_oid},
            {
                "$set": {
                    "success_count": success_count,
                    "failure_count": failure_count,
                }
            }
        )

        active_state = get_active_state("season")
        old_season_id = (active_state or {}).get("state_id", "unknown")

        event_id = record_season_transition_event(
            old_season_id=old_season_id,
            new_season_id=new_season_id,
            trigger="operator",
            operator_id=operation.get("operator_id"),
            reason=operation.get("reason"),
            idempotency_key=f"xp_season_reset:{operation_id}",
        )

        if event_id:
            ops_collection.update_one(
                {"_id": op_oid},
                {"$set": {"event_id": event_id}}
            )
            logger.info(f"[📢] Queued season announcement event {event_id} for op {operation_id}")
        else:
            logger.warning(f"[📢] Failed to queue season announcement for op {operation_id}")

        return True, {
            "operation_id": operation_id,
            "success_count": success_count,
            "failure_count": failure_count,
            "errors": errors,
            "event_id": event_id,
        }
    
    except Exception as e:
        logger.error(f"[❌] Phase C failed: {e}")
        mark_operation_failed(operation_id, str(e), {"success": success_count, "failure": failure_count})
        return False, {
            "error": str(e),
            "success_count": success_count,
            "failure_count": failure_count,
        }


def rollback_xp_season_reset(operation_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Rollback an XP reset operation."""
    from abby_core.system.system_operations import rollback_operation
    
    try:
        success = rollback_operation(operation_id)
        
        if success:
            from abby_core.economy.user_summary import get_user_summary_collection
            summary_collection = get_user_summary_collection()
            summary_collection.delete_many({})
            
            logger.info(f"[✅] Rolled back operation {operation_id} and invalidated summaries")
            return True, {"operation_id": operation_id, "rolled_back": True}
        return False, {"operation_id": operation_id, "error": "Rollback failed"}
    
    except Exception as e:
        logger.error(f"[❌] Rollback failed: {e}")
        return False, {"operation_id": operation_id, "error": str(e)}


# ==================== CONCURRENCY GUARD ====================

def check_concurrent_xp_operations() -> Tuple[bool, Optional[str]]:
    """Check if there are in-flight XP operations."""
    from abby_core.system.system_operations import get_system_operations_collection
    
    ops_collection = get_system_operations_collection()
    
    in_flight = list(ops_collection.find({
        "op_type": OperationType.XP_SEASON_RESET.value,
        "status": "prepared",
        "dry_run": False,
    }))
    
    if in_flight:
        blocking_op_id = str(in_flight[0]["_id"])
        return False, blocking_op_id
    
    return True, None
