"""System-wide effects registry and validation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Central registry of allowed effect keys and their constraints
# Extend this list to add new effect types; keep values deterministic and safe.
#
# merge_strategy controls how overlapping effects are combined:
# - override: last writer wins (default)
# - additive: numbers are summed (identity: 0.0)
# - multiplier: numbers are multiplied (identity: 1.0)
# - max: maximum wins for numbers (identity: -inf)
# - or: booleans OR together (identity: False)
#
# identity: the starting value for merge operations. For additive, start at 0.
# For multiplier, start at 1.0. This ensures deterministic results regardless
# of state order.
EFFECT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "persona_overlay": {
        "type": "enum",
        "options": [
            "romantic_playful",
            "bunny_pride",
            "cozy_ceremonial",
            "energetic_sunny",
        ],
        "description": "Persona overlay tone preset",
        "merge_strategy": "override",
        "identity": None,  # No identity for override strategy
    },
    "affinity_modifier": {
        "type": "number",
        "choices": [0.75, 1.0, 1.25, 1.5],
        "min": 0.5,
        "max": 2.0,
        "description": "Multiplier for affinity gain",
        "merge_strategy": "multiplier",
        "identity": 1.0,  # Multiplier starts at 1.0 (multiplicative identity)
    },
    "crush_system_enabled": {
        "type": "bool",
        "description": "Enable crush system",
        "merge_strategy": "or",
        "identity": False,  # OR starts at False
    },
    "egg_hunt_enabled": {
        "type": "bool",
        "description": "Enable egg hunt flow",
        "merge_strategy": "or",
        "identity": False,
    },
    "special_dialogue": {
        "type": "bool",
        "description": "Enable special dialogue lines",
        "merge_strategy": "or",
        "identity": False,
    },
    "daily_drops_enabled": {
        "type": "bool",
        "description": "Enable daily drop rewards",
        "merge_strategy": "or",
        "identity": False,
    },
    "festive_theme": {
        "type": "bool",
        "description": "Enable festive theming",
        "merge_strategy": "or",
        "identity": False,
    },
    "outdoor_activities_enabled": {
        "type": "bool",
        "description": "Enable outdoor activity prompts",
        "merge_strategy": "or",
        "identity": False,
    },
}


class ValidationError(Exception):
    """Raised when effect validation fails."""


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ValidationError(f"Invalid bool value: {value}")


def _coerce_number(value: Any, min_v: Optional[float], max_v: Optional[float]) -> float:
    try:
        num = float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValidationError(f"Invalid number value: {value}") from exc
    if min_v is not None and num < min_v:
        raise ValidationError(f"Value {num} below min {min_v}")
    if max_v is not None and num > max_v:
        raise ValidationError(f"Value {num} above max {max_v}")
    return num


def validate_effects(
    effects: Dict[str, Any],
    allowed_keys: Optional[List[str]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate and normalize effects.

    Returns (ok, message, normalized_effects).
    """
    normalized: Dict[str, Any] = {}

    for key, value in effects.items():
        if allowed_keys is not None and key not in allowed_keys:
            return False, f"Effect '{key}' is not allowed for this template", {}

        schema = EFFECT_REGISTRY.get(key)
        if not schema:
            return False, f"Unknown effect '{key}'", {}

        typ = schema.get("type")
        try:
            if typ == "bool":
                normalized[key] = _coerce_bool(value)
            elif typ == "number":
                min_v = schema.get("min")
                max_v = schema.get("max")
                normalized[key] = _coerce_number(value, min_v, max_v)
            elif typ == "enum":
                options = schema.get("options", [])
                if value not in options:
                    raise ValidationError(f"Value '{value}' not in options: {options}")
                normalized[key] = value
            else:
                raise ValidationError(f"Unsupported effect type '{typ}'")
        except ValidationError as exc:
            return False, str(exc), {}

    return True, "ok", normalized


def get_effect_ui_choices(effect_key: str) -> List[str]:
    """Return a list of safe UI choices for an effect key."""
    schema = EFFECT_REGISTRY.get(effect_key)
    if not schema:
        return []
    if schema.get("type") == "enum":
        return list(schema.get("options", []))
    if schema.get("type") == "number":
        if "choices" in schema:
            return [str(v) for v in schema["choices"]]
    if schema.get("type") == "bool":
        return ["true", "false"]
    return []
