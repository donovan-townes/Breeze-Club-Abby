"""
System State Management (Canon System for Platform-Wide State)

This module manages the platform's canonical state: seasons, eras, events, and modes.
Everything that affects multiple subsystems (economy, persona, lore) reads from here.

Design Philosophy:
- Single source of truth for what time/era/state the platform is in
- Not guild-configurable; guilds participate in system state
- Time-aware but intentionally managed (not calculated)
- Extensible beyond just seasons
- Drives both operational logic (XP resets) and persona (tone, symbolism)

Key Concepts:
- state_id: Unique identifier (e.g., "winter-2026")
- state_type: Category (season, era, arc, event, mode)
- canon_ref: Link to lore canon (e.g., "lore.lore.season.winter.v1")
- effects: What this state triggers (xp_reset, persona_overlay, tone_shift)
- active: Boolean flag (exactly one state active at a time)
- start_at / end_at: Time boundaries for validation
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


def ensure_state_instance_indexes() -> None:
    """Ensure MongoDB indexes for system state collections (Phase 5).
    
    Creates unique constraint on system_state to prevent duplicate active states
    by type. Prevents orphaned instances and race conditions.
    
    Should be called during bot initialization.
    """
    try:
        db = get_database()
        state_coll = db["system_state"]
        
        # Unique index: Only one active state per type
        state_coll.create_index(
            [("state_type", 1), ("active", 1)],
            unique=True,
            partialFilterExpression={"active": True},
            name="unique_active_per_type"
        )
        
        # Index for state lookups by type
        state_coll.create_index([("state_type", 1)], name="idx_state_type")
        
        logger.info("[✓] system_state indexes created/verified")
    except Exception as e:
        logger.warning(f"[⚠️] Could not create indexes: {e}")


# ==================== COLLECTION ACCESS ====================

def get_system_state_collection():
    """Get the system_state collection from configured database (respects dev/prod)."""
    db = get_database()
    return db["system_state"]


# ==================== STATE QUERIES ====================

def get_active_state(state_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the currently active system state.
    
    Args:
        state_type: If provided, filter to this type (e.g., "season", "era")
    
    Returns:
        dict: Active state document or None if not found
    
    Example:
        state = get_active_state("season")
        # Returns: {
        #     "state_id": "winter-2026",
        #     "state_type": "season",
        #     ...
        # }
    """
    collection = get_system_state_collection()
    query: Dict[str, Any] = {"active": True}
    if state_type:
        query["state_type"] = state_type
    
    return collection.find_one(query)


def get_state_by_id(state_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific state by ID, regardless of active status."""
    collection = get_system_state_collection()
    return collection.find_one({"state_id": state_id})


def get_active_season() -> Optional[Dict[str, Any]]:
    """Convenience method: get active season state."""
    return get_active_state("season")


def get_season_for_date(date_obj: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Get the season that covers a specific date.
    
    This is useful for historical lookups or validation.
    Only returns states whose time boundaries cover the date.
    """
    if date_obj is None:
        date_obj = datetime.utcnow()
    
    collection = get_system_state_collection()
    
    # Find all season states where date falls within boundaries
    result = collection.find_one({
        "state_type": "season",
        "start_at": {"$lte": date_obj},
        "end_at": {"$gte": date_obj}
    })
    
    return result


def list_all_states(state_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all states, optionally filtered by type."""
    collection = get_system_state_collection()
    query = {}
    if state_type:
        query["state_type"] = state_type
    
    return list(collection.find(query).sort("start_at", -1))


# ==================== STATE TRANSITIONS ====================

def activate_state(state_id: str, operator_id: Optional[str] = None) -> bool:
    """Activate a state and deactivate others of the same type.
    
    This is the primary way to transition to a new state (e.g., season change).
    
    **Industry-Standard Audit Trail:**
    All activations logged with operator_id (who made the decision).
    This ensures accountability and observability in production.
    
    Args:
        state_id: The state to activate
        operator_id: User/system ID activating this state (for audit trail)
    
    Returns:
        bool: True if successful
    
    Side effects:
        1. Validates state definition and effects before activation
        2. Sets active=True on the target state
        3. Sets active=False on all other states of the same type
        4. Records activation timestamp and operator_id
        5. Emits activation event with operator context
    """
    from abby_core.system.effects_registry import validate_effects
    from abby_core.system.state_validation_service import get_state_validation_service
    from abby_core.system.effects_merger import merge_effects
    
    operator_id = operator_id or "system:scheduler"
    collection = get_system_state_collection()
    
    # Get the state we're activating
    state = get_state_by_id(state_id)
    if not state:
        logger.error(
            f"[❌] State not found: {state_id} operator={operator_id}"
        )
        return False
    
    state_type = state.get("state_type")
    
    # Phase 1: Comprehensive state validation before activation
    validation_service = get_state_validation_service()
    is_valid, validation_errors = validation_service.validate_state_definition(state)
    if not is_valid:
        logger.error(
            f"[❌] Cannot activate state {state_id}: State definition validation failed: "
            f"{len(validation_errors)} error(s) "
            f"operator={operator_id} "
            f"first_error='{validation_errors[0] if validation_errors else 'unknown'}'"
        )
        for err in validation_errors:
            logger.debug(f"  - {err}")
        return False
    logger.debug(f"[✓] State definition validated for {state_id}")
    
    # Validate effects before allowing activation (with operator context)
    effects = state.get("effects", {})
    if effects:
        is_valid, validation_message, _ = validate_effects(effects)
        if not is_valid:
            logger.error(
                f"[❌] Cannot activate state {state_id}: {validation_message} "
                f"operator={operator_id}"
            )
            return False
        logger.debug(f"[✓] Effects validated for state {state_id}")
        
        # Phase 5 hardening: Strict effects validation with warnings
        from abby_core.system.effects_validation_service import get_effects_validation_service
        validation_service = get_effects_validation_service()
        is_valid, strict_errors = validation_service.validate_merged_effects_strict(effects, state_id)
        if not is_valid:
            logger.error(
                f"[❌] Cannot activate state {state_id}: Strict validation failed "
                f"({len(strict_errors)} error(s)) operator={operator_id}"
            )
            for err in strict_errors:
                logger.debug(f"  - {err}")
            return False
    
    # Phase 2: ATOMIC state transition with transaction (prevents race conditions)
    # Both deactivate and activate must succeed or both must fail
    try:
        db = get_database()
        with db.client.start_session() as session:
            with session.start_transaction():
                # Deactivate other states of the same type
                deactivate_result = collection.update_many(
                    {"state_type": state_type, "state_id": {"$ne": state_id}},
                    {
                        "$set": {
                            "active": False,
                            "deactivated_at": datetime.utcnow(),
                            "deactivated_by": operator_id,
                        }
                    },
                    session=session
                )
                logger.info(
                    f"[📋] Deactivated {deactivate_result.modified_count} other {state_type} state(s) "
                    f"operator={operator_id}"
                )
                
                # Activate target state (with operator audit trail)
                activate_result = collection.update_one(
                    {"state_id": state_id},
                    {
                        "$set": {
                            "active": True,
                            "activated_at": datetime.utcnow(),
                            "activated_by": operator_id,  # Industry-standard: track who activated
                        }
                    },
                    session=session
                )
                
                # Transaction commits atomically here
                if activate_result.modified_count > 0:
                    logger.info(
                        f"[✅ state_activation] SUCCESSFUL "
                        f"state_id={state_id} "
                        f"type={state_type} "
                        f"operator={operator_id} "
                        f"effects_count={len(effects) if effects else 0} "
                        f"[ATOMIC_TRANSACTION_COMMITTED]"
                    )
                    return True
                else:
                    logger.warning(
                        f"[⚠️ state_activation] No state modified (already active?) "
                        f"state_id={state_id} operator={operator_id}"
                    )
                    return False
    except Exception as e:
        logger.error(
            f"[❌ state_activation_transaction_failed] "
            f"state_id={state_id} "
            f"type={state_type} "
            f"operator={operator_id} "
            f"error={str(e)} "
            f"[TRANSACTION_ROLLED_BACK]"
        )
        return False


def deactivate_state(state_id: str, operator_id: Optional[str] = None) -> bool:
    """Deactivate a specific state.
    
    Used primarily for event end handling when an event's time window expires.
    
    Args:
        state_id: The state to deactivate
        operator_id: User/system ID deactivating this state (for audit trail)
    
    Returns:
        bool: True if successful
    """
    operator_id = operator_id or "system:scheduler"
    collection = get_system_state_collection()
    
    # Get the state we're deactivating
    state = get_state_by_id(state_id)
    if not state:
        logger.error(f"[❌] State not found: {state_id} operator={operator_id}")
        return False
    
    state_type = state.get("state_type")
    is_active = state.get("active", False)
    
    if not is_active:
        logger.warning(f"[⚠️] State {state_id} is already inactive operator={operator_id}")
        return True  # Success (idempotent)
    
    try:
        result = collection.update_one(
            {"state_id": state_id},
            {
                "$set": {
                    "active": False,
                    "deactivated_at": datetime.utcnow(),
                    "deactivated_by": operator_id,
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(
                f"[✅ state_deactivation] SUCCESSFUL "
                f"state_id={state_id} "
                f"type={state_type} "
                f"operator={operator_id}"
            )
            return True
        else:
            logger.warning(f"[⚠️] No state modified for deactivation: {state_id}")
            return False
            
    except Exception as e:
        logger.error(
            f"[❌ state_deactivation_failed] "
            f"state_id={state_id} "
            f"operator={operator_id} "
            f"error={str(e)}"
        )
        return False


# ==================== STATE INITIALIZATION ====================

def initialize_state(
    state_id: str,
    state_type: str,
    key: str,
    label: str,
    canon_ref: str,
    start_at: datetime,
    end_at: datetime,
    effects: Dict[str, bool],
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create a new system state document.
    
    This is typically called during database setup or when adding new states.
    
    Args:
        state_id: Unique identifier (e.g., "winter-2026")
        state_type: Type of state (season, era, arc, event, mode)
        key: Short key for programmatic use (e.g., "winter")
        label: Human-readable label (e.g., "Winter 2026")
        canon_ref: Reference to canonical lore (e.g., "lore.lore.season.winter.v1")
        start_at: When this state begins
        end_at: When this state ends
        effects: Dict of effects this state triggers (e.g., {"xp_reset": True})
        metadata: Optional additional metadata
    
    Returns:
        bool: True if successful
    """
    collection = get_system_state_collection()
    
    state_doc = {
        "state_id": state_id,
        "state_type": state_type,
        "key": key,
        "label": label,
        "canon_ref": canon_ref,
        "active": False,
        "start_at": start_at,
        "end_at": end_at,
        "effects": effects,
        "created_at": datetime.utcnow(),
        "activated_at": None,
        "activated_by": None,
        "metadata": metadata or {}
    }
    
    try:
        collection.insert_one(state_doc)
        logger.info(f"[✅] Created state: {state_id} ({state_type})")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to create state {state_id}: {e}")
        return False


# ==================== PREDEFINED SEASONS (2026-2027) ====================

def initialize_predefined_seasons():
    """Create the canonical season schedule for 2026-2027.
    
    This defines the authoritative season boundaries and their effects.
    
    Schedule (aligned with astronomical seasons):
    - Winter: Dec 21 – Mar 19 (theme: reflection, gathering, warmth)
    - Spring: Mar 20 – Jun 20 (theme: renewal, growth, awakening)
    - Summer: Jun 21 – Sep 21 (theme: abundance, expansion, energy)
    - Fall: Sep 22 – Dec 20 (theme: harvest, change, preparation)
    
    All seasons:
    - Trigger XP reset
    - Enable persona overlay
    - Shift tone and symbolism
    """
    collection = get_system_state_collection()
    
    seasons = [
        {
            "state_id": "winter-2026",
            "state_type": "season",
            "key": "winter",
            "label": "Winter 2026",
            "canon_ref": "lore.lore.season.winter.v1",
            "start_at": datetime(2025, 12, 21, 0, 0, 0),
            "end_at": datetime(2026, 3, 19, 23, 59, 59),
            "effects": {
                "xp_reset": True,
                "persona_overlay": True,
                "tone_shift": True
            }
        },
        {
            "state_id": "spring-2026",
            "state_type": "season",
            "key": "spring",
            "label": "Spring 2026",
            "canon_ref": "lore.lore.season.spring.v1",
            "start_at": datetime(2026, 3, 20, 0, 0, 0),
            "end_at": datetime(2026, 6, 20, 23, 59, 59),
            "effects": {
                "xp_reset": True,
                "persona_overlay": True,
                "tone_shift": True
            }
        },
        {
            "state_id": "summer-2026",
            "state_type": "season",
            "key": "summer",
            "label": "Summer 2026",
            "canon_ref": "lore.lore.season.summer.v1",
            "start_at": datetime(2026, 6, 21, 0, 0, 0),
            "end_at": datetime(2026, 9, 21, 23, 59, 59),
            "effects": {
                "xp_reset": True,
                "persona_overlay": True,
                "tone_shift": True
            }
        },
        {
            "state_id": "fall-2026",
            "state_type": "season",
            "key": "fall",
            "label": "Fall 2026",
            "canon_ref": "lore.lore.season.fall.v1",
            "start_at": datetime(2026, 9, 22, 0, 0, 0),
            "end_at": datetime(2026, 12, 20, 23, 59, 59),
            "effects": {
                "xp_reset": True,
                "persona_overlay": True,
                "tone_shift": True
            }
        }
    ]
    
    for season_data in seasons:
        # Check if season already exists
        existing = collection.find_one({"state_id": season_data["state_id"]})
        if existing:
            logger.debug(f"[📋] Season already exists: {season_data['state_id']}")
            continue
        
        # Create season
        season_data["active"] = False
        season_data["created_at"] = datetime.utcnow()
        season_data["activated_at"] = None
        season_data["activated_by"] = None
        season_data["metadata"] = {}
        
        collection.insert_one(season_data)
        logger.info(f"[✅] Created season: {season_data['state_id']}")


# ==================== HELPERS ====================

def get_state_description(state: Dict[str, Any]) -> str:
    """Generate a user-friendly description of a state."""
    label = state.get("label", "Unknown")
    state_type = state.get("state_type", "state")
    canon_ref = state.get("canon_ref", "")
    
    return f"{label} (type: {state_type}, canon: {canon_ref})"


def ensure_canonical_state():
    """Ensure at least one active season exists.
    
    This is a safety check to prevent undefined state.
    Called during initialization and can be used as a recovery mechanism.
    """
    active_season = get_active_season()
    
    if active_season:
        logger.debug(f"[✅] Active season verified: {active_season.get('state_id')}")
        return True
    
    logger.warning("[⚠️] No active season found. Activating Winter 2026...")
    
    # Try to activate Winter 2026
    winter = get_state_by_id("winter-2026")
    if not winter:
        logger.error("[❌] Winter 2026 not found in database. Run initialize_predefined_seasons first.")
        return False
    
    return activate_state("winter-2026")


# ==================== EFFECTS INTERPRETER ====================

def should_reset_xp_this_season() -> bool:
    """Check if current active season triggers XP reset.
    
    Returns True if active season has xp_reset effect enabled.
    """
    state = get_active_state("season")
    if not state:
        return False
    
    effects = state.get("effects", {})
    return effects.get("xp_reset", False)


def get_persona_overlays() -> Dict[str, Any]:
    """Get all active persona overlays from system state.
    
    Returns a dict of overlay rules that persona assembly should apply.
    Example:
        {
            "tone_domain": "season",
            "tone_slot": "mood",
            "tone_values": {...},
            "mood_theme": "winter"
        }
    """
    state = get_active_state("season")
    if not state:
        return {}
    
    effects = state.get("effects", {})
    if not effects.get("persona_overlay"):
        return {}
    
    label = state.get("label")
    label_lower = label.lower() if isinstance(label, str) else "neutral"
    
    return {
        "tone_domain": "season",
        "tone_slot": "mood",
        "season_key": state.get("key"),
        "season_canon_ref": state.get("canon_ref"),
        "mood_theme": label_lower
    }
