"""Effects merging logic for system state resolution.

Extracted from system_state_resolver.py to properly separate concerns:
- State resolver: Fetches instances, normalizes, resolves active states
- Effects merger (this module): Merges effects using registry strategies

Architecture Benefit:
- Effects merge logic isolated and testable
- Reusable for validation, testing, simulation
- State resolver focuses on fetching/normalization
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from abby_core.system.effects_registry import EFFECT_REGISTRY

logger = logging.getLogger(__name__)


def merge_effects(
    states: List[Dict[str, Any]],
    operator_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge effects deterministically using registry-defined strategies with identity values.
    
    **Merge Precedence (Deterministic Order):**
    1. Sort states by (priority DESC, start_at DESC)
       - Higher priority wins in case of ties
       - More recent start_at wins if priorities are equal
    2. For each effect in order:
       - Initialize with registry-defined identity value
       - Apply merge strategy (additive, multiplier, or, override, max)
       - Type mismatch results in hard error (no silent fallback)
    
    **Merge Strategies (Registry-Defined):**
    - **override**: Last writer wins. Identity: None. Used for: persona_overlay
    - **additive**: Sum all values. Identity: 0.0. Used for: XP multipliers (deprecated - use multiplier instead)
    - **multiplier**: Product of all values. Identity: 1.0. Used for: affinity_modifier, rate multipliers
    - **max**: Maximum value wins. Identity: -∞. Used for: level caps, max values
    - **or**: Boolean OR. Identity: False. Used for: crush_system_enabled, egg_hunt_enabled, etc.
    
    **Type Safety (Hard Validation):**
    Each effect type must match its strategy exactly:
    - additive/multiplier/max require numeric types (int, float)
    - or requires bool type
    - override accepts any type
    If types don't match strategy, merge raises ValueError (prevents silent corruption)
    
    **Example Merge (Deterministic):**
    ```
    State A (priority=10, start_at=2026-01-15):
      affinity_modifier: 1.25
      crush_system_enabled: True
    
    State B (priority=10, start_at=2026-01-20):  # More recent, so applied second
      affinity_modifier: 1.1
      crush_system_enabled: False
    
    Sort order: [B (newer), A (older)]
    
    Result (after merge):
      affinity_modifier: 1.0 (identity) * 1.1 * 1.25 = 1.375
      crush_system_enabled: False (identity) OR True OR False = True
    ```
    
    Each merge strategy has a defined identity value (starting point):
    - additive: identity = 0.0 (sum starts at zero)
    - multiplier: identity = 1.0 (product starts at one)
    - or: identity = False (OR starts at false)
    - override: identity = None (no accumulation)
    
    **Type Safety (Phase 1):**
    Type mismatches are logged as ERROR and raise ValueError
    (not silent fallback) for observability. Prevents silent data corruption.
    
    Args:
        states: List of active state dictionaries with 'effects', 'priority', 'start_at' fields
        operator_id: User/system ID performing the merge (for audit trail)
        
    Returns:
        Dictionary of merged effects with resolved values
        
    Raises:
        ValueError: If effect type mismatches merge strategy
    """
    operator_id = operator_id or "system"
    merged: Dict[str, Any] = {}
    type_mismatch_count = 0
    
    sorted_states = sorted(
        states,
        key=lambda s: (s.get("priority", 0), s.get("start_at") or datetime.min),
        reverse=True,
    )

    for state in sorted_states:
        effects = state.get("effects") or {}
        for key, value in effects.items():
            if key not in merged:
                # Initialize with identity value from registry
                schema = EFFECT_REGISTRY.get(key, {})
                strategy = schema.get("merge_strategy", "override")
                identity = schema.get("identity")
                
                # For strategies with identity values, start with identity
                if strategy in ("additive", "multiplier", "or"):
                    merged[key] = identity
                else:
                    merged[key] = None
                
                logger.debug(f"[effects_merge] Initialized {key} with identity {identity} (strategy: {strategy})")
                # Fall through to apply the first value

            schema = EFFECT_REGISTRY.get(key, {})
            strategy = schema.get("merge_strategy", "override")
            current = merged.get(key)

            try:
                if strategy == "or" and isinstance(value, bool) and isinstance(current, bool):
                    merged[key] = current or value
                elif strategy == "additive" and isinstance(value, (int, float)) and isinstance(current, (int, float)):
                    merged[key] = current + value
                elif strategy == "multiplier" and isinstance(value, (int, float)) and isinstance(current, (int, float)):
                    merged[key] = current * value
                elif strategy == "max" and isinstance(value, (int, float)) and isinstance(current, (int, float)):
                    merged[key] = max(current, value)
                elif strategy == "override":
                    merged[key] = value
                else:
                    # Type mismatch - HARD FAIL (don't silent fallback)
                    # This ensures state definitions are validated at activation time, not merge time
                    type_mismatch_count += 1
                    error_msg = (
                        f"Type mismatch for effect '{key}': "
                        f"strategy '{strategy}' cannot merge "
                        f"current={type(current).__name__}({current!r}) "
                        f"with new={type(value).__name__}({value!r}). "
                        f"State definition validation failed. "
                        f"operator={operator_id} state_id={state.get('state_id', '?')}"
                    )
                    logger.error(f"[❌ effects_merge] {error_msg}")
                    raise ValueError(error_msg)
            except ValueError:
                # Re-raise type validation errors
                raise
            except Exception as exc:
                type_mismatch_count += 1
                logger.error(
                    f"[❌ effects_merge] Error merging effect '{key}' with strategy '{strategy}': {exc}. "
                    f"operator={operator_id}",
                    exc_info=True
                )
                raise
    
    # Log merge summary (metrics for observability)
    if merged or states:
        logger.info(
            f"[✓ effects_merge] Completed "
            f"states={len(states)} "
            f"effects={len(merged)} "
            f"type_mismatches={type_mismatch_count} "
            f"operator={operator_id}"
        )
    
    return merged
