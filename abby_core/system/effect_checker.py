"""
Effect Checker Helper

Simple utilities for job handlers to check if effects are active.
"""

from typing import Any, Optional
from abby_core.llm.system_state_resolver import resolve_system_state

try:
    from abby_core.observability.logging import logging
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None


def is_effect_active(effect_key: str) -> bool:
    """
    Check if a specific effect is currently active.
    
    Used by job handlers to conditionally run event-specific logic.
    
    Example:
        if is_effect_active("crush_system_enabled"):
            await spawn_valentine_heart()
    
    Args:
        effect_key: Effect key from effects_registry (e.g., "crush_system_enabled")
    
    Returns:
        True if effect is active, False otherwise
    """
    try:
        state = resolve_system_state()
        effects = state.get("effects", {})
        return bool(effects.get(effect_key, False))
    except Exception as exc:
        if logger:
            logger.warning(f"[effect] Error checking effect '{effect_key}': {exc}")
        return False


def get_active_effect_value(effect_key: str, default: Any = None) -> Any:
    """
    Get the current value of an active effect.
    
    Used for numeric or enum effects that have multipliers or settings.
    
    Example:
        modifier = get_active_effect_value("affinity_modifier", 1.0)
        affinity_gain = base_affinity * modifier
    
    Args:
        effect_key: Effect key from effects_registry
        default: Default value if effect not active
    
    Returns:
        Effect value or default
    """
    try:
        state = resolve_system_state()
        effects = state.get("effects", {})
        return effects.get(effect_key, default)
    except Exception as exc:
        if logger:
            logger.warning(f"[effect] Error getting effect value '{effect_key}': {exc}")
        return default


def get_active_state_id(state_type: str = "event") -> Optional[str]:
    """
    Get the ID of the currently active state of a specific type.
    
    Example:
        event_id = get_active_state_id("event")
        if event_id:
            print(f"Active event: {event_id}")
    
    Args:
        state_type: Type filter (event, season, era, mode)
    
    Returns:
        state_id or None if no matching state active
    """
    try:
        state = resolve_system_state()
        active_states = state.get("active_states", [])
        
        # Find first state matching type
        for st in active_states:
            if st.get("state_type") == state_type:
                return st.get("state_id")
        
        return None
    except Exception as exc:
        if logger:
            logger.warning(f"[effect] Error getting active state: {exc}")
        return None


def get_all_active_effects() -> dict:
    """
    Get all currently active effects as a merged dict.
    
    Returns a dict of all active effects from all active states,
    merged by priority (higher priority wins).
    
    Example:
        effects = get_all_active_effects()
        print(f"persona_overlay: {effects.get('persona_overlay')}")
    
    Returns:
        Dict of {effect_key: value, ...}
    """
    try:
        state = resolve_system_state()
        return state.get("effects", {})
    except Exception as exc:
        if logger:
            logger.warning(f"[effect] Error getting all effects: {exc}")
        return {}
