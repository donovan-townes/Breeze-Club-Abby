"""Turn Manager Adapter - Discord Implementation

Thin wrapper around turn tracking and session management for Discord chatbot.
Extracted from chatbot.py (Phase 2: Architecture Refactoring).

**Responsibility:**
- Session lifecycle management (create, track, close)
- Turn counting and limit enforcement
- Usage gate integration
- Gate result tracking

**Does NOT:**
- Build conversation context (delegated to context_factory)
- Execute LLM calls (delegated to conversation_service)
- Handle Discord-specific I/O (delegated to chatbot cog)

Architecture Benefits:
- Reduces chatbot.py from 1600+ → ~800 lines
- Isolates turn management from Discord API surface
- Testable without Discord mocks
- Reusable across adapters (future: web, CLI)
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging

from abby_core.services.usage_gate_service import get_usage_gate_service
from abby_core.database.session_repository import (
    get_active_session,
    create_session,
)

logger = logging.getLogger(__name__)


@dataclass
class TurnGateResult:
    """Result of turn limit gate check.
    
    Attributes:
        allowed: Whether turn is allowed
        new_turn_count: Turn count after increment (if allowed)
        is_final_turn: Whether this is the last allowed turn
        turn_limit_hit: Whether limit was exceeded
        session_id: Session identifier
    """
    allowed: bool
    new_turn_count: int
    is_final_turn: bool
    turn_limit_hit: bool
    session_id: Optional[str] = None


class TurnManager:
    """Manages turn tracking and session lifecycle for chat adapters.
    
    Provides adapter-agnostic turn management:
    - Session creation and retrieval
    - Atomic turn limit enforcement
    - Turn count tracking
    - Gate result packaging
    """
    
    def __init__(self):
        """Initialize turn manager with usage gate service."""
        self.usage_gate_service = get_usage_gate_service()
    
    def get_or_create_session(
        self,
        user_id: int,
        guild_id: int,
        adapter_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get active session or create new one.
        
        Args:
            user_id: User identifier
            guild_id: Guild identifier
            adapter_context: Optional adapter-specific context (e.g., channel_id)
        
        Returns:
            Session dictionary with session_id, turn_count, etc.
        """
        session = get_active_session(user_id, guild_id)
        
        if not session:
            # Create new session with adapter context
            from datetime import datetime, timezone
            import uuid
            
            context = adapter_context or {}
            session_id = str(uuid.uuid4())
            session_doc = {
                "session_id": session_id,
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "status": "active",
                "turn_count": 0,
                **context
            }
            create_session(session_doc)
            session = session_doc
            logger.info(
                f"[turn_manager] Created new session for user {user_id} "
                f"in guild {guild_id} (session_id={session_id[:8]}...)"
            )
        
        return session
    
    def increment_and_check_turn(
        self,
        session_id: str,
        max_turns: int
    ) -> TurnGateResult:
        """Atomically increment turn count and check limit.
        
        Uses usage_gate_service.increment_and_check_turn_limit() for atomic
        MongoDB operation.
        
        Args:
            session_id: Session identifier
            max_turns: Maximum allowed turns per session
        
        Returns:
            TurnGateResult with allowed status and turn count
        """
        result = self.usage_gate_service.increment_and_check_turn_limit(
            session_id=session_id,
            max_turns=max_turns
        )
        
        # Handle error case (None, error_message)
        if isinstance(result, tuple) and result[0] is None:
            error_msg = result[1]
            logger.error(f"[turn_manager] Turn increment failed: {error_msg}")
            return TurnGateResult(
                allowed=False,
                new_turn_count=0,
                is_final_turn=False,
                turn_limit_hit=True,
                session_id=session_id
            )
        
        # Unpack success result (allowed, new_count, is_final)
        allowed, new_count, is_final = result
        
        return TurnGateResult(
            allowed=allowed,
            new_turn_count=new_count,
            is_final_turn=is_final,
            turn_limit_hit=not allowed,
            session_id=session_id
        )
    
    async def close_session(
        self,
        user_id: int,
        session_id: str,
        reason: str = "completed"
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """Close session gracefully.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            reason: Closure reason (completed, timeout, error, etc.)
        
        Returns:
            (True, None) on success, (None, error_message) on failure
        """
        return await self.usage_gate_service.close_session_gracefully(
            user_id=user_id,
            session_id=session_id,
            reason=reason
        )
    
    def calculate_turn_number(self, chat_history: Optional[list]) -> int:
        """Calculate current turn number from chat history.
        
        Args:
            chat_history: List of previous chat exchanges
        
        Returns:
            Current turn number (1-indexed)
        """
        return len(chat_history) + 1 if chat_history else 1


# Singleton instance for adapter use
_turn_manager: Optional[TurnManager] = None


def get_turn_manager() -> TurnManager:
    """Get singleton turn manager instance.
    
    Returns:
        TurnManager instance
    """
    global _turn_manager
    if _turn_manager is None:
        _turn_manager = TurnManager()
    return _turn_manager
