"""System State Registry - Event/State templates and helpers (system namespace)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from abby_core.database.mongodb import get_database
from abby_core.system.system_state import (
    get_system_state_collection,
    initialize_state,
    get_state_by_id,
)
from abby_core.system.effects_registry import validate_effects
from abby_core.system.state_instance_sync import ensure_instance_for_state

try:  # pragma: no cover - logging optional in some environments
    from abby_core.observability.logging import logging
    logger = logging.getLogger(__name__)
except Exception:  # pragma: no cover - defensive
    logger = None


class StateCategory(str, Enum):
    """Categories of system states for validation."""
    SEASON = "season"
    EVENT = "event"
    ERA = "era"
    MODE = "mode"


# ==================== EVENT TEMPLATES ====================

APPROVED_EVENT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "valentines": {
        "state_type": "event",
        "key": "valentines",
        "label_template": "Breeze Club Valentine's Day {year}",
        "canon_ref": "lore.events.valentines.v1",
        "duration_days": 14,  # Feb 1-14
        "start_month": 2,
        "start_day": 1,
        "effects": {
            "persona_overlay": "romantic_playful",
            "affinity_modifier": 1.25,
            "crush_system_enabled": True,
        },
        "priority": 15,
        "description": "Valentine's Day event with crush system and playful romantic tone.",
        "allowed_overrides": [
            "persona_overlay",
            "affinity_modifier",
            "crush_system_enabled",
        ],
    },
    "easter": {
        "state_type": "event",
        "key": "easter",
        "label_template": "Easter {year} - Abby's Favorite Holiday",
        "canon_ref": "lore.events.easter.v1",
        "duration_days": 3,  # Good Friday through Easter Sunday
        "effects": {
            "persona_overlay": "bunny_pride",
            "special_dialogue": True,
            "egg_hunt_enabled": True,
        },
        "priority": 15,
        "description": "Easter event - Abby's favorite holiday as a bunny.",
        "notes": "Easter date varies yearly and is computed dynamically (Good Friday start).",
        "variable_date": True,
        "allowed_overrides": [
            "persona_overlay",
            "crush_system_enabled",
            "egg_hunt_enabled",
        ],
    },
    "21_days_breeze": {
        "state_type": "event",
        "key": "21_days_breeze",
        "label_template": "21 Days of the Breeze {year}",
        "canon_ref": "lore.events.21_days.v1",
        "duration_days": 21,  # Dec 1-21
        "start_month": 12,
        "start_day": 1,
        "effects": {
            "daily_drops_enabled": True,
            "festive_theme": True,
            "persona_overlay": "cozy_ceremonial",
        },
        "priority": 15,
        "description": "21 days of winter celebration with daily rewards.",
        "allowed_overrides": [
            "persona_overlay",
            "daily_drops_enabled",
            "festive_theme",
        ],
    },
}


# ==================== DATE HELPERS ====================


def _compute_easter_sunday(year: int) -> datetime:
    """Compute Easter Sunday (Gregorian) for a given year."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = 1 + ((h + l - 7 * m + 114) % 31)
    return datetime(year, month, day)


def _coerce_datetime(value: Optional[Any], label: str) -> Optional[datetime]:
    """Normalize datetime inputs; allow datetime or ISO-8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{label} must be ISO-8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM)")
    raise ValueError(f"{label} must be datetime or ISO-8601 string")


def _compute_event_window(
    event_key: str,
    year: int,
    start_at_override: Optional[Any] = None,
    end_at_override: Optional[Any] = None,
) -> Tuple[bool, Optional[str], Dict[str, datetime]]:
    template = APPROVED_EVENT_TEMPLATES[event_key]
    duration_days = template.get("duration_days", 1)

    if event_key == "easter":
        easter_sunday = _compute_easter_sunday(year)
        # Start on Good Friday (2 days before Easter Sunday)
        default_start = easter_sunday - timedelta(days=2)
    else:
        start_month = template.get("start_month")
        start_day = template.get("start_day")
        if not start_month or not start_day:
            return False, f"Template '{event_key}' missing start date info", {}
        default_start = datetime(year, start_month, start_day)

    default_end = default_start + timedelta(days=duration_days - 1)
    default_end = default_end.replace(hour=23, minute=59, second=59)

    start_at = _coerce_datetime(start_at_override, "start_at_override") or default_start
    end_at = _coerce_datetime(end_at_override, "end_at_override") or default_end

    if start_at >= end_at:
        return False, "Start date must be before end date", {}

    return True, None, {
        "start_at": start_at,
        "end_at": end_at,
        "default_start_at": default_start,
        "default_end_at": default_end,
    }


def get_event_schedule(
    event_key: str,
    year: int,
    start_at_override: Optional[Any] = None,
    end_at_override: Optional[Any] = None,
) -> Tuple[bool, Optional[str], Dict[str, datetime]]:
    """Public helper to compute event schedule for UI/validation."""
    is_valid, error = validate_event_template(event_key)
    if not is_valid:
        return False, error, {}

    return _compute_event_window(event_key, year, start_at_override, end_at_override)


# ==================== VALIDATION HELPERS ====================


def validate_event_template(event_key: str) -> Tuple[bool, Optional[str]]:
    """Validate that an event key exists in approved templates."""
    if event_key not in APPROVED_EVENT_TEMPLATES:
        available = ", ".join(APPROVED_EVENT_TEMPLATES.keys())
        return False, f"Unknown event '{event_key}'. Available: {available}"
    return True, None


def validate_state_definition(
    state_id: str,
    state_type: str,
    effects: Dict[str, Any],
    priority: int,
) -> Tuple[bool, Optional[str]]:
    """Validate state definition before creation."""
    existing = get_state_by_id(state_id)
    if existing:
        return False, f"State '{state_id}' already exists"
    try:
        StateCategory(state_type)
    except ValueError:
        valid_types = ", ".join([c.value for c in StateCategory])
        return False, f"Invalid state_type '{state_type}'. Valid: {valid_types}"
    if not (0 <= priority <= 100):
        return False, f"Priority must be 0-100, got {priority}"
    if not isinstance(effects, dict):
        return False, "Effects must be a dictionary"
    return True, None


# ==================== CRUD HELPERS ====================


def create_event_from_template(
    event_key: str,
    year: int,
    operator_id: Optional[int] = None,
    override_effects: Optional[Dict[str, Any]] = None,
    start_at_override: Optional[Any] = None,
    end_at_override: Optional[Any] = None,
    date_override_reason: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """Create a new event state + instance from approved template.

    Returns: (success, message, state_id)
    """
    is_valid, error = validate_event_template(event_key)
    if not is_valid:
        return False, error or "Unknown validation error", None

    template = APPROVED_EVENT_TEMPLATES[event_key]
    state_id = f"{event_key}-{year}"

    # Check if state already exists (prevents duplicate creation)
    existing_state = get_state_by_id(state_id)
    if existing_state:
        # State exists, but instance might be missing - ensure instance exists
        if logger:
            logger.info(f"[registry] State '{state_id}' already exists, ensuring instance...")
        sync_ok, sync_msg = ensure_instance_for_state(
            state_id=state_id,
            state_type=template["state_type"],
            priority=template["priority"],
        )
        if sync_ok:
            return True, f"Event '{state_id}' already exists (instance synced)", state_id
        else:
            return False, f"Event exists but instance sync failed: {sync_msg}", state_id

    ok_window, window_err, schedule = _compute_event_window(
        event_key,
        year,
        start_at_override=start_at_override,
        end_at_override=end_at_override,
    )
    if not ok_window:
        return False, window_err or "Invalid schedule", None

    effects = template["effects"].copy()

    allowed_overrides = template.get("allowed_overrides", [])
    overrides_to_apply: Dict[str, Any] = {}
    if override_effects:
        ok, msg, normalized = validate_effects(override_effects, allowed_keys=allowed_overrides)
        if not ok:
            return False, msg, None
        overrides_to_apply = normalized
        effects.update(normalized)

    # Validate definition fields
    valid_def, def_err = validate_state_definition(
        state_id=state_id,
        state_type=template["state_type"],
        effects=effects,
        priority=template["priority"],
    )
    if not valid_def:
        return False, def_err or "Invalid state definition", None

    is_date_overridden = (
        schedule["start_at"] != schedule["default_start_at"]
        or schedule["end_at"] != schedule["default_end_at"]
    )

    metadata = {
        "template": event_key,
        "created_by_operator": operator_id,
        "description": template.get("description", ""),
        "allowed_overrides": allowed_overrides,
        "applied_overrides": overrides_to_apply,
        "default_window": {
            "start_at": schedule["default_start_at"],
            "end_at": schedule["default_end_at"],
        },
    }

    if is_date_overridden:
        metadata["date_override"] = {
            "start_at": schedule["start_at"],
            "end_at": schedule["end_at"],
            "set_at": datetime.utcnow(),
            "set_by": operator_id,
            "reason": date_override_reason,
        }

    try:
        success = initialize_state(
            state_id=state_id,
            state_type=template["state_type"],
            key=template["key"],
            label=template["label_template"].format(year=year),
            canon_ref=template["canon_ref"],
            start_at=schedule["start_at"],
            end_at=schedule["end_at"],
            effects=effects,
            metadata=metadata,
        )

        if not success:
            return False, f"Failed to create state definition for '{state_id}'", None
    except Exception as exc:
        if logger:
            logger.error(f"[registry] Error creating state: {exc}")
        return False, f"Error creating state: {exc}", None

    db = get_database()
    instances = db["system_state_instances"]

    instance = {
        "state_id": state_id,
        "state_type": template["state_type"],
        "scope": "global",
        "priority": template["priority"],
        "active": False,
        "activated_at": None,
        "activated_by": None,
        "start_at": schedule["start_at"],
        "end_at": schedule["end_at"],
        "effects_overrides": overrides_to_apply,
        "default_start_at": schedule["default_start_at"],
        "default_end_at": schedule["default_end_at"],
        "date_override_applied": is_date_overridden,
    }

    try:
        result = instances.insert_one(instance)
        if logger:
            logger.info(f"[registry] Created instance for '{state_id}': {result.inserted_id}")
    except Exception as exc:
        if logger:
            logger.error(f"[registry] Error creating instance: {exc}")
        return False, f"State created but instance failed: {exc}", state_id

    return True, f"Event '{state_id}' created successfully", state_id


def list_upcoming_events(days_ahead: int = 90) -> List[Dict[str, Any]]:
    """List upcoming events within the next N days."""
    db = get_database()
    instances = db["system_state_instances"]

    now = datetime.utcnow()
    future = now + timedelta(days=days_ahead)

    query = {
        "state_type": "event",
        "start_at": {"$lte": future},
        "end_at": {"$gte": now},
    }

    events = list(instances.find(query).sort("start_at", 1))

    collection = get_system_state_collection()
    for event in events:
        state_id = event.get("state_id")
        if state_id:
            definition = collection.find_one({"state_id": state_id})
            if definition:
                event["label"] = definition.get("label")
                event["effects"] = definition.get("effects")
                event["metadata"] = definition.get("metadata")

    return events


def preview_active_states_at_date(target_date: datetime) -> Dict[str, Any]:
    """Preview which states would be active at a specific date."""
    db = get_database()
    instances = db["system_state_instances"]

    query = {
        "start_at": {"$lte": target_date},
        "end_at": {"$gte": target_date},
    }

    active_instances = list(instances.find(query).sort("priority", -1))

    state_ids = [inst["state_id"] for inst in active_instances if inst.get("state_id")]
    collection = get_system_state_collection()
    definitions = {
        doc["state_id"]: doc
        for doc in collection.find({"state_id": {"$in": state_ids}})
    }

    states = []
    for inst in active_instances:
        state_id = inst.get("state_id")
        if state_id and state_id in definitions:
            states.append({
                "state_id": state_id,
                "state_type": inst.get("state_type"),
                "label": definitions[state_id].get("label"),
                "priority": inst.get("priority"),
                "effects": definitions[state_id].get("effects"),
            })

    merged_effects = {}
    for state in states:
        effects = state.get("effects") or {}
        for key, value in effects.items():
            if key not in merged_effects:
                merged_effects[key] = value

    return {
        "target_date": target_date.isoformat(),
        "active_states": states,
        "merged_effects": merged_effects,
    }


def get_available_event_templates() -> List[Dict[str, Any]]:
    """Get list of available event templates for UI selection."""
    templates = []
    for key, template in APPROVED_EVENT_TEMPLATES.items():
        templates.append({
            "key": key,
            "label": template.get("label_template", key),
            "description": template.get("description", ""),
            "duration_days": template.get("duration_days"),
            "effects": list(template.get("effects", {}).keys()),
            "allowed_overrides": template.get("allowed_overrides", []),
        })
    return templates


def get_event_template(event_key: str) -> Optional[Dict[str, Any]]:
    """Return full template for a key."""
    return APPROVED_EVENT_TEMPLATES.get(event_key)
