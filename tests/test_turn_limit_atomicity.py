"""
Turn Limit Atomicity Tests

Validates that conversation turn limits enforce fairness under concurrent load.

**Scenario:** Multiple concurrent messages from same user attempt to execute
in parallel before turn limit is checked, potentially bypassing the limit.

**Expected Behavior:** Only one message executes before hitting the turn limit;
others are blocked atomically at MongoDB level.

**Risk (Before Fix):** Two concurrent messages could both pass the pre-increment
check and both execute (doubling turn consumption).

**Mechanism:** TurnManager.increment_and_check_turn() uses MongoDB find_one_and_update()
with atomic increment to prevent race conditions. Turn count incremented BEFORE
LLM invocation ensures serialization.

Run with: pytest tests/test_turn_limit_atomicity.py -v
"""

import pytest
from threading import Thread, Lock, Event
from typing import List, Tuple, Optional, Any, Dict
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import time

from abby_core.services.usage_gate_service import UsageGateService
from abby_core.discord.adapters.turn_manager import TurnManager
from abby_core.database.mongodb import get_database


class TestTurnLimitAtomicity:
    """Test atomic turn limit enforcement under concurrent load."""

    @pytest.fixture
    def usage_gate_service(self):
        """Create UsageGateService instance."""
        return UsageGateService()

    @pytest.fixture
    def test_session(self):
        """Create test session with turn tracking."""
        db = get_database()
        sessions = db["chat_sessions"]
        
        test_session_id = "test-session-concurrent-turns"
        
        # Clean up any existing session
        sessions.delete_one({"session_id": test_session_id})
        
        # Create fresh session
        session_doc = {
            "session_id": test_session_id,
            "user_id": "test-user-turns",
            "guild_id": 123456,
            "turn_count": 0,
            "created_at": datetime.now(timezone.utc),
            "messages": []
        }
        sessions.insert_one(session_doc)
        
        yield test_session_id
        
        # Cleanup
        sessions.delete_one({"session_id": test_session_id})

    def test_single_turn_increments_correctly(self, usage_gate_service, test_session):
        """Test that single turn increment works as baseline."""
        result = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=3
        )
        
        # Result is tuple: (allowed, new_turn_count, is_final_turn)
        assert isinstance(result, tuple), "Should return tuple"
        allowed, turn_count, is_final = result
        
        assert allowed is True, "First turn should be allowed"
        assert turn_count == 1, "Turn count should increment to 1"
        assert is_final is False, "Turn 1 of 3 is not final"

    def test_sequential_turns_increment_atomically(self, usage_gate_service, test_session):
        """Test sequential turns increment one at a time."""
        max_turns = 3
        
        # Turn 1
        result1 = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=max_turns
        )
        allowed1, turn1, final1 = result1
        assert allowed1 is True and turn1 == 1 and final1 is False
        
        # Turn 2
        result2 = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=max_turns
        )
        allowed2, turn2, final2 = result2
        assert allowed2 is True and turn2 == 2 and final2 is False
        
        # Turn 3 (final)
        result3 = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=max_turns
        )
        allowed3, turn3, final3 = result3
        assert allowed3 is True and turn3 == 3 and final3 is True
        
        # Turn 4 (should fail)
        result4 = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=max_turns
        )
        allowed4, turn4, final4 = result4
        assert allowed4 is False, "Turn 4 should exceed limit of 3"

    def test_concurrent_turns_only_one_succeeds(self, usage_gate_service, test_session):
        """Test that only one concurrent turn increments before limit."""
        max_turns = 2
        results = []
        lock = Lock()
        start_event = Event()
        
        def attempt_turn(thread_id: int):
            """Simulate concurrent turn attempt."""
            # Wait for all threads to be ready
            start_event.wait()
            
            # All threads attempt increment simultaneously
            result = usage_gate_service.increment_and_check_turn_limit(
                session_id=test_session,
                max_turns=max_turns
            )
            
            with lock:
                results.append({
                    "thread_id": thread_id,
                    "result": result
                })
        
        # Start 3 threads trying to use turns (max 2)
        threads = []
        for i in range(3):
            t = Thread(target=attempt_turn, args=(i,))
            t.start()
            threads.append(t)
        
        # Give threads time to reach wait point
        time.sleep(0.1)
        
        # Release all threads simultaneously
        start_event.set()
        
        # Wait for all to complete
        for t in threads:
            t.join()
        
        # Sort by turn count to analyze
        results.sort(key=lambda x: x["result"][1])
        
        # Exactly 2 should succeed, 1 should fail
        succeeded = [r for r in results if r["result"][0] is True]
        failed = [r for r in results if r["result"][0] is False]
        
        assert len(succeeded) == 2, f"Exactly 2 turns should succeed, got {len(succeeded)}"
        assert len(failed) == 1, f"Exactly 1 turn should fail, got {len(failed)}"
        
        # Verify turn counts are 1 and 2
        success_turns = sorted([r["result"][1] for r in succeeded])
        assert success_turns == [1, 2], f"Success turns should be [1, 2], got {success_turns}"
        
        # Verify failed turn has turn_count at limit
        failed_turn = failed[0]["result"][1]
        assert failed_turn == max_turns, f"Failed turn count should be {max_turns}, got {failed_turn}"

    def test_concurrent_rapid_fire_respects_limit(self, usage_gate_service, test_session):
        """Test rapid-fire concurrent requests respect atomicity."""
        max_turns = 5
        num_concurrent = 10
        results = []
        lock = Lock()
        
        def rapid_attempt(thread_id: int):
            """Rapid fire turn attempt."""
            result = usage_gate_service.increment_and_check_turn_limit(
                session_id=test_session,
                max_turns=max_turns
            )
            
            with lock:
                results.append({
                    "thread_id": thread_id,
                    "allowed": result[0],
                    "turn_count": result[1]
                })
        
        # Fire 10 concurrent threads against limit of 5
        threads = []
        for i in range(num_concurrent):
            t = Thread(target=rapid_attempt, args=(i,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # Count successes
        succeeded = [r for r in results if r["allowed"] is True]
        failed = [r for r in results if r["allowed"] is False]
        
        # Should have exactly max_turns successes
        assert len(succeeded) == max_turns, \
            f"Should have exactly {max_turns} successes, got {len(succeeded)}"
        assert len(failed) == num_concurrent - max_turns, \
            f"Should have {num_concurrent - max_turns} failures, got {len(failed)}"
        
        # Turn counts should be sequential: 1, 2, 3, 4, 5
        success_turns = sorted([r["turn_count"] for r in succeeded])
        expected = list(range(1, max_turns + 1))
        assert success_turns == expected, \
            f"Success turns should be {expected}, got {success_turns}"
        
        # Failed attempts should all report turn_count >= max_turns
        for fail in failed:
            assert fail["turn_count"] >= max_turns, \
                f"Failed attempt should report turn_count >= {max_turns}, got {fail['turn_count']}"

    def test_turn_limit_with_zero_max_turns(self, usage_gate_service, test_session):
        """Test edge case: max_turns of 0 (no turns allowed)."""
        result = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=0
        )
        
        # With max_turns=0, first increment should still fail
        allowed, turn_count, is_final = result
        assert allowed is False, "With max_turns=0, no turns allowed"

    def test_turn_limit_with_one_turn(self, usage_gate_service, test_session):
        """Test edge case: max_turns of 1 (single turn only)."""
        max_turns = 1
        
        # First turn
        result1 = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=max_turns
        )
        allowed1, turn1, final1 = result1
        assert allowed1 is True, "First turn should succeed"
        assert turn1 == 1, "Turn count should be 1"
        assert final1 is True, "First turn with max_turns=1 is final"
        
        # Second attempt
        result2 = usage_gate_service.increment_and_check_turn_limit(
            session_id=test_session,
            max_turns=max_turns
        )
        allowed2, turn2, final2 = result2
        assert allowed2 is False, "Second turn should fail with max_turns=1"


class TestTurnLimitIsolation:
    """Test turn limit isolation between sessions/users."""

    @pytest.fixture
    def db(self):
        """Get database."""
        return get_database()

    @pytest.fixture
    def usage_gate_service(self):
        """Create UsageGateService instance."""
        return UsageGateService()

    def test_turn_limits_isolated_per_session(self, db, usage_gate_service):
        """Test that turn limits are isolated per session."""
        sessions = db["chat_sessions"]
        max_turns = 2
        
        session_ids = ["test-session-iso-1", "test-session-iso-2"]
        
        # Clean up
        sessions.delete_many({"session_id": {"$in": session_ids}})
        
        # Create sessions
        for sid in session_ids:
            sessions.insert_one({
                "session_id": sid,
                "turn_count": 0,
                "created_at": datetime.now(timezone.utc)
            })
        
        try:
            # Increment first session twice (hits limit)
            for i in range(2):
                result = usage_gate_service.increment_and_check_turn_limit(
                    session_id=session_ids[0],
                    max_turns=max_turns
                )
                assert result[0] is True, f"Session 1 turn {i+1} should succeed"
            
            # Third attempt on first session should fail
            result = usage_gate_service.increment_and_check_turn_limit(
                session_id=session_ids[0],
                max_turns=max_turns
            )
            assert result[0] is False, "Session 1 turn 3 should fail"
            
            # But second session should still allow turns
            result = usage_gate_service.increment_and_check_turn_limit(
                session_id=session_ids[1],
                max_turns=max_turns
            )
            assert result[0] is True, "Session 2 turn 1 should succeed despite session 1 limit"
            
        finally:
            # Cleanup
            sessions.delete_many({"session_id": {"$in": session_ids}})

    def test_turn_count_persists_across_checks(self, db, usage_gate_service):
        """Test that turn count persists in MongoDB across separate calls."""
        sessions = db["chat_sessions"]
        session_id = "test-session-persist"
        max_turns = 3
        
        # Clean up
        sessions.delete_one({"session_id": session_id})
        
        # Create session
        sessions.insert_one({
            "session_id": session_id,
            "turn_count": 0,
            "created_at": datetime.now(timezone.utc)
        })
        
        try:
            # First increment
            result1 = usage_gate_service.increment_and_check_turn_limit(
                session_id=session_id,
                max_turns=max_turns
            )
            assert result1[1] == 1, "First result should show turn_count=1"
            
            # Directly check MongoDB to verify persistence
            session_doc = sessions.find_one({"session_id": session_id})
            assert session_doc is not None, "Session should exist"
            assert session_doc.get("turn_count") == 1, "Turn count should be persisted in MongoDB"
            
            # Second increment (after delay to ensure separate operation)
            time.sleep(0.05)
            result2 = usage_gate_service.increment_and_check_turn_limit(
                session_id=session_id,
                max_turns=max_turns
            )
            assert result2[1] == 2, "Second result should show turn_count=2"
            
            # Verify again in MongoDB
            session_doc = sessions.find_one({"session_id": session_id})
            assert session_doc.get("turn_count") == 2, "Turn count should be updated to 2"
            
        finally:
            sessions.delete_one({"session_id": session_id})
