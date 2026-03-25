"""State Validation Service

Pre-flight validation for system state definitions before activation.
Part of Phase 2 architectural improvements.

**Responsibility:**
- Validate state definitions before activation
- Check effects exist in registry
- Verify priority levels are reasonable
- Ensure dates are sensible (start < end, not in distant past)
- Validate scope values

**Benefits:**
- Prevent bad state definitions from entering system
- Operator safety and error detection early
- Clear error messages for troubleshooting
- Reduce runtime failures from bad config
"""

from __future__ import annotations

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timezone
import logging

from abby_core.system.effects_registry import EFFECT_REGISTRY, validate_effects

logger = logging.getLogger(__name__)


# Valid scope values
VALID_SCOPES = {"global", "guild", "user"}

# Valid state types
VALID_STATE_TYPES = {"season", "event", "mode", "override"}

# Priority bounds (reasonable range)
MIN_PRIORITY = 0
MAX_PRIORITY = 1000


class StateValidationService:
    """Pre-flight validation for system state definitions.
    
    Validates state definitions before they are activated to catch
    operator errors early and prevent bad configs from entering the system.
    """
    
    def validate_state_definition(
        self,
        state_def: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate a complete state definition.
        
        Args:
            state_def: State definition dict to validate
        
        Returns:
            (all_valid, list_of_errors)
        """
        errors = []
        
        # Required fields check
        required_fields = ["state_id", "state_type", "key", "label"]
        for field in required_fields:
            if field not in state_def:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return (False, errors)
        
        # Validate state_type
        state_type = state_def.get("state_type")
        if state_type not in VALID_STATE_TYPES:
            errors.append(
                f"Invalid state_type '{state_type}'. "
                f"Must be one of: {VALID_STATE_TYPES}"
            )
        
        # Validate scope
        scope = state_def.get("scope", "global")
        if scope not in VALID_SCOPES:
            errors.append(
                f"Invalid scope '{scope}'. "
                f"Must be one of: {VALID_SCOPES}"
            )
        
        # Validate priority
        priority = state_def.get("priority", 0)
        if not isinstance(priority, (int, float)):
            errors.append(f"Priority must be a number, got {type(priority).__name__}")
        elif priority < MIN_PRIORITY or priority > MAX_PRIORITY:
            errors.append(
                f"Priority {priority} out of range "
                f"({MIN_PRIORITY}-{MAX_PRIORITY})"
            )
        
        # Validate effects if present
        effects = state_def.get("effects", {})
        if effects:
            effects_valid, effects_msg, _ = validate_effects(effects)
            if not effects_valid:
                errors.append(f"Effects validation failed: {effects_msg}")
        
        # Validate metadata structure
        metadata = state_def.get("metadata", {})
        if not isinstance(metadata, dict):
            errors.append(f"Metadata must be a dict, got {type(metadata).__name__}")
        
        return (len(errors) == 0, errors)
    
    def validate_state_instance(
        self,
        instance: Dict[str, Any],
        now: Optional[datetime] = None
    ) -> Tuple[bool, List[str]]:
        """Validate a state instance (activation record).
        
        Args:
            instance: State instance dict to validate
            now: Current time for date validation (defaults to UTC now)
        
        Returns:
            (all_valid, list_of_errors)
        """
        errors = []
        now = now or datetime.now(timezone.utc)
        
        # Required fields
        required_fields = ["state_id", "start_at"]
        for field in required_fields:
            if field not in instance:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return (False, errors)
        
        # Validate dates
        start_at = instance.get("start_at")
        end_at = instance.get("end_at")
        
        if start_at:
            if not isinstance(start_at, datetime):
                errors.append(
                    f"start_at must be datetime, got {type(start_at).__name__}"
                )
            else:
                # Warn if start date is too far in the past (likely config error)
                days_old = (now - start_at).days
                if days_old > 365:
                    errors.append(
                        f"start_at is {days_old} days in the past. "
                        "Check if this is intended."
                    )
        
        if end_at:
            if not isinstance(end_at, datetime):
                errors.append(
                    f"end_at must be datetime, got {type(end_at).__name__}"
                )
            elif start_at and end_at < start_at:
                errors.append(
                    f"end_at ({end_at}) is before start_at ({start_at})"
                )
        
        # Validate priority
        priority = instance.get("priority", 0)
        if not isinstance(priority, (int, float)):
            errors.append(f"Priority must be a number, got {type(priority).__name__}")
        elif priority < MIN_PRIORITY or priority > MAX_PRIORITY:
            errors.append(
                f"Priority {priority} out of range "
                f"({MIN_PRIORITY}-{MAX_PRIORITY})"
            )
        
        return (len(errors) == 0, errors)
    
    def validate_before_activation(
        self,
        state_def: Dict[str, Any],
        instance: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Comprehensive validation before activating a state.
        
        Validates both the state definition and the instance activation record.
        
        Args:
            state_def: State definition dict
            instance: State instance activation record
        
        Returns:
            (all_valid, list_of_errors)
        """
        all_errors = []
        
        # Validate definition
        def_valid, def_errors = self.validate_state_definition(state_def)
        if not def_valid:
            all_errors.extend([f"Definition: {e}" for e in def_errors])
        
        # Validate instance
        inst_valid, inst_errors = self.validate_state_instance(instance)
        if not inst_valid:
            all_errors.extend([f"Instance: {e}" for e in inst_errors])
        
        # Cross-check: state_id must match
        if state_def.get("state_id") != instance.get("state_id"):
            all_errors.append(
                f"state_id mismatch: definition has "
                f"'{state_def.get('state_id')}', instance has "
                f"'{instance.get('state_id')}'"
            )
        
        return (len(all_errors) == 0, all_errors)


# Singleton instance
_validation_service: Optional[StateValidationService] = None


def validate_persona_overlay(
    persona_overlay_value: str,
) -> Tuple[bool, Optional[str]]:
    """Validate persona_overlay effect against PersonalityManager.
    
    Ensures that persona overlay values reference personas that actually
    exist in the personality definitions. Prevents state definitions from
    specifying non-existent persona names.
    
    **Motivation:** New personas can be added to personality definitions
    without updating effects registry. This validation detects mismatch early.
    
    Args:
        persona_overlay_value: Persona name to validate (e.g., "romantic_playful")
    
    Returns:
        (is_valid, error_message or None)
    
    Example:
        is_valid, error = validate_persona_overlay("romantic_playful")
        if not is_valid:
            logger.error(f"Invalid persona: {error}")
    """
    try:
        from abby_core.personality.manager import PersonalityManager
        
        # Get list of available personas from personality manager
        manager = PersonalityManager()
        available = manager.get_available_personas()
        
        if persona_overlay_value not in available:
            available_list = ", ".join(sorted(available.keys()))
            error_msg = (
                f"Persona '{persona_overlay_value}' not found in PersonalityManager. "
                f"Available personas: {available_list}"
            )
            return (False, error_msg)
        
        return (True, None)
    
    except Exception as e:
        # If PersonalityManager fails to load, be lenient but warn
        error_msg = (
            f"Could not validate persona '{persona_overlay_value}' "
            f"against PersonalityManager: {str(e)}. "
            f"Allowing activation but check personality data."
        )
        logger.warning(f"[⚠️ persona_validation] {error_msg}")
        return (True, None)  # Lenient: don't block if we can't validate


_validation_service: Optional[StateValidationService] = None


def get_state_validation_service() -> StateValidationService:
    """Get singleton state validation service.
    
    Returns:
        StateValidationService instance
    """
    global _validation_service
    if _validation_service is None:
        _validation_service = StateValidationService()
    return _validation_service
