"""Conversation FSM State Machine - explicit state tracking for conversational turns.

This module implements the conversation finite state machine described in
docs/states/CONVERSATION_FSM.md, providing explicit state tracking, transition
validation, and telemetry for all conversation flows.

Design Goals:
- Make implicit state transitions explicit
- Enable observability per conversation phase
- Identify stuck or slow states
- Support debugging and error recovery
- Work across all adapters (Discord, Web, CLI)
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """FSM states for a single conversational turn.
    
    States align with docs/states/CONVERSATION_FSM.md.
    """
    
    # Initial state
    IDLE = "idle"  # No active turn; waiting for trigger
    
    # Ingress & routing
    INGRESS = "ingress"  # Message/command received
    GATE = "gate"  # Summon/dismiss and routing checks
    
    # Processing pipeline  
    INTENT_CLASSIFIED = "intent_classified"  # Intent layer selected handler
    POLICY_CHECK = "policy_check"  # Safety and mode constraints evaluated
    CONTEXT_ASSEMBLED = "context_assembled"  # Prompt built with persona/memory/RAG
    
    # Generation
    LLM_CALL = "llm_call"  # LLM invoked with assembled context
    POST_PROCESS = "post_process"  # Length/tone filters, formatting
    
    # Delivery
    DELIVER = "deliver"  # Adapter sends response
    
    # Terminal states
    RECOVER = "recover"  # Fallback messaging on failure
    COMPLETE = "complete"  # Turn finalized
    
    # Early exit states
    IGNORE = "ignore"  # Not summoned / blocked channel
    REFUSE = "refuse"  # Dismissed / user muted / mode blocks


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


@dataclass
class StateTransition:
    """Record of a single state transition."""
    
    from_state: ConversationState
    to_state: ConversationState
    timestamp: datetime
    duration_ms: Optional[float] = None  # Time in previous state
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTurn:
    """Conversation turn with explicit FSM state tracking.
    
    Tracks:
    - Current state
    - State transition history
    - Time-in-state metrics
    - Turn metadata (user, guild, channel, etc.)
    
    Usage:
        turn = ConversationTurn.create(user_id="123", guild_id="456")
        turn.transition_to(ConversationState.INGRESS)
        turn.transition_to(ConversationState.GATE)
        # ... process turn ...
        turn.transition_to(ConversationState.COMPLETE)
        
        # Get metrics
        total_duration = turn.get_total_duration_ms()
        slow_states = turn.get_slow_states(threshold_ms=1000)
    """
    
    # Identity
    turn_id: str
    user_id: str
    guild_id: str
    channel_id: Optional[str] = None
    message: Optional[str] = None
    
    # State tracking
    current_state: ConversationState = ConversationState.IDLE
    state_history: List[StateTransition] = field(default_factory=list)
    state_entered_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    intent: Optional[str] = None
    intent_confidence: Optional[str] = None
    used_rag: bool = False
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Turn metadata (for context)
    platform_state: Dict[str, Any] = field(default_factory=dict)
    guild_config: Dict[str, Any] = field(default_factory=dict)
    user_context: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(
        cls,
        turn_id: str,
        user_id: str,
        guild_id: str,
        channel_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> ConversationTurn:
        """Create a new conversation turn in IDLE state."""
        return cls(
            turn_id=turn_id,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            message=message,
        )
    
    def transition_to(
        self,
        new_state: ConversationState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transition to a new state with validation and telemetry.
        
        Args:
            new_state: Target state
            metadata: Optional metadata about this transition
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        # Validate transition
        if not self._is_valid_transition(self.current_state, new_state):
            raise StateTransitionError(
                f"Invalid transition: {self.current_state.value} → {new_state.value}"
            )
        
        # Calculate duration in previous state
        now = datetime.utcnow()
        duration_ms = (now - self.state_entered_at).total_seconds() * 1000
        
        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            timestamp=now,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        self.state_history.append(transition)
        
        # Update current state
        old_state = self.current_state
        self.current_state = new_state
        self.state_entered_at = now
        
        # Mark completion if terminal state
        if new_state in (ConversationState.COMPLETE, ConversationState.IGNORE, ConversationState.REFUSE):
            self.completed_at = now
        
        # Log transition
        logger.debug(
            f"[FSM] Turn {self.turn_id}: {old_state.value} → {new_state.value} "
            f"({duration_ms:.1f}ms in {old_state.value})"
        )
    
    def _is_valid_transition(
        self,
        from_state: ConversationState,
        to_state: ConversationState,
    ) -> bool:
        """Validate that a state transition is allowed.
        
        Transition rules based on docs/states/CONVERSATION_FSM.md.
        """
        # Define valid transitions (from_state → [allowed_to_states])
        VALID_TRANSITIONS = {
            ConversationState.IDLE: [ConversationState.INGRESS],
            
            ConversationState.INGRESS: [ConversationState.GATE],
            
            ConversationState.GATE: [
                ConversationState.INTENT_CLASSIFIED,
                ConversationState.IGNORE,  # Not summoned / blocked
                ConversationState.REFUSE,  # Dismissed / muted
            ],
            
            ConversationState.INTENT_CLASSIFIED: [ConversationState.POLICY_CHECK],
            
            ConversationState.POLICY_CHECK: [
                ConversationState.CONTEXT_ASSEMBLED,
                ConversationState.REFUSE,  # Safety violation / lockdown
            ],
            
            ConversationState.CONTEXT_ASSEMBLED: [ConversationState.LLM_CALL],
            
            ConversationState.LLM_CALL: [
                ConversationState.POST_PROCESS,
                ConversationState.RECOVER,  # Generation error
            ],
            
            ConversationState.POST_PROCESS: [ConversationState.DELIVER],
            
            ConversationState.DELIVER: [
                ConversationState.COMPLETE,
                ConversationState.RECOVER,  # Delivery error
            ],
            
            ConversationState.RECOVER: [ConversationState.COMPLETE],
            
            # Terminal states can't transition (except for re-entry from COMPLETE to IDLE for new turn)
            ConversationState.COMPLETE: [ConversationState.IDLE],  # Allow reuse
            ConversationState.IGNORE: [],
            ConversationState.REFUSE: [],
        }
        
        allowed_states = VALID_TRANSITIONS.get(from_state, [])
        return to_state in allowed_states
    
    def get_current_state(self) -> ConversationState:
        """Get current FSM state."""
        return self.current_state
    
    def get_time_in_current_state_ms(self) -> float:
        """Get milliseconds spent in current state."""
        return (datetime.utcnow() - self.state_entered_at).total_seconds() * 1000
    
    def get_total_duration_ms(self) -> float:
        """Get total turn duration from creation to completion (or now if incomplete)."""
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.created_at).total_seconds() * 1000
    
    def get_state_durations(self) -> Dict[ConversationState, float]:
        """Get total time spent in each state (milliseconds).
        
        Returns:
            dict: {state: total_ms}
        """
        durations: Dict[ConversationState, float] = {}
        
        for transition in self.state_history:
            if transition.duration_ms is not None:
                state = transition.from_state
                durations[state] = durations.get(state, 0.0) + transition.duration_ms
        
        # Add current state duration if still in progress
        if not self.is_complete():
            current_duration = self.get_time_in_current_state_ms()
            durations[self.current_state] = durations.get(self.current_state, 0.0) + current_duration
        
        return durations
    
    def get_slow_states(self, threshold_ms: float = 1000.0) -> List[tuple[ConversationState, float]]:
        """Get states that exceeded a duration threshold.
        
        Args:
            threshold_ms: Threshold in milliseconds (default: 1000ms)
            
        Returns:
            list: [(state, duration_ms)] sorted by duration descending
        """
        durations = self.get_state_durations()
        slow = [(state, ms) for state, ms in durations.items() if ms > threshold_ms]
        return sorted(slow, key=lambda x: x[1], reverse=True)
    
    def is_complete(self) -> bool:
        """Check if turn has reached a terminal state."""
        return self.current_state in (
            ConversationState.COMPLETE,
            ConversationState.IGNORE,
            ConversationState.REFUSE,
        )
    
    def is_stuck(self, timeout_ms: float = 30000.0) -> bool:
        """Check if turn is stuck (in non-terminal state for too long).
        
        Args:
            timeout_ms: Timeout threshold in milliseconds (default: 30s)
            
        Returns:
            bool: True if stuck
        """
        if self.is_complete():
            return False
        
        time_in_state = self.get_time_in_current_state_ms()
        return time_in_state > timeout_ms
    
    def get_transition_history(self) -> List[StateTransition]:
        """Get full state transition history."""
        return self.state_history.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization/telemetry.
        
        Returns:
            dict: Turn data with state history
        """
        return {
            "turn_id": self.turn_id,
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "current_state": self.current_state.value,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "used_rag": self.used_rag,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_ms": self.get_total_duration_ms(),
            "is_complete": self.is_complete(),
            "is_stuck": self.is_stuck(),
            "state_history": [
                {
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "duration_ms": t.duration_ms,
                    "timestamp": t.timestamp.isoformat(),
                    "metadata": t.metadata,
                }
                for t in self.state_history
            ],
            "state_durations": {
                state.value: ms
                for state, ms in self.get_state_durations().items()
            },
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        status = "complete" if self.is_complete() else "in-progress"
        return (
            f"ConversationTurn(turn_id={self.turn_id}, "
            f"state={self.current_state.value}, "
            f"status={status}, "
            f"duration={self.get_total_duration_ms():.1f}ms)"
        )
