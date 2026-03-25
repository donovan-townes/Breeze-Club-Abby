"""Unit tests for Conversation FSM state machine.
"""

import pytest
from datetime import datetime, timedelta
from abby_core.llm.conversation_turn import (
    ConversationState,
    StateTransition,
    ConversationTurn,
    StateTransitionError,
)
from abby_core.observability.conversation_metrics import (
    ConversationMetrics,
    get_conversation_metrics,
)


# Global metrics reset function (stub for tests)
def reset_metrics():
    """Reset global conversation metrics counters.
    
    In production, this would reset metrics in abby_core.observability.conversation_metrics.
    For tests, this is a no-op stub.
    """
    pass


# Test fixtures
@pytest.fixture
def reset_global_metrics():
    """Reset global conversation metrics before each test."""
    reset_metrics()
    yield
    reset_metrics()


def test_conversation_fsm():
    pass


class TestConversationState:
    """Test ConversationState enum."""
    
    def test_all_states_exist(self):
        """Verify all required FSM states are defined."""
        expected_states = {
            "idle",
            "ingress",
            "gate",
            "intent_classified",
            "policy_check",
            "context_assembled",
            "llm_call",
            "post_process",
            "deliver",
            "recover",
            "complete",
            "ignore",
            "refuse",
        }
        
        actual_states = {state.value for state in ConversationState}
        assert actual_states == expected_states


class TestStateTransition:
    """Test StateTransition dataclass."""
    
    def test_create_transition(self):
        """Test creating a state transition."""
        transition = StateTransition(
            from_state=ConversationState.IDLE,
            to_state=ConversationState.INGRESS,
            timestamp=datetime.utcnow(),
            duration_ms=10.5,
            metadata={"test": "data"},
        )
        
        assert transition.from_state == ConversationState.IDLE
        assert transition.to_state == ConversationState.INGRESS
        assert transition.duration_ms == 10.5
        assert transition.metadata == {"test": "data"}


class TestConversationTurn:
    """Test ConversationTurn state machine."""
    
    def test_create_turn(self):
        """Test creating a conversation turn."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Hello, bot!",
        )
        
        assert turn.turn_id == "test-123"
        assert turn.user_id == "user-456"
        assert turn.guild_id == "guild-789"
        assert turn.channel_id == "channel-abc"
        assert turn.message == "Hello, bot!"
        assert turn.current_state == ConversationState.IDLE
        assert turn.created_at is not None
        assert turn.get_transition_history() == []
    
    def test_valid_transition(self):
        """Test valid state transition."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # IDLE → INGRESS is valid
        turn.transition_to(ConversationState.INGRESS, {"source": "test"})
        
        assert turn.current_state == ConversationState.INGRESS
        assert len(turn.get_transition_history()) == 1
        
        transition = turn.get_transition_history()[0]
        assert transition.from_state == ConversationState.IDLE
        assert transition.to_state == ConversationState.INGRESS
        assert transition.metadata == {"source": "test"}
    
    def test_invalid_transition(self):
        """Test invalid state transition raises error."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # IDLE → COMPLETE is invalid (must go through pipeline)
        with pytest.raises(ValueError, match="Invalid transition"):
            turn.transition_to(ConversationState.COMPLETE, {})
    
    def test_transition_sequence(self):
        """Test complete valid transition sequence."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # Happy path: IDLE → INGRESS → GATE → INTENT → POLICY → CONTEXT → LLM → POST → DELIVER → COMPLETE
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.GATE)
        turn.transition_to(ConversationState.INTENT_CLASSIFIED)
        turn.transition_to(ConversationState.POLICY_CHECK)
        turn.transition_to(ConversationState.CONTEXT_ASSEMBLED)
        turn.transition_to(ConversationState.LLM_CALL)
        turn.transition_to(ConversationState.POST_PROCESS)
        turn.transition_to(ConversationState.DELIVER)
        turn.transition_to(ConversationState.COMPLETE)
        
        assert turn.current_state == ConversationState.COMPLETE
        assert len(turn.get_transition_history()) == 9
    
    def test_early_exit_ignore(self):
        """Test early exit to IGNORE state."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # IDLE → INGRESS → GATE → IGNORE
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.GATE)
        turn.transition_to(ConversationState.IGNORE, {"reason": "bot_message"})
        
        assert turn.current_state == ConversationState.IGNORE
        assert turn.is_complete()
    
    def test_early_exit_refuse(self):
        """Test early exit to REFUSE state."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # IDLE → INGRESS → GATE → INTENT → POLICY → REFUSE
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.GATE)
        turn.transition_to(ConversationState.INTENT_CLASSIFIED)
        turn.transition_to(ConversationState.POLICY_CHECK)
        turn.transition_to(ConversationState.REFUSE, {"reason": "policy_violation"})
        
        assert turn.current_state == ConversationState.REFUSE
        assert turn.is_complete()
    
    def test_error_recovery(self):
        """Test error recovery through RECOVER state."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # IDLE → INGRESS → GATE → INTENT → POLICY → CONTEXT → LLM → RECOVER → COMPLETE
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.GATE)
        turn.transition_to(ConversationState.INTENT_CLASSIFIED)
        turn.transition_to(ConversationState.POLICY_CHECK)
        turn.transition_to(ConversationState.CONTEXT_ASSEMBLED)
        turn.transition_to(ConversationState.LLM_CALL)
        turn.transition_to(ConversationState.RECOVER, {"error": "LLM timeout"})
        turn.transition_to(ConversationState.COMPLETE, {"recovered": True})
        
        assert turn.current_state == ConversationState.COMPLETE
        assert turn.is_complete()
    
    def test_get_state_durations(self):
        """Test state duration calculation."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # Perform transitions
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.GATE)
        turn.transition_to(ConversationState.COMPLETE)
        
        durations = turn.get_state_durations()
        
        assert ConversationState.IDLE.value in durations
        assert ConversationState.INGRESS.value in durations
        assert ConversationState.GATE.value in durations
        
        # All durations should be non-negative
        for duration in durations.values():
            assert duration >= 0
    
    def test_get_slow_states(self):
        """Test slow state detection."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # Manually add transitions with durations
        turn.state_history.append(
            StateTransition(
                from_state=ConversationState.IDLE,
                to_state=ConversationState.INGRESS,
                timestamp=datetime.utcnow(),
                duration_ms=10.0,
                metadata={},
            )
        )
        turn.state_history.append(
            StateTransition(
                from_state=ConversationState.INGRESS,
                to_state=ConversationState.GATE,
                timestamp=datetime.utcnow(),
                duration_ms=600.0,  # Slow!
                metadata={},
            )
        )
        
        slow_states = turn.get_slow_states(threshold_ms=500.0)
        
        assert len(slow_states) == 1
        assert slow_states[0][0] == ConversationState.INGRESS
        assert slow_states[0][1] == 600.0
    
    def test_is_stuck(self):
        """Test stuck conversation detection."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        # New turn is not stuck
        assert not turn.is_stuck()
        
        # Simulate old turn by backdating created_at
        turn.created_at = datetime.utcnow() - timedelta(seconds=35)
        
        # Turn stuck for >30s (30000ms)
        assert turn.is_stuck(timeout_ms=30000.0)
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.COMPLETE)
        
        data = turn.to_dict()
        
        assert data["turn_id"] == "test-123"
        assert data["user_id"] == "user-456"
        assert data["current_state"] == ConversationState.COMPLETE.value
        assert "transitions" in data
        assert len(data["transitions"]) == 2
        assert "state_durations" in data
        assert "total_duration_ms" in data


class TestConversationMetrics:
    """Test ConversationMetrics aggregation."""
    
    @pytest.fixture(autouse=True)
    def reset_global_metrics(self):
        """Reset global metrics before each test."""
        reset_metrics()
        yield
        reset_metrics()
    
    def test_create_metrics(self):
        """Test creating metrics instance."""
        metrics = ConversationMetrics()
        
        assert metrics.total_turns == 0
        assert len(metrics.completed_turns) == 0
        assert len(metrics.stuck_turns) == 0
        assert len(metrics.error_turns) == 0
    
    def test_record_turn(self):
        """Test recording a conversation turn."""
        metrics = ConversationMetrics()
        
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.COMPLETE)
        
        metrics.record_turn(turn)
        
        assert metrics.total_turns == 1
        assert len(metrics.completed_turns) == 1
    
    def test_record_error_turn(self):
        """Test recording error turn."""
        metrics = ConversationMetrics()
        
        turn = ConversationTurn(
            turn_id="test-123",
            user_id="user-456",
            guild_id="guild-789",
            channel_id="channel-abc",
            message="Test",
        )
        
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.RECOVER)
        turn.error_message = "Test error"
        turn.transition_to(ConversationState.COMPLETE)
        
        metrics.record_turn(turn)
        
        assert metrics.total_turns == 1
        assert len(metrics.error_turns) == 1
    
    def test_state_statistics(self):
        """Test state statistics calculation."""
        metrics = ConversationMetrics()
        
        turn1 = ConversationTurn("t1", "u1", "g1", "c1", "Test")
        turn1.state_history.append(
            StateTransition(
                from_state=ConversationState.IDLE,
                to_state=ConversationState.INGRESS,
                timestamp=datetime.utcnow(),
                duration_ms=100.0,
                metadata={},
            )
        )
        
        turn2 = ConversationTurn("t2", "u2", "g2", "c2", "Test")
        turn2.state_history.append(
            StateTransition(
                from_state=ConversationState.IDLE,
                to_state=ConversationState.INGRESS,
                timestamp=datetime.utcnow(),
                duration_ms=200.0,
                metadata={},
            )
        )
        
        metrics.record_turn(turn1)
        metrics.record_turn(turn2)
        
        stats = metrics.get_state_statistics(ConversationState.IDLE)
        
        assert stats["count"] == 2
        assert stats["avg_duration_ms"] == 150.0
        assert stats["min_duration_ms"] == 100.0
        assert stats["max_duration_ms"] == 200.0
    
    def test_slowest_states(self):
        """Test slowest states identification."""
        metrics = ConversationMetrics()
        
        turn = ConversationTurn("t1", "u1", "g1", "c1", "Test")
        turn.state_history.extend([
            StateTransition(
                ConversationState.IDLE,
                ConversationState.INGRESS,
                datetime.utcnow(),
                100.0,
                {},
            ),
            StateTransition(
                ConversationState.INGRESS,
                ConversationState.GATE,
                datetime.utcnow(),
                500.0,
                {},
            ),
            StateTransition(
                ConversationState.GATE,
                ConversationState.COMPLETE,
                datetime.utcnow(),
                50.0,
                {},
            ),
        ])
        
        metrics.record_turn(turn)
        
        slowest = metrics.get_slowest_states(top_n=2)
        
        assert len(slowest) == 2
        assert slowest[0][0] == ConversationState.INGRESS
        assert slowest[0][1] == 500.0
    
    def test_error_rate(self):
        """Test error rate calculation."""
        metrics = ConversationMetrics()
        
        # 1 successful turn
        turn1 = ConversationTurn("t1", "u1", "g1", "c1", "Test")
        turn1.transition_to(ConversationState.INGRESS)
        turn1.transition_to(ConversationState.COMPLETE)
        metrics.record_turn(turn1)
        
        # 1 error turn
        turn2 = ConversationTurn("t2", "u2", "g2", "c2", "Test")
        turn2.transition_to(ConversationState.INGRESS)
        turn2.transition_to(ConversationState.RECOVER)
        turn2.error_message = "Error"
        turn2.transition_to(ConversationState.COMPLETE)
        metrics.record_turn(turn2)
        
        assert metrics.get_error_rate() == 50.0
    
    def test_completion_rate(self):
        """Test completion rate calculation."""
        metrics = ConversationMetrics()
        
        # 2 successful completions
        for i in range(2):
            turn = ConversationTurn(f"t{i}", "u1", "g1", "c1", "Test")
            turn.transition_to(ConversationState.INGRESS)
            turn.transition_to(ConversationState.COMPLETE)
            metrics.record_turn(turn)
        
        # 1 ignore
        turn = ConversationTurn("t3", "u3", "g3", "c3", "Test")
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.IGNORE)
        metrics.record_turn(turn)
        
        # 2/3 = 66.67% completion
        assert 66.0 < metrics.get_completion_rate() < 67.0
    
    def test_metrics_summary(self):
        """Test complete metrics summary."""
        metrics = ConversationMetrics()
        
        turn = ConversationTurn("t1", "u1", "g1", "c1", "Test")
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.COMPLETE)
        metrics.record_turn(turn)
        
        summary = metrics.get_summary()
        
        assert "total_turns" in summary
        assert "completion_rate" in summary
        assert "error_rate" in summary
        assert "slowest_states" in summary
        assert "common_transitions" in summary
        assert summary["total_turns"] == 1
    
    def test_global_metrics(self):
        """Test global metrics singleton."""
        metrics1 = get_conversation_metrics()
        metrics2 = get_conversation_metrics()
        
        # Same instance
        assert metrics1 is metrics2
        
        # Record turn in one
        turn = ConversationTurn("t1", "u1", "g1", "c1", "Test")
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.COMPLETE)
        record_conversation_turn(turn)
        
        # Visible in other
        assert metrics2.total_turns == 1
