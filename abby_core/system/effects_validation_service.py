"""Effects Validation Service

Pre-flight and runtime validation for system state effects.
Part of Phase 2 architectural improvements.

**Responsibility:**
- Validate effect values before state activation
- Check effect ranges (e.g., affinity_modifier in 0.5-2.0)
- Verify effect types match merge strategies
- Detect operator errors early

**Benefits:**
- Prevent bad state definitions from entering system
- Operator safety and error detection
- Runtime validation for merged effects
- Clear error messages for troubleshooting
"""

from __future__ import annotations

from typing import Dict, Any, Tuple, Optional
import logging

from abby_core.system.effects_registry import EFFECT_REGISTRY, validate_effects

logger = logging.getLogger(__name__)


class EffectsValidationService:
    """Validates effect values against registry schema.
    
    Provides pre-flight and runtime validation for system state effects:
    - Type checking (bool, number, enum)
    - Range validation (min/max constraints)
    - Identity type matching
    - Merge strategy compatibility
    """
    
    def validate_effect_values(
        self,
        effects: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate and normalize effect values.
        
        Args:
            effects: Effect key-value pairs to validate
        
        Returns:
            (success, error_message, normalized_effects)
        """
        return validate_effects(effects)
    
    def validate_merged_effects(
        self,
        merged_effects: Dict[str, Any]
    ) -> Tuple[bool, list]:
        """Runtime validation of merged effects.
        
        Checks that merged effect values are within valid ranges.
        
        Args:
            merged_effects: Final merged effects dict
        
        Returns:
            (all_valid, list_of_errors)
        """
        errors = []
        
        for key, value in merged_effects.items():
            schema = EFFECT_REGISTRY.get(key)
            if not schema:
                errors.append(f"Unknown effect '{key}' in merged result")
                continue
            
            # Validate type
            effect_type = schema.get("type")
            if effect_type == "number":
                if not isinstance(value, (int, float)):
                    errors.append(
                        f"Effect '{key}' has invalid type {type(value).__name__}, "
                        f"expected number"
                    )
                    continue
                
                # Check range constraints
                min_val = schema.get("min")
                max_val = schema.get("max")
                if min_val is not None and value < min_val:
                    errors.append(
                        f"Effect '{key}' value {value} below minimum {min_val}"
                    )
                if max_val is not None and value > max_val:
                    errors.append(
                        f"Effect '{key}' value {value} above maximum {max_val}"
                    )
            
            elif effect_type == "bool":
                if not isinstance(value, bool):
                    errors.append(
                        f"Effect '{key}' has invalid type {type(value).__name__}, "
                        f"expected bool"
                    )
            
            elif effect_type == "enum":
                options = schema.get("options", [])
                if value not in options:
                    errors.append(
                        f"Effect '{key}' value '{value}' not in valid options: {options}"
                    )
        
        return (len(errors) == 0, errors)
    
    def validate_merged_effects_strict(self, merged_effects: Dict[str, Any], state_id: str) -> Tuple[bool, list]:
        """Strict validation with warnings for merged effects (Phase 5 hardening).
        
        Enhanced validation that logs warnings for suspicious values even if valid.
        Validates merge strategy compatibility and records validation metrics.
        
        Args:
            merged_effects: Final merged effects dict
            state_id: State being validated (for logging context)
        
        Returns:
            (all_valid, list_of_errors)
        """
        errors = []
        warnings = []
        
        for key, value in merged_effects.items():
            schema = EFFECT_REGISTRY.get(key)
            if not schema:
                errors.append(f"Unknown effect '{key}' in merged result")
                continue
            
            effect_type = schema.get("type")
            merge_strategy = schema.get("merge_strategy")
            
            # Strict type validation
            if effect_type == "number":
                if not isinstance(value, (int, float)):
                    errors.append(
                        f"Effect '{key}' type mismatch: got {type(value).__name__}, "
                        f"expected number (state_id={state_id})"
                    )
                    continue
                
                min_val = schema.get("min")
                max_val = schema.get("max")
                if min_val is not None and value < min_val:
                    errors.append(f"Effect '{key}' {value} below minimum {min_val} (state_id={state_id})")
                if max_val is not None and value > max_val:
                    errors.append(f"Effect '{key}' {value} above maximum {max_val} (state_id={state_id})")
                
                if min_val is not None and value == min_val:
                    warnings.append(f"Effect '{key}' at minimum boundary {min_val} (state_id={state_id})")
                if max_val is not None and value == max_val:
                    warnings.append(f"Effect '{key}' at maximum boundary {max_val} (state_id={state_id})")
            
            elif effect_type == "bool":
                if not isinstance(value, bool):
                    errors.append(f"Effect '{key}' type mismatch: got {type(value).__name__}, expected bool (state_id={state_id})")
            
            elif effect_type == "enum":
                options = schema.get("options", [])
                if value not in options:
                    errors.append(f"Effect '{key}' invalid value '{value}', not in {options} (state_id={state_id})")
            
            if merge_strategy and effect_type:
                if merge_strategy in ["additive", "multiplier"] and effect_type != "number":
                    errors.append(f"Effect '{key}' has {merge_strategy} strategy but type is {effect_type}, expected number (state_id={state_id})")
        
        for warning in warnings:
            logger.warning(f"[⚠️ effect_merge] {warning}")
        
        return (len(errors) == 0, errors)
    
    def validate_identity_types(self) -> Tuple[bool, list]:
        """Validate that all effect identities match their merge strategies.
        
        Returns:
            (all_valid, list_of_errors)
        """
        errors = []
        
        for effect_key, schema in EFFECT_REGISTRY.items():
            strategy = schema.get("merge_strategy")
            identity = schema.get("identity")
            effect_type = schema.get("type")
            
            if strategy == "additive":
                if not isinstance(identity, (int, float)):
                    errors.append(
                        f"Effect '{effect_key}' has additive strategy but "
                        f"identity {identity} is not numeric"
                    )
                if identity != 0.0:
                    errors.append(
                        f"Effect '{effect_key}' has additive strategy but "
                        f"identity {identity} != 0.0"
                    )
            
            elif strategy == "multiplier":
                if not isinstance(identity, (int, float)):
                    errors.append(
                        f"Effect '{effect_key}' has multiplier strategy but "
                        f"identity {identity} is not numeric"
                    )
                if identity != 1.0:
                    errors.append(
                        f"Effect '{effect_key}' has multiplier strategy but "
                        f"identity {identity} != 1.0"
                    )
            
            elif strategy == "or":
                if not isinstance(identity, bool):
                    errors.append(
                        f"Effect '{effect_key}' has OR strategy but "
                        f"identity {identity} is not boolean"
                    )
                if identity is not False:
                    errors.append(
                        f"Effect '{effect_key}' has OR strategy but "
                        f"identity {identity} != False"
                    )
        
        return (len(errors) == 0, errors)


# Singleton instance
_validation_service: Optional[EffectsValidationService] = None


def get_effects_validation_service() -> EffectsValidationService:
    """Get singleton effects validation service.
    
    Returns:
        EffectsValidationService instance
    """
    global _validation_service
    if _validation_service is None:
        _validation_service = EffectsValidationService()
    return _validation_service
