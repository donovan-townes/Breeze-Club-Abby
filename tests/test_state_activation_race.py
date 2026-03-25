"""
Concurrent State Activation Race Condition Tests

Validates atomic state transitions prevent race conditions in multi-instance
deployments where multiple scheduler/operator processes try to activate states
simultaneously.

**Scenario:** Two operators simultaneously try to activate different states of
the same type (e.g., season change during concurrent API calls).

**Expected Behavior:** Only one state becomes active; the other fails.
Both see consistent view of which state is active.

**Risk (Before Fix):** Both states marked active, causing state confusion.

Run with: pytest tests/test_state_activation_race.py -v
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from threading import Thread, Lock, Event

from abby_core.system.system_state import activate_state, get_active_state, initialize_state
from abby_core.database.mongodb import get_database


class TestStateActivationAtomicity:
    """Test atomic state activation with transaction guarantees."""
    
    @pytest.fixture
    def test_states(self):
        """Create test states for concurrent activation."""
        db = get_database()
        collection = db["system_state"]
        
        # Clean up test states
        collection.delete_many({"state_id": {"$in": ["test-season-a", "test-season-b", "test-season-c"]}})
        
        # Create test states
        now = datetime.now(timezone.utc)
        
        for state_id in ["test-season-a", "test-season-b", "test-season-c"]:
            collection.insert_one({
                "state_id": state_id,
                "state_type": "season",
                "key": state_id.split("-")[2],
                "label": f"Test Season {state_id}",
                "canon_ref": f"lore.test.{state_id}",
                "start_at": now,
                "end_at": datetime(2027, 1, 1),
                "effects": {},
                "active": False,
                "created_at": now,
            })
        
        yield ["test-season-a", "test-season-b", "test-season-c"]
        
        # Cleanup
        collection.delete_many({"state_id": {"$in": ["test-season-a", "test-season-b", "test-season-c"]}})
    
    def test_single_activation_succeeds(self, test_states):
        """Verify single state activation works correctly."""
        result = activate_state("test-season-a", operator_id="operator:test-1")
        
        assert result is True, "State activation should succeed"
        
        db = get_database()
        collection = db["system_state"]
        
        # Verify state is now active
        active_state = collection.find_one({"state_id": "test-season-a", "active": True})
        assert active_state is not None, "Activated state should be marked active"
        assert active_state.get("activated_by") == "operator:test-1", "Operator should be recorded"
    
    def test_activation_deactivates_previous(self, test_states):
        """Verify activating a new state deactivates the previous one."""
        # Activate first state
        activate_state("test-season-a", operator_id="operator:test-1")
        
        db = get_database()
        collection = db["system_state"]
        
        # Verify A is active
        state_a_active = collection.find_one({"state_id": "test-season-a", "active": True})
        assert state_a_active is not None, "State A should be active"
        
        # Activate second state
        activate_state("test-season-b", operator_id="operator:test-2")
        
        # Verify B is now active and A is inactive
        state_a_inactive = collection.find_one({"state_id": "test-season-a", "active": False})
        state_b_active = collection.find_one({"state_id": "test-season-b", "active": True})
        
        assert state_a_inactive is not None, "State A should be deactivated"
        assert state_b_active is not None, "State B should be active"
        assert state_b_active.get("deactivated_by") is None, "State B should not have deactivated_by"
        assert state_a_inactive.get("deactivated_by") == "operator:test-2", "Deactivation should record operator"
    
    def test_concurrent_activation_atomic(self, test_states):
        """Test concurrent activation attempts - only one should succeed (atomic).
        
        Simulates two operators trying to activate different states simultaneously.
        With atomic transactions, only one succeeds; the other sees consistent state.
        """
        results = {}
        lock = Lock()
        
        def activate_in_thread(state_id: str, operator_id: str):
            """Activate state and record result."""
            try:
                result = activate_state(state_id, operator_id=operator_id)
                with lock:
                    results[operator_id] = (state_id, result)
            except Exception as e:
                with lock:
                    results[operator_id] = (state_id, f"error: {str(e)}")
        
        # Create two threads trying to activate different states
        thread_a = Thread(target=activate_in_thread, args=("test-season-a", "operator:thread-a"))
        thread_b = Thread(target=activate_in_thread, args=("test-season-b", "operator:thread-b"))
        
        # Start both threads (may interleave)
        thread_a.start()
        thread_b.start()
        
        # Wait for both to complete
        thread_a.join(timeout=5)
        thread_b.join(timeout=5)
        
        # Both should have completed
        assert "operator:thread-a" in results, "Thread A should complete"
        assert "operator:thread-b" in results, "Thread B should complete"
        
        # Verify exactly one is active (not both)
        db = get_database()
        collection = db["system_state"]
        
        active_count = collection.count_documents({
            "state_id": {"$in": ["test-season-a", "test-season-b"]},
            "active": True
        })
        
        assert active_count == 1, f"Exactly one state should be active, found {active_count}"
        
        # Get the active state
        active_state = collection.find_one({
            "state_id": {"$in": ["test-season-a", "test-season-b"]},
            "active": True
        })
        
        assert active_state is not None, "Should have one active state"
        
        # Verify the inactive state is marked inactive
        inactive = collection.find_one({
            "state_id": {"$in": ["test-season-a", "test-season-b"]},
            "active": False
        })
        
        assert inactive is not None, "Other state should be inactive"
        assert inactive.get("deactivated_by") in ["operator:thread-a", "operator:thread-b"], \
            "Deactivation should have correct operator"
    
    def test_activation_with_invalid_state_fails(self, test_states):
        """Verify activation of non-existent state fails gracefully."""
        result = activate_state("non-existent-state", operator_id="operator:test")
        
        assert result is False, "Activation should fail for non-existent state"
        
        # No state should be marked active as result of failed activation
        db = get_database()
        collection = db["system_state"]
        
        active = collection.find_one({"state_id": "non-existent-state", "active": True})
        assert active is None, "Non-existent state should not be active"
    
    def test_activation_records_operator_audit_trail(self, test_states):
        """Verify activation records operator ID for audit trail."""
        activate_state("test-season-a", operator_id="operator:audit-test")
        
        db = get_database()
        collection = db["system_state"]
        
        state = collection.find_one({"state_id": "test-season-a", "active": True})
        
        assert state is not None and state.get("activated_by") == "operator:audit-test", "Operator should be recorded"
        assert state is not None and "activated_at" in state, "Activation timestamp should be recorded"
        assert state is not None and state.get("activated_at") is not None, "Activation timestamp should not be null"
    
    def test_sequential_activations_atomic(self, test_states):
        """Test sequence of activations - each is atomic."""
        # Activate A
        result_a = activate_state("test-season-a", operator_id="operator:1")
        assert result_a is True, "First activation should succeed"
        
        db = get_database()
        collection = db["system_state"]
        
        active_a = collection.find_one({"state_id": "test-season-a", "active": True})
        assert active_a is not None, "A should be active"
        
        # Activate B (should deactivate A atomically)
        result_b = activate_state("test-season-b", operator_id="operator:2")
        assert result_b is True, "Second activation should succeed"
        
        # Verify state: A inactive, B active
        state_a = collection.find_one({"state_id": "test-season-a"})
        state_b = collection.find_one({"state_id": "test-season-b"})
        
        assert state_a is not None and state_a.get("active") is False, "A should be inactive"
        assert state_b is not None and state_b.get("active") is True, "B should be active"
        assert state_a is not None and state_a.get("deactivated_by") == "operator:2", "Deactivation should record operator"
        
        # Activate C (should deactivate B atomically)
        result_c = activate_state("test-season-c", operator_id="operator:3")
        assert result_c is True, "Third activation should succeed"
        
        # Verify state: A inactive, B inactive, C active
        state_a = collection.find_one({"state_id": "test-season-a"})
        state_b = collection.find_one({"state_id": "test-season-b"})
        state_c = collection.find_one({"state_id": "test-season-c"})
        
        assert state_a is not None and state_a.get("active") is False, "A should still be inactive"
        assert state_b is not None and state_b.get("active") is False, "B should be deactivated"
        assert state_c is not None and state_c.get("active") is True, "C should be active"
        assert state_b is not None and state_b.get("deactivated_by") == "operator:3", "B deactivation should record operator:3"
    
    def test_transaction_rollback_on_validation_error(self, test_states):
        """Verify transaction rolls back if validation fails.
        
        If a state has invalid effects, the entire activation should fail.
        No state should be left in inconsistent state.
        """
        db = get_database()
        collection = db["system_state"]
        
        # Create a state with invalid effects
        invalid_state_id = "test-season-invalid"
        collection.insert_one({
            "state_id": invalid_state_id,
            "state_type": "season",
            "key": "invalid",
            "label": "Invalid Season",
            "canon_ref": "lore.test.invalid",
            "start_at": datetime.now(timezone.utc),
            "end_at": datetime(2027, 1, 1),
            "effects": {
                "invalid_effect_key": {"nested": "invalid"}  # Invalid effect
            },
            "active": False,
            "created_at": datetime.now(timezone.utc),
        })
        
        # Try to activate invalid state
        result = activate_state(invalid_state_id, operator_id="operator:test")
        
        # Should fail
        assert result is False, "Activation should fail for invalid state"
        
        # Verify state is not active
        invalid = collection.find_one({"state_id": invalid_state_id, "active": True})
        assert invalid is None, "Invalid state should not be active"
        
        # Verify other states still have correct active status
        state_a = collection.find_one({"state_id": "test-season-a"})
        assert state_a is not None, "Other states should be unaffected"
        
        # Cleanup
        collection.delete_one({"state_id": invalid_state_id})


class TestStateActivationIndependence:
    """Test that different state types are activated independently."""
    
    def test_different_state_types_independent(self):
        """Verify activating one state type doesn't affect other types."""
        db = get_database()
        collection = db["system_state"]
        
        # Clean up
        collection.delete_many({"state_id": {"$in": ["test-event-1", "test-event-2"]}})
        
        # Create test event states (different type from season)
        now = datetime.now(timezone.utc)
        for state_id in ["test-event-1", "test-event-2"]:
            collection.insert_one({
                "state_id": state_id,
                "state_type": "event",
                "key": state_id.split("-")[2],
                "label": f"Test Event {state_id}",
                "canon_ref": f"lore.test.{state_id}",
                "start_at": now,
                "end_at": datetime(2027, 1, 1),
                "effects": {},
                "active": False,
                "created_at": now,
            })
        
        # Activate event-1
        activate_state("test-event-1", operator_id="operator:test")
        
        # Verify event-1 is active, event-2 is not
        event_1 = collection.find_one({"state_id": "test-event-1"})
        event_2 = collection.find_one({"state_id": "test-event-2"})
        
        assert event_1 is not None and event_1.get("active") is True, "Event-1 should be active"
        assert event_2 is not None and event_2.get("active") is False, "Event-2 should be inactive"
        
        # Cleanup
        collection.delete_many({"state_id": {"$in": ["test-event-1", "test-event-2"]}})
