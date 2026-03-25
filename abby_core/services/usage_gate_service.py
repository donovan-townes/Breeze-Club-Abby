"""
UsageGateService - Platform-Agnostic Rate Limiting & Usage Control

Extracts all conversation usage gating from Discord, providing unified
rate limiting, cooldown, burst protection, and session timeout enforcement
across all adapters (Discord, Web, CLI, etc.).

Architecture:
    Discord Adapter  ─┐
    Web Adapter      ─┼──→ UsageGateService ──→ MongoDB + Guild Config
    CLI Adapter      ─┘

Gate Checks (in order):
1. Session expiration (timeout)
2. Turn count limits
3. Cooldown periods
4. Burst protection

Responsibilities:
- Pre-flight usage gate checks before LLM invocation
- Turn count tracking and limits
- Cooldown management
- Burst protection
- Session timeout enforcement
- Graceful session closure
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import logging

from abby_core.database.mongodb import get_database
from abby_core.database.collections.guild_configuration import get_memory_settings

try:
    from tdos_intelligence.observability import logging as tdos_logging  # type: ignore
    logger = tdos_logging.getLogger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA MODELS
# ════════════════════════════════════════════════════════════════════════════════

class GateFailureReason(str, Enum):
    """Reasons a usage gate check can fail."""
    SESSION_EXPIRED = "session_expired"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    COOLDOWN_ACTIVE = "cooldown_active"
    BURST_LIMIT_HIT = "burst_limit_hit"


class UsageGateResult:
    """Result of a usage gate check with detailed failure information."""

    def __init__(
        self,
        allowed: bool,
        reason: Optional[str] = None,
        response_text: Optional[str] = None,
        session_expired: bool = False,
        turn_limit_hit: bool = False,
        cooldown_active: bool = False,
        burst_limit_hit: bool = False,
        is_final_turn: bool = False,
        remaining_cooldown_seconds: int = 0,
    ):
        self.allowed = allowed
        self.reason = reason
        self.response_text = response_text
        self.session_expired = session_expired
        self.turn_limit_hit = turn_limit_hit
        self.cooldown_active = cooldown_active
        self.burst_limit_hit = burst_limit_hit
        self.is_final_turn = is_final_turn
        self.remaining_cooldown_seconds = remaining_cooldown_seconds

    def __repr__(self) -> str:
        return f"UsageGateResult(allowed={self.allowed}, reason={self.reason}, is_final_turn={self.is_final_turn})"


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_usage_gate_service: Optional['UsageGateService'] = None


def get_usage_gate_service() -> 'UsageGateService':
    """Get or create UsageGateService singleton."""
    global _usage_gate_service
    if _usage_gate_service is None:
        _usage_gate_service = UsageGateService()
    return _usage_gate_service


# ════════════════════════════════════════════════════════════════════════════════
# MAIN SERVICE CLASS
# ════════════════════════════════════════════════════════════════════════════════

class UsageGateService:
    """Platform-agnostic usage rate limiting and conversation gating.
    
    Enforces:
    - Session timeout (max session duration)
    - Turn limits (max exchanges per session)
    - Cooldown periods (enforced pauses)
    - Burst protection (max messages per time window)
    
    All methods return structured results/errors for consistent handling.
    """

    # ════════════════════════════════════════════════════════════════════════════════
    # GATE CHECKING
    # ════════════════════════════════════════════════════════════════════════════════

    async def check_usage_gate(
        self,
        guild_id: int | str,
        user_id: int | str,
        session: Optional[Dict[str, Any]] = None,
        personality_manager: Optional[Any] = None,
    ) -> UsageGateResult:
        """
        Pre-flight usage gate check before context assembly and LLM calls.
        
        Performs 4 gate checks in order:
        1. Session timeout
        2. Turn limit
        3. Cooldown period
        4. Burst protection
        
        Args:
            guild_id: Guild/server identifier
            user_id: User identifier
            session: Active session dict (will fetch if not provided)
            personality_manager: Optional PersonalityManager for response messages
        
        Returns:
            UsageGateResult with allowed status and detailed failure info
        """
        try:
            guild_id = int(guild_id)
            user_id = int(user_id)
            
            # Fetch config for this guild
            guild_config = get_memory_settings(guild_id)
            usage_limits = guild_config.get("usage_limits", {})
            conv_limits = usage_limits.get("conversation", {})
            
            # Get or load session
            if session is None:
                from abby_core.database.session_repository import get_active_session
                session = get_active_session(user_id, guild_id)
            
            if not session:
                # No active session yet — new conversation, always allowed
                return UsageGateResult(allowed=True)
            
            now = datetime.now(timezone.utc)
            
            # ────── GATE 1: Session Timeout ──────
            session_started = session.get("created_at")
            if session_started:
                session_started = self._parse_datetime(session_started)
                
                if session_started:
                    session_age = (now - session_started).total_seconds()
                    session_timeout_seconds = conv_limits.get("session_timeout_seconds", 60)
                    
                    if session_age > session_timeout_seconds:
                        response_text = self._get_gate_message(
                            personality_manager,
                            "session_expired",
                            f"Your conversation has timed out after {int(session_timeout_seconds)}s."
                        )
                        logger.info(
                            f"[⏰] Session timeout for user {user_id} in guild {guild_id} "
                            f"(age: {session_age:.0f}s > {session_timeout_seconds}s)"
                        )
                        return UsageGateResult(
                            allowed=False,
                            reason=GateFailureReason.SESSION_EXPIRED.value,
                            response_text=response_text,
                            session_expired=True,
                        )
            
            # ────── GATE 2: Turn Limit ──────
            max_turns = conv_limits.get("max_turns_per_session", 3)
            turn_count = session.get("turn_count", 0)
            
            # Check if we're on the final turn (turn_count is 0-indexed)
            is_final_turn = (turn_count == max_turns - 1)
            
            if turn_count >= max_turns:
                response_text = self._get_gate_message(
                    personality_manager,
                    "turn_limit_reached",
                    f"You've reached the limit of {max_turns} messages per conversation."
                )
                logger.info(
                    f"[🛑] Turn limit reached for user {user_id} in guild {guild_id} "
                    f"({turn_count}/{max_turns})"
                )
                return UsageGateResult(
                    allowed=False,
                    reason=GateFailureReason.TURN_LIMIT_REACHED.value,
                    response_text=response_text,
                    turn_limit_hit=True,
                )
            
            # ────── GATE 3: Cooldown ──────
            cooldown_until = session.get("cooldown_until")
            if cooldown_until:
                cooldown_until = self._parse_datetime(cooldown_until)
                
                if cooldown_until and now < cooldown_until:
                    remaining_seconds = int((cooldown_until - now).total_seconds())
                    response_text = self._get_gate_message(
                        personality_manager,
                        "cooldown_active",
                        f"Please wait {remaining_seconds} seconds before the next message."
                    )
                    logger.debug(
                        f"[⏱️] Cooldown active for user {user_id} in guild {guild_id} "
                        f"({remaining_seconds}s remaining)"
                    )
                    return UsageGateResult(
                        allowed=False,
                        reason=GateFailureReason.COOLDOWN_ACTIVE.value,
                        response_text=response_text,
                        cooldown_active=True,
                        remaining_cooldown_seconds=remaining_seconds,
                    )
            
            # ────── GATE 4: Burst Protection ──────
            burst_result = self._check_burst_protection(
                session, usage_limits, now, personality_manager
            )
            if burst_result and not burst_result.allowed:
                return burst_result
            
            # All gates passed
            logger.debug(
                f"[✅] User {user_id} in guild {guild_id} passed all gates "
                f"(turn {turn_count}/{max_turns}, final={is_final_turn})"
            )
            return UsageGateResult(allowed=True, is_final_turn=is_final_turn)

        except Exception as e:
            logger.error(f"[❌] Error in check_usage_gate: {e}")
            # On error, allow the request (fail open rather than breaking the bot)
            return UsageGateResult(allowed=True)

    # ════════════════════════════════════════════════════════════════════════════════
    # SESSION UPDATES
    # ════════════════════════════════════════════════════════════════════════════════

    def increment_and_check_turn_limit(
        self,
        session_id: str,
        max_turns: int,
    ) -> Tuple[bool, int, bool] | Tuple[None, str]:
        """
        Atomically increment turn count and check if limit is exceeded.
        
        Uses MongoDB's findOneAndUpdate to ensure turn increment and limit
        check happen atomically, preventing race conditions from parallel requests.
        
        Args:
            session_id: Session identifier
            max_turns: Maximum allowed turns per session
        
        Returns:
            (allowed, new_turn_count, is_final_turn) on success
            (None, error_message) on failure
            
            - allowed: False if limit exceeded, True otherwise
            - new_turn_count: Turn count after increment
            - is_final_turn: True if this was the last allowed turn
        """
        try:
            db = get_database()
            collection = db["chat_sessions"]
            now = datetime.now(timezone.utc)
            
            # Atomic increment with condition: only increment if turn_count < max_turns
            result = collection.find_one_and_update(
                {
                    "session_id": session_id,
                    "turn_count": {"$lt": max_turns}
                },
                {
                    "$inc": {"turn_count": 1},
                    "$set": {"last_message_at": now},
                    "$unset": {"cooldown_until": ""}
                },
                return_document=True  # Return updated document
            )
            
            if not result:
                # Update failed - check if session exists or limit exceeded
                session = collection.find_one({"session_id": session_id})
                if not session:
                    return None, f"Session {session_id} not found"
                
                current_count = session.get("turn_count", 0)
                logger.info(
                    f"[🛑] Turn limit exceeded atomically for session {session_id} "
                    f"({current_count}/{max_turns})"
                )
                return False, current_count, False
            
            # Success - turn incremented atomically
            new_count = result.get("turn_count", 0)
            is_final = (new_count == max_turns)
            
            logger.info(
                f"[usage_gate] ✓ Atomic increment: session={session_id[:8]}... "
                f"turn={new_count}/{max_turns} final={is_final}"
            )
            return True, new_count, is_final
            
        except Exception as e:
            logger.error(f"[❌] Error in atomic turn increment: {e}")
            return None, f"Atomic increment failed: {str(e)}"

    async def update_session_after_turn(
        self,
        user_id: int | str,
        session_id: str,
        increment_turn: bool = True,
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """
        Update session after a successful LLM turn.
        
        DEPRECATED: Use increment_and_check_turn_limit for atomic turn tracking.
        This method is kept for backward compatibility.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            increment_turn: Whether to increment turn count
        
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            db = get_database()
            collection = db["chat_sessions"]
            
            now = datetime.now(timezone.utc)
            
            update_doc: Dict[str, Any] = {
                "$set": {
                    "last_message_at": now,
                }
            }
            
            if increment_turn:
                update_doc["$inc"] = {"turn_count": 1}
            
            # Clear cooldown after successful turn completion
            update_doc["$unset"] = {"cooldown_until": ""}
            
            result = collection.update_one(
                {"session_id": session_id},
                update_doc
            )
            
            if result.matched_count == 0:
                return None, f"Session {session_id} not found"
            
            logger.debug(
                f"[📊] Updated session {session_id} (turn_inc={increment_turn})"
            )
            return True, None

        except Exception as e:
            logger.error(f"[❌] Error updating session {session_id}: {e}")
            return None, f"Failed to update session: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # COOLDOWN MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════════

    async def set_cooldown_on_session(
        self,
        user_id: int | str,
        session_id: str,
        cooldown_seconds: int,
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """
        Set a cooldown period on a session (e.g., during LLM generation).
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            cooldown_seconds: Duration in seconds
        
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            db = get_database()
            collection = db["chat_sessions"]
            
            now = datetime.now(timezone.utc)
            cooldown_until = now + timedelta(seconds=cooldown_seconds)
            
            result = collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "cooldown_until": cooldown_until,
                        "state": "cooldown"
                    }
                }
            )
            
            if result.matched_count == 0:
                return None, f"Session {session_id} not found"
            
            logger.debug(
                f"[⏱️] Set {cooldown_seconds}s cooldown on session {session_id}"
            )
            return True, None

        except Exception as e:
            logger.error(f"[❌] Error setting cooldown: {e}")
            return None, f"Failed to set cooldown: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # SESSION CLOSURE
    # ════════════════════════════════════════════════════════════════════════════════

    async def close_session_gracefully(
        self,
        user_id: int | str,
        session_id: str,
        reason: str = "completed",
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """
        Close a conversation session gracefully.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            reason: Why session is closing (completed, expired, abandoned, etc.)
        
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            db = get_database()
            collection = db["chat_sessions"]
            
            now = datetime.now(timezone.utc)
            
            result = collection.update_one(
                {
                    "session_id": session_id,
                    "status": {"$ne": "completed"}  # Only if not already closed
                },
                {
                    "$set": {
                        "status": reason,
                        "state": "closed",
                        "closed_at": now
                    }
                }
            )
            
            if result.matched_count > 0:
                logger.info(
                    f"[🔒] Closed session {session_id} (reason: {reason})"
                )
                return True, None
            else:
                logger.debug(
                    f"[ℹ️] Session {session_id} already closed or not found"
                )
                return None, "Session already closed"

        except Exception as e:
            logger.error(f"[❌] Error closing session {session_id}: {e}")
            return None, f"Failed to close session: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ════════════════════════════════════════════════════════════════════════════════

    def get_guild_limits(
        self,
        guild_id: int | str,
    ) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
        """
        Get usage limit configuration for a guild.
        
        Returns:
            (limits_dict, None) with keys:
                - conversation: {session_timeout_seconds, max_turns_per_session, cooldown_seconds}
                - burst: {max_messages, window_seconds}
            (None, error_message) on failure
        """
        try:
            guild_id = int(guild_id)
            guild_config = get_memory_settings(guild_id)
            usage_limits = guild_config.get("usage_limits", {})
            
            return usage_limits, None

        except Exception as e:
            logger.error(f"[❌] Error fetching guild limits: {e}")
            return None, f"Failed to fetch guild limits: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════════════════════════

    def _parse_datetime(self, dt_value: Any) -> Optional[datetime]:
        """Parse various datetime formats to timezone-aware UTC datetime."""
        if isinstance(dt_value, datetime):
            if dt_value.tzinfo is None:
                return dt_value.replace(tzinfo=timezone.utc)
            elif dt_value.tzinfo != timezone.utc:
                return dt_value.astimezone(timezone.utc)
            return dt_value
        
        elif isinstance(dt_value, str):
            try:
                dt = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                elif dt.tzinfo != timezone.utc:
                    return dt.astimezone(timezone.utc)
                return dt
            except (ValueError, AttributeError):
                logger.warning(f"[⚠️] Could not parse datetime string: {dt_value}")
                return None
        
        return None

    def _get_gate_message(
        self,
        personality_manager: Optional[Any],
        message_type: str,
        default_message: str,
    ) -> str:
        """Get a gate message from personality manager or use default."""
        if personality_manager:
            try:
                return personality_manager.get_usage_gate_message(message_type)
            except Exception:
                pass
        return default_message

    def _check_burst_protection(
        self,
        session: Dict[str, Any],
        usage_limits: Dict[str, Any],
        now: datetime,
        personality_manager: Optional[Any],
    ) -> Optional[UsageGateResult]:
        """Check burst protection gate (max messages per time window)."""
        try:
            burst_limits = usage_limits.get("burst", {})
            burst_max = burst_limits.get("max_messages", 10)
            burst_window = burst_limits.get("window_seconds", 60)
            
            # Count messages in the last N seconds
            recent_interactions = [
                i for i in session.get("interactions", [])
                if isinstance(i, dict) and "timestamp" in i
            ]
            
            if not recent_interactions:
                return None
            
            last_message_time = recent_interactions[-1].get("timestamp")
            last_message_time = self._parse_datetime(last_message_time)
            
            if not last_message_time:
                return None
            
            burst_age = (now - last_message_time).total_seconds()
            
            if burst_age < burst_window:
                # Count messages in window
                burst_messages = sum(
                    1 for i in recent_interactions
                    if self._parse_datetime(i.get("timestamp")) is not None
                )
                
                if burst_messages >= burst_max:
                    response_text = self._get_gate_message(
                        personality_manager,
                        "burst_limit_hit",
                        f"You're sending messages too quickly. Please slow down."
                    )
                    logger.warning(
                        f"[⚡] Burst limit hit ({burst_messages}/{burst_max} in {burst_window}s)"
                    )
                    return UsageGateResult(
                        allowed=False,
                        reason=GateFailureReason.BURST_LIMIT_HIT.value,
                        response_text=response_text,
                        burst_limit_hit=True,
                    )
            
            return None

        except Exception as e:
            logger.warning(f"[⚠️] Error in burst protection check: {e}")
            return None
