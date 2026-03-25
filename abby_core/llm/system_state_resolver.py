"""System state resolver for conversation context.

Resolves active system states (seasons, events, modes) and produces a
merged effects map for downstream prompt building. Prefers the
`system_state_instances` collection (definition + activation), but falls back
to legacy `system_state` collection when instances are unavailable.

Architecture Refactoring:
- Effects merging extracted to abby_core/system/effects_merger.py
- State resolver focuses on fetching/normalization
- Effects merge logic reusable for testing, validation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from abby_core.database.mongodb import get_database
from abby_core.database.collections.system_state import (
    get_active_states as query_active_states,
    get_states_by_ids,
)
from abby_core.system.system_state import get_system_state_collection
from abby_core.system.effects_merger import merge_effects
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


# ==================== FETCH HELPERS (using collection module) ====================


def _normalize_state(base: Optional[Dict[str, Any]], instance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = base or {}
    instance = instance or {}

    state = {
        "state_id": instance.get("state_id") or base.get("state_id"),
        "state_type": instance.get("state_type") or base.get("state_type"),
        "key": instance.get("key") or base.get("key"),
        "label": instance.get("label") or base.get("label"),
        "scope": instance.get("scope") or base.get("scope") or "global",
        "priority": instance.get("priority", base.get("priority", 0)),
        "effects": base.get("effects", {}),
        "metadata": base.get("metadata", {}),
        "start_at": instance.get("start_at") or base.get("start_at"),
        "end_at": instance.get("end_at") or base.get("end_at"),
        "active": instance.get("active", base.get("active", False)),
        "activated_at": instance.get("activated_at") or base.get("activated_at"),
        "activated_by": instance.get("activated_by") or base.get("activated_by"),
    }

    return state


def _fetch_active_instances(now: datetime, scope: str) -> List[Dict[str, Any]]:
    """Fetch active state instances (canonical, singleton)."""
    try:
        # Use collection module helper instead of direct get_database() call
        return query_active_states(now=now, scope=scope)
    except Exception as exc:  # pragma: no cover - defensive for missing collection
        logger.warning(f"[state_resolver] Unable to query system_state_instances: {exc}")
        return []


def _fetch_state_definitions(state_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch state definitions by IDs (canonical, singleton)."""
    if not state_ids:
        return {}
    try:
        # Use collection module helper instead of direct collection.find()
        return get_states_by_ids(state_ids)
    except Exception as exc:  # pragma: no cover - defensive for missing collection
        logger.warning(f"[state_resolver] Unable to query system_state: {exc}")
        return {}


def _fallback_active_states(now: datetime) -> List[Dict[str, Any]]:
    """Fallback: fetch active states from legacy system_state collection."""
    try:
        # Use collection helper for fallback
        return query_active_states(now=now, scope="global")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[state_resolver] Fallback system_state query failed: {exc}")
        return []


# _merge_effects moved to abby_core/system/effects_merger.py
# This resolver now delegates to the extracted module for better testability
# and reusability across testing/validation/simulation scenarios.


def resolve_system_state(now: Optional[datetime] = None, scope: str = "global") -> Dict[str, Any]:
    """Resolve active system state stack and merged effects.
    
    Uses MongoDB snapshot read concern to ensure deterministic resolution
    during concurrent state transitions. All reads within this function
    see a consistent view of the database.

    Args:
        now: Timestamp to resolve against (defaults to UTC now)
        scope: State scope (global by default)

    Returns:
        Dict with timestamp, scope, active_states, and merged effects.
    """
    ts = now or datetime.utcnow()

    # Use snapshot isolation for deterministic concurrent reads
    # This ensures all queries see a consistent view of active states
    try:
        db = get_database()
        with db.client.start_session() as session:
            # Set snapshot read concern for consistent reads
            session.start_transaction(
                read_concern=ReadConcern(level="snapshot"),
                write_concern=WriteConcern(w="majority"),
            )
            try:
                # Prefer instance-based resolution
                instances = _fetch_active_instances(ts, scope)
                if instances:
                    # Extract state IDs with proper type narrowing (filter truthy, then index safely)
                    state_ids = [inst["state_id"] for inst in instances if inst.get("state_id")]
                    definitions = _fetch_state_definitions(state_ids)
                    # Build active states, safely accessing state_id since we already filtered
                    active_states = []
                    for inst in instances:
                        state_id = inst.get("state_id")
                        if state_id:
                            active_states.append(_normalize_state(definitions.get(state_id), inst))
                else:
                    # Fallback to legacy collection (single active flag)
                    active_states = _fallback_active_states(ts)

                # Use extracted merger from system layer
                effects = merge_effects(active_states)
                
                # Commit transaction (read-only, but completes snapshot)
                session.commit_transaction()
                
                logger.debug(
                    f"[state_resolver] Resolved {len(active_states)} active states "
                    f"with {len(effects)} merged effects (snapshot isolation)"
                )
                
                return {
                    "timestamp": ts,
                    "scope": scope,
                    "active_states": active_states,
                    "effects": effects,
                }
                
            except Exception as e:
                session.abort_transaction()
                raise
                
    except Exception as e:
        # Fallback: If snapshot isolation fails (unsupported MongoDB version),
        # perform non-transactional read with warning
        logger.warning(
            f"[state_resolver] Snapshot isolation failed: {e}. "
            f"Falling back to non-transactional read (non-deterministic under concurrent transitions)"
        )
        
        # Fallback to original logic without transaction
        instances = _fetch_active_instances(ts, scope)
        if instances:
            state_ids = [inst["state_id"] for inst in instances if inst.get("state_id")]
            definitions = _fetch_state_definitions(state_ids)
            active_states = []
            for inst in instances:
                state_id = inst.get("state_id")
                if state_id:
                    active_states.append(_normalize_state(definitions.get(state_id), inst))
        else:
            active_states = _fallback_active_states(ts)
        
        effects = merge_effects(active_states)
        
        return {
            "timestamp": ts,
            "scope": scope,
            "active_states": active_states,
            "effects": effects,
        }


def summarize_state_for_prompt(state_context: Optional[Dict[str, Any]]) -> Optional[str]:
    """Format system state context for safe prompt injection."""
    if not state_context:
        return None

    active_states = state_context.get("active_states") or []
    effects = state_context.get("effects") or {}

    if not active_states and not effects:
        return None

    lines: List[str] = []
    scope = state_context.get("scope", "global")
    lines.append(f"Scope: {scope}")

    if active_states:
        lines.append("Active states:")
        for state in sorted(active_states, key=lambda s: s.get("priority", 0), reverse=True):
            label = state.get("label") or state.get("state_id") or "unknown"
            state_type = state.get("state_type", "unknown")
            priority = state.get("priority", 0)
            key = state.get("key") or "-"
            lines.append(f"- {state_type}:{key} ({label}) priority={priority}")

    if effects:
        lines.append("Merged effects:")
        for effect_key, effect_value in effects.items():
            lines.append(f"- {effect_key}: {effect_value}")

    return "\n".join(lines)
