"""State Activation Service

Orchestrates atomic state transitions with full audit trail.

**Responsibility:**
- Provide service-level API for state activation (vs. low-level system_state.py functions)
- Atomic multi-step transitions with transaction guarantees
- Operator audit trail recording
- Effect validation integration
- State transition coordination
- Consistent error handling and rollback on validation failure

**Design Philosophy:**
- Single source of truth for how states get activated
- All state changes go through this service (not scattered across codebase)
- Returns tuples (result, error_message) for consistent error handling
- Validates before activating (fail-fast)
- Logs at info level for operator visibility
- Integrates with StateValidationService for effect validation

**Typical Usage:**

    service = get_state_activation_service()
    
    # Activate a season
    state_doc, error = service.activate_state(
        "winter-2026",
        operator_id="operator:alice",
        reason="Scheduled seasonal transition"
    )
    
    if error:
        logger.error(f"Cannot activate state: {error}")
        return
    
    logger.info(f"Activated state: {state_doc['state_id']}")

**Thread Safety:**
- Uses MongoDB transactions for atomic state transitions
- Safe for concurrent activation requests (only one will succeed)
- Deactivation and activation are atomic together
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from abby_core.database.collections.system_state import get_collection as get_system_state_coll
from abby_core.database.collections.system_operations import (
    get_collection as get_system_operations_coll,
    mark_operation_completed,
    mark_operation_failed,
)
from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)

# Singleton instance
_state_activation_service: Optional[StateActivationService] = None


def get_state_activation_service() -> StateActivationService:
    """Get or create the StateActivationService singleton."""
    global _state_activation_service
    if _state_activation_service is None:
        _state_activation_service = StateActivationService()
    return _state_activation_service


class StateActivationService:
    """Orchestrate platform state transitions with atomic guarantees."""

    def __init__(self):
        """Initialize the state activation service."""
        self.validation_service = get_state_validation_service()

    def activate_state(
        self,
        state_id: str,
        operator_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Atomically activate a state with full audit trail.

        This is the primary service-level entry point for state activation.
        It replaces scattered activate_state calls with a single coordinated flow.

        **Steps:**
        1. Fetch state definition (validate exists)
        2. Validate state definition (via StateValidationService)
        3. Validate effects (via effects registry)
        4. Create operation record (via system_operations)
        5. Deactivate conflicting states (same type) [atomic]
        6. Activate new state [atomic with step 5]
        7. Return activated state document
        
        **Atomicity Guarantee:**
        Deactivation and activation happen in same MongoDB transaction.
        If either fails, both are rolled back (no partial state).

        **Audit Trail:**
        - operator_id: Who initiated the state change (required)
        - activated_at: When change occurred
        - reason: Why this change was made
        - activated_by: Operator ID (for industry-standard audit trails)

        Args:
            state_id: State to activate (e.g., "winter-2026")
            operator_id: User/system ID performing activation (default: "system:service")
            reason: Reason for activation (for audit trail, optional)

        Returns:
            (state_document, error_message):
                - On success: (state_dict, None)
                - On failure: (None, error_string)
            
            State document includes:
            - state_id, state_type, canon_ref
            - effects (all effects that this state applies)
            - active=True, activated_at, activated_by
            - start_at, end_at (time boundaries)

        Raises:
            None - all errors returned as (None, error_message)

        Example:
            state_doc, error = service.activate_state(
                "winter-2026",
                operator_id="operator:alice",
                reason="Scheduled seasonal transition"
            )
            if error:
                logger.error(f"Failed: {error}")
                return
        """
        # Use system default if no operator specified
        operator_id = operator_id or "system:service"

        # Step 1: Fetch state definition (validate exists) - use collection helper
        collection = get_system_state_coll()
        state = collection.find_one({"state_id": state_id})
        if not state:
            error_msg = f"State not found: {state_id}"
            logger.error(
                f"[❌ state_activation_not_found] "
                f"state_id={state_id} "
                f"operator={operator_id} "
                f"reason={reason}"
            )
            return None, error_msg

        state_type = state.get("state_type")
        if not state_type:
            error_msg = f"State {state_id} missing state_type"
            logger.error(
                f"[❌ state_activation_invalid_definition] "
                f"state_id={state_id} "
                f"missing_field=state_type "
                f"operator={operator_id}"
            )
            return None, error_msg

        # Step 2: Validate state definition (comprehensive checks)
        from abby_core.system.state_validation_service import get_state_validation_service
        from abby_core.system.effects_registry import validate_effects
        
        validation_service = get_state_validation_service()
        is_valid, validation_errors = validation_service.validate_state_definition(state)
        if not is_valid:
            error_msg = f"State definition validation failed: {', '.join(validation_errors[:3])}"
            logger.error(
                f"[❌ state_activation_definition_invalid] "
                f"state_id={state_id} "
                f"type={state_type} "
                f"operator={operator_id} "
                f"error_count={len(validation_errors)} "
                f"first_error={validation_errors[0] if validation_errors else 'unknown'}"
            )
            return None, error_msg

        # Step 3: Validate effects (via registry)
        effects = state.get("effects", {})
        if effects:
            is_valid, validation_message, _ = validate_effects(effects)
            if not is_valid:
                error_msg = f"Effects validation failed: {validation_message}"
                logger.error(
                    f"[❌ state_activation_effects_invalid] "
                    f"state_id={state_id} "
                    f"operator={operator_id} "
                    f"error={validation_message}"
                )
                return None, error_msg
            
            # Additional validation: check persona_overlay against PersonalityManager
            if "persona_overlay" in effects:
                from abby_core.system.state_validation_service import validate_persona_overlay
                persona_value = effects.get("persona_overlay")
                if isinstance(persona_value, str):
                    persona_valid, persona_error = validate_persona_overlay(persona_value)
                    if not persona_valid:
                        error_msg = f"Invalid persona_overlay: {persona_error}"
                        logger.error(
                            f"[❌ state_activation_persona_invalid] "
                            f"state_id={state_id} "
                            f"operator={operator_id} "
                            f"error={persona_error}"
                        )
                        return None, error_msg

        # Step 4: Create operation record (audit trail) - use collection helper
        # This ensures we have a log of who activated what state and when
        try:
            operations_coll = get_system_operations_coll()
            operation_doc = {
                "operation_type": "state_activation",
                "state_id": state_id,
                "state_type": state_type,
                "operator_id": operator_id,
                "reason": reason,
                "timestamp": datetime.utcnow(),
                "status": "pending",  # Will update to "committed" after transaction
            }
            op_result = operations_coll.insert_one(operation_doc)
            operation_id = op_result.inserted_id
            logger.debug(f"[📋] Created operation record: {operation_id}")
        except Exception as e:
            error_msg = f"Failed to create operation record: {str(e)}"
            logger.error(
                f"[❌ state_activation_operation_record_failed] "
                f"state_id={state_id} "
                f"operator={operator_id} "
                f"error={str(e)}"
            )
            return None, error_msg

        # Step 5-6: ATOMIC state transition with transaction (prevents race conditions)
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
                    logger.debug(
                        f"[📋] Deactivated {deactivate_result.modified_count} other "
                        f"{state_type} state(s)"
                    )

                    # Activate target state (with operator audit trail)
                    activate_result = collection.update_one(
                        {"state_id": state_id},
                        {
                            "$set": {
                                "active": True,
                                "activated_at": datetime.utcnow(),
                                "activated_by": operator_id,  # Audit trail
                                "activation_reason": reason,  # Why this change
                            }
                        },
                        session=session
                    )

                    # Transaction commits atomically here
                    if activate_result.modified_count == 0:
                        # State might already be active - treat as no-op success
                        logger.warning(
                            f"[⚠️ state_activation_already_active] "
                            f"state_id={state_id} "
                            f"operator={operator_id} "
                            f"(state may already be active)"
                        )

                    # Update operation record to committed
                    operations_coll.update_one(
                        {"_id": operation_id},
                        {"$set": {"status": "committed"}},
                        session=session
                    )

                    # Fetch updated state document to return
                    activated_state = collection.find_one(
                        {"state_id": state_id},
                        session=session
                    )

                    if activated_state:
                        logger.info(
                            f"[✅ state_activation] SUCCESSFUL "
                            f"state_id={state_id} "
                            f"type={state_type} "
                            f"operator={operator_id} "
                            f"reason={reason} "
                            f"effects_count={len(effects) if effects else 0} "
                            f"[ATOMIC_TRANSACTION_COMMITTED]"
                        )
                        return activated_state, None
                    else:
                        error_msg = "Activated state document not found after activation"
                        logger.error(
                            f"[❌ state_activation_fetch_failed] "
                            f"state_id={state_id} "
                            f"operator={operator_id}"
                        )
                        return None, error_msg

        except Exception as e:
            # Mark operation as failed
            try:
                operations_coll.update_one(
                    {"_id": operation_id},
                    {"$set": {"status": "failed", "error": str(e)}}
                )
            except Exception:
                pass  # Suppress error in error handler

            error_msg = f"Transaction failed: {str(e)}"
            logger.error(
                f"[❌ state_activation_transaction_failed] "
                f"state_id={state_id} "
                f"type={state_type} "
                f"operator={operator_id} "
                f"error={str(e)} "
                f"[TRANSACTION_ROLLED_BACK]"
            )
            return None, error_msg

    def deactivate_state(
        self,
        state_id: str,
        operator_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Atomically deactivate a state.

        Deactivates a state without activating another one.
        Used for mode toggles, temporary overrides, or emergency shutdowns.

        Args:
            state_id: State to deactivate
            operator_id: User/system ID performing deactivation
            reason: Reason for deactivation (for audit trail)

        Returns:
            (state_document, error_message):
                - On success: (state_dict, None) with active=False
                - On failure: (None, error_string)
        """
        operator_id = operator_id or "system:service"

        # Fetch state definition - use collection helper
        collection = get_system_state_coll()
        state = collection.find_one({"state_id": state_id})
        if not state:
            error_msg = f"State not found: {state_id}"
            logger.error(
                f"[❌ state_deactivation_not_found] "
                f"state_id={state_id} "
                f"operator={operator_id}"
            )
            return None, error_msg

        # Create operation record - use collection helper
        try:
            operations_coll = get_system_operations_coll()
            operation_doc = {
                "operation_type": "state_deactivation",
                "state_id": state_id,
                "operator_id": operator_id,
                "reason": reason,
                "timestamp": datetime.utcnow(),
                "status": "pending",
            }
            op_result = operations_coll.insert_one(operation_doc)
            operation_id = op_result.inserted_id
        except Exception as e:
            error_msg = f"Failed to create operation record: {str(e)}"
            logger.error(
                f"[❌ state_deactivation_operation_failed] "
                f"state_id={state_id} "
                f"operator={operator_id} "
                f"error={str(e)}"
            )
            return None, error_msg

        # Deactivate atomically
        try:
            db = get_database()
            with db.client.start_session() as session:
                with session.start_transaction():
                    result = collection.update_one(
                        {"state_id": state_id},
                        {
                            "$set": {
                                "active": False,
                                "deactivated_at": datetime.utcnow(),
                                "deactivated_by": operator_id,
                                "deactivation_reason": reason,
                            }
                        },
                        session=session
                    )

                    if result.modified_count == 0:
                        logger.warning(
                            f"[⚠️ state_deactivation_already_inactive] "
                            f"state_id={state_id} "
                            f"operator={operator_id}"
                        )

                    # Update operation record
                    operations_coll.update_one(
                        {"_id": operation_id},
                        {"$set": {"status": "committed"}},
                        session=session
                    )

                    # Fetch updated state
                    deactivated_state = collection.find_one(
                        {"state_id": state_id},
                        session=session
                    )

                    if deactivated_state:
                        logger.info(
                            f"[✅ state_deactivation] SUCCESSFUL "
                            f"state_id={state_id} "
                            f"operator={operator_id} "
                            f"reason={reason} "
                            f"[ATOMIC_TRANSACTION_COMMITTED]"
                        )
                        return deactivated_state, None
                    else:
                        return None, "Deactivated state document not found"

        except Exception as e:
            # Mark operation as failed
            try:
                operations_coll.update_one(
                    {"_id": operation_id},
                    {"$set": {"status": "failed", "error": str(e)}}
                )
            except Exception:
                pass

            error_msg = f"Transaction failed: {str(e)}"
            logger.error(
                f"[❌ state_deactivation_transaction_failed] "
                f"state_id={state_id} "
                f"operator={operator_id} "
                f"error={str(e)}"
            )
            return None, error_msg
