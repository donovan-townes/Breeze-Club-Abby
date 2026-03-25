"""Conversation FSM observability and metrics tracking.

Provides metrics collection and analysis for conversation state machine performance:
- State transition counts
- Time-in-state per phase
- Slow state detection
- Stuck conversation identification
- FSM health metrics
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
from collections import defaultdict
from datetime import datetime, timedelta
import logging

if TYPE_CHECKING:
    from abby_core.llm.conversation_turn import ConversationTurn, ConversationState

logger = logging.getLogger(__name__)


class ConversationMetrics:
    """Aggregate metrics for conversation FSM performance.
    
    Tracks metrics across multiple conversation turns to identify:
    - Average time per state
    - Slowest states
    - Most common state transitions
    - Error recovery patterns
    - Stuck conversation trends
    """
    
    def __init__(self):
        """Initialize metrics collectors."""
        self.state_transition_counts: Dict[tuple, int] = defaultdict(int)
        self.state_durations: Dict[Any, List[float]] = defaultdict(list)
        self.completed_turns: List[Any] = []
        self.stuck_turns: List[Any] = []
        self.error_turns: List[Any] = []
        self.total_turns = 0
        self.collection_started_at = datetime.utcnow()
    
    def record_turn(self, turn: "ConversationTurn") -> None:
        """Record metrics from a completed conversation turn.
        
        Args:
            turn: Completed ConversationTurn to analyze
        """
        from abby_core.llm.conversation_turn import ConversationState
        
        self.total_turns += 1
        
        # Track state transitions
        for transition in turn.get_transition_history():
            key = (transition.from_state, transition.to_state)
            self.state_transition_counts[key] += 1
            
            # Track duration in from_state
            if transition.duration_ms is not None:
                self.state_durations[transition.from_state].append(transition.duration_ms)
        
        # Categorize turn
        if turn.is_complete():
            self.completed_turns.append(turn)
            
            # Check for errors
            if turn.error_message or turn.current_state == ConversationState.RECOVER:
                self.error_turns.append(turn)
        
        if turn.is_stuck():
            self.stuck_turns.append(turn)
            logger.warning(f"[Metrics] Stuck turn detected: {turn.turn_id} in state {turn.current_state.value}")
    
    def get_state_statistics(self, state: "ConversationState") -> Dict[str, Any]:
        """Get statistical metrics for a specific state.
        
        Args:
            state: State to analyze
            
        Returns:
            dict: {
                "count": int,  # Number of times state was entered
                "avg_duration_ms": float,
                "min_duration_ms": float,
                "max_duration_ms": float,
                "p95_duration_ms": float,
            }
        """
        durations = self.state_durations.get(state, [])
        
        if not durations:
            return {
                "count": 0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "p95_duration_ms": 0.0,
            }
        
        sorted_durations = sorted(durations)
        p95_index = int(len(sorted_durations) * 0.95)
        
        return {
            "count": len(durations),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p95_duration_ms": sorted_durations[p95_index] if sorted_durations else 0.0,
        }
    
    def get_slowest_states(self, top_n: int = 5) -> List[tuple["ConversationState", float]]:
        """Get states with highest average duration.
        
        Args:
            top_n: Number of slowest states to return
            
        Returns:
            list: [(state, avg_duration_ms)] sorted by duration descending
        """
        from abby_core.llm.conversation_turn import ConversationState
        
        state_avgs = []
        for state in ConversationState:
            stats = self.get_state_statistics(state)
            if stats["count"] > 0:
                state_avgs.append((state, stats["avg_duration_ms"]))
        
        return sorted(state_avgs, key=lambda x: x[1], reverse=True)[:top_n]
    
    def get_most_common_transitions(self, top_n: int = 10) -> List[tuple[tuple["ConversationState", "ConversationState"], int]]:
        """Get most common state transitions.
        
        Args:
            top_n: Number of transitions to return
            
        Returns:
            list: [((from_state, to_state), count)] sorted by count descending
        """
        return sorted(
            self.state_transition_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
    
    def get_error_rate(self) -> float:
        """Get percentage of turns that had errors.
        
        Returns:
            float: Error rate as percentage (0-100)
        """
        if self.total_turns == 0:
            return 0.0
        return (len(self.error_turns) / self.total_turns) * 100
    
    def get_stuck_rate(self) -> float:
        """Get percentage of turns that got stuck.
        
        Returns:
            float: Stuck rate as percentage (0-100)
        """
        if self.total_turns == 0:
            return 0.0
        return (len(self.stuck_turns) / self.total_turns) * 100
    
    def get_completion_rate(self) -> float:
        """Get percentage of turns that completed successfully.
        
        Returns:
            float: Completion rate as percentage (0-100)
        """
        from abby_core.llm.conversation_turn import ConversationState
        
        if self.total_turns == 0:
            return 0.0
        
        successful_completions = sum(
            1 for turn in self.completed_turns
            if turn.current_state == ConversationState.COMPLETE and not turn.error_message
        )
        return (successful_completions / self.total_turns) * 100
    
    def get_average_turn_duration_ms(self) -> float:
        """Get average total turn duration.
        
        Returns:
            float: Average duration in milliseconds
        """
        if not self.completed_turns:
            return 0.0
        
        total_duration = sum(turn.get_total_duration_ms() for turn in self.completed_turns)
        return total_duration / len(self.completed_turns)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary.
        
        Returns:
            dict: Complete metrics overview
        """
        return {
            "total_turns": self.total_turns,
            "completed_turns": len(self.completed_turns),
            "error_turns": len(self.error_turns),
            "stuck_turns": len(self.stuck_turns),
            "completion_rate": self.get_completion_rate(),
            "error_rate": self.get_error_rate(),
            "stuck_rate": self.get_stuck_rate(),
            "avg_turn_duration_ms": self.get_average_turn_duration_ms(),
            "slowest_states": [
                {"state": state.value, "avg_duration_ms": avg_ms}
                for state, avg_ms in self.get_slowest_states(5)
            ],
            "common_transitions": [
                {
                    "from": from_state.value,
                    "to": to_state.value,
                    "count": count,
                }
                for (from_state, to_state), count in self.get_most_common_transitions(10)
            ],
            "collection_duration_seconds": (
                datetime.utcnow() - self.collection_started_at
            ).total_seconds(),
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.state_transition_counts.clear()
        self.state_durations.clear()
        self.completed_turns.clear()
        self.stuck_turns.clear()
        self.error_turns.clear()
        self.total_turns = 0
        self.collection_started_at = datetime.utcnow()
        logger.info("[Metrics] Conversation metrics reset")


# Global metrics instance
_global_metrics: Optional[ConversationMetrics] = None


def get_conversation_metrics() -> ConversationMetrics:
    """Get or create global conversation metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = ConversationMetrics()
    return _global_metrics


def record_conversation_turn(turn: "ConversationTurn") -> None:
    """Record a conversation turn in global metrics.
    
    Args:
        turn: Completed ConversationTurn to record
    """
    metrics = get_conversation_metrics()
    metrics.record_turn(turn)


def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of global conversation metrics.
    
    Returns:
        dict: Metrics summary
    """
    metrics = get_conversation_metrics()
    return metrics.get_summary()


def reset_metrics() -> None:
    """Reset global conversation metrics."""
    metrics = get_conversation_metrics()
    metrics.reset()
