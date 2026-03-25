"""
ConversationService - Platform-Agnostic Conversation Management

Extracts all conversation session management from Discord, providing a unified
interface for creating, managing, and closing conversation sessions across all
adapters (Discord, Web, CLI, etc.).

Architecture:
    Discord Adapter  ─┐
    Web Adapter      ─┼──→ ConversationService ──→ MongoDB
    CLI Adapter      ─┘

Responsibilities:
- Session lifecycle (create, update, close)
- Message recording (append exchanges)
- Session expiration and cleanup
- Turn count and cooldown tracking
- Session state transitions
- Graceful session closure with summaries
- LLM conversation generation (respond, summarize, analyze)
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List
import logging

from abby_core.database.mongodb import (
    get_sessions_collection,
)
from abby_core.database import session_repository

try:
    from tdos_intelligence.observability import logging as tdos_logging  # type: ignore
    logger = tdos_logging.getLogger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA MODELS
# ════════════════════════════════════════════════════════════════════════════════

class ConversationState(str, Enum):
    """Explicit session lifecycle markers."""
    OPEN = "open"
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    CLOSED = "closed"
    EXPIRED = "expired"


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ════════════════════════════════════════════════════════════════════════════════

_conversation_service: Optional['ConversationService'] = None


def get_conversation_service() -> 'ConversationService':
    """Get or create ConversationService singleton."""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service


# ════════════════════════════════════════════════════════════════════════════════
# MAIN SERVICE CLASS
# ════════════════════════════════════════════════════════════════════════════════

class ConversationService:
    """Platform-agnostic conversation session management.
    
    All methods return (result, error) tuples for consistent error handling:
    - Success: (result_value, None)
    - Failure: (None, error_message_str)
    """

    # ════════════════════════════════════════════════════════════════════════════════
    # SESSION LIFECYCLE
    # ════════════════════════════════════════════════════════════════════════════════

    def create_session(
        self,
        user_id: int | str,
        session_id: str,
        *,
        channel_id: Optional[int | str] = None,
        guild_id: Optional[int | str] = None,
    ) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
        """Create a new conversation session.
        
        Directly creates session in MongoDB without intermediate legacy helpers.
        
        Args:
            user_id: User identifier (int for Discord, str for others)
            session_id: Unique session identifier
            channel_id: Optional channel where conversation started
            guild_id: Optional guild/server identifier
        
        Returns:
            (session_dict, None) on success
            (None, error_message) on failure
        """
        try:
            user_id_str = str(user_id)
            guild_id_str = str(guild_id) if guild_id else None
            channel_id_str = str(channel_id) if channel_id else None
            now = datetime.now(timezone.utc)

            # Create session document directly in MongoDB
            collection = get_sessions_collection()
            session_doc = {
                "user_id": user_id_str,
                "guild_id": guild_id_str,
                "session_id": session_id,
                "channel_id": channel_id_str,
                "interactions": [],
                "summary": None,
                "status": "active",
                "state": ConversationState.ACTIVE.value,
                "turn_count": 0,
                "last_message_at": None,
                "cooldown_until": None,
                "created_at": now,
                "closed_at": None,
            }
            
            result = collection.insert_one(session_doc)
            
            if not result.acknowledged:
                return None, "Failed to create session in MongoDB"
            
            # Return simplified session data to caller
            session_data = {
                "session_id": session_id,
                "user_id": user_id_str,
                "guild_id": guild_id_str,
                "channel_id": channel_id_str,
                "status": "active",
                "state": ConversationState.ACTIVE.value,
                "turn_count": 0,
                "created_at": now.isoformat(),
                "closed_at": None,
            }

            logger.info(
                "session_created",
                extra={"user_id": user_id_str, "session_id": session_id, "guild_id": guild_id_str}
            )
            return session_data, None

        except Exception as e:
            logger.error(f"[❌] Failed to create session: {e}")
            return None, f"Failed to create session: {str(e)}"

    def get_session(
        self,
        user_id: int | str,
        session_id: str,
    ) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
        """Retrieve a session by ID.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
        
        Returns:
            (session_dict, None) on success
            (None, error_message) on failure
        """
        try:
            user_id = str(user_id)
            
            session = session_repository.get_session_by_id(session_id)
            
            if not session or session.get("user_id") != user_id:
                return None, f"Session {session_id} not found for user {user_id}"
            
            return session, None

        except Exception as e:
            logger.error(f"[❌] Failed to get session: {e}")
            return None, f"Failed to retrieve session: {str(e)}"

    def get_active_session(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None,
    ) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
        """Get the active conversation session for a user.
        
        Args:
            user_id: User identifier
            guild_id: Optional guild filter
        
        Returns:
            (session_dict, None) if active session exists
            (None, error_message) otherwise
        """
        try:
            user_id = str(user_id)
            guild_id_str = str(guild_id) if guild_id is not None else None
            
            session = session_repository.get_active_session(user_id, guild_id_str)
            
            if not session:
                return None, "No active session found"
            
            return session, None

        except Exception as e:
            logger.error(f"[❌] Failed to get active session: {e}")
            return None, f"Failed to retrieve active session: {str(e)}"

    def close_session(
        self,
        user_id: int | str,
        session_id: str,
        *,
        summary: Optional[str] = None,
        reason: str = "completed",
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """Close a conversation session.
        
        Directly updates session in MongoDB without intermediate legacy helpers.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            summary: Optional session summary
            reason: Reason for closure (completed, expired, error, etc.)
        
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            user_id_str = str(user_id)
            now = datetime.now(timezone.utc)
            
            # Update session directly in MongoDB
            collection = get_sessions_collection()
            
            update_doc = {
                "state": ConversationState.CLOSED.value,
                "status": reason,
                "closed_at": now,
            }
            
            if summary:
                update_doc["summary"] = summary
            
            result = collection.update_one(
                {"session_id": session_id, "user_id": user_id_str},
                {"$set": update_doc}
            )
            
            if result.matched_count == 0:
                return None, f"Session {session_id} not found for user {user_id_str}"
            
            logger.info(
                "session_closed",
                extra={"user_id": user_id_str, "session_id": session_id, "reason": reason}
            )
            return True, None

        except Exception as e:
            logger.error(f"[❌] Failed to close session: {e}")
            return None, f"Failed to close session: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # MESSAGE RECORDING
    # ════════════════════════════════════════════════════════════════════════════════

    def record_exchange(
        self,
        user_id: int | str,
        session_id: str,
        user_message: str,
        assistant_message: Optional[str] = None,
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """Record a user/assistant exchange in the session.
        
        Directly appends messages to MongoDB without legacy helpers.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            user_message: The user's message
            assistant_message: The assistant's response (optional)
        
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            user_id_str = str(user_id)
            collection = get_sessions_collection()
            now = datetime.now(timezone.utc)
            
            # Build messages to append
            messages = [
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": now,
                }
            ]
            
            if assistant_message is not None:
                messages.append({
                    "role": "assistant",
                    "content": assistant_message,
                    "timestamp": now,
                })
            
            # Append all messages in single operation
            result = collection.update_one(
                {"session_id": session_id, "user_id": user_id_str},
                {"$push": {"interactions": {"$each": messages}}}
            )
            
            if result.matched_count == 0:
                return None, f"Session {session_id} not found for user {user_id_str}"
            
            logger.debug(
                "exchange_recorded",
                extra={"user_id": user_id_str, "session_id": session_id, "message_count": len(messages)}
            )
            return True, None

        except Exception as e:
            logger.error(f"[❌] Failed to record exchange: {e}")
            return None, f"Failed to record exchange: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # SESSION EXPIRATION & CLEANUP
    # ════════════════════════════════════════════════════════════════════════════════

    def expire_active_sessions(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None,
    ) -> Tuple[int, None] | Tuple[None, str]:
        """Mark lingering active sessions as expired for a user.
        
        Used when user starts a new session to expire any old ones.
        
        Args:
            user_id: User identifier
            guild_id: Optional guild filter
        
        Returns:
            (count_expired, None) - number of sessions marked as expired
            (None, error_message) on failure
        """
        try:
            user_id = str(user_id)
            
            collection = get_sessions_collection()
            filter_doc: Dict[str, Any] = {
                "user_id": user_id,
                "status": "active"
            }
            
            if guild_id is not None:
                filter_doc["guild_id"] = str(guild_id)
            
            now = datetime.now(timezone.utc)
            result = collection.update_many(
                filter_doc,
                {
                    "$set": {
                        "status": "expired",
                        "state": ConversationState.EXPIRED.value,
                        "closed_at": now,
                    }
                },
            )
            
            if result.modified_count:
                logger.info(
                    "sessions_expired",
                    extra={"user_id": user_id, "guild_id": str(guild_id) if guild_id else None, "count": result.modified_count, "timestamp": now.isoformat()}
                )
            else:
                logger.info(f"[session_cleanup] No sessions to expire for user {user_id}")
            
            return result.modified_count, None

        except Exception as e:
            logger.error(f"[❌] Failed to expire sessions: {e}")
            return None, f"Failed to expire sessions: {str(e)}"

    def expire_old_sessions(
        self,
        max_age_hours: int = 24,
    ) -> Tuple[int, None] | Tuple[None, str]:
        """Clean up sessions older than max_age_hours that are still open.
        
        Args:
            max_age_hours: Sessions older than this are marked expired (default 24h)
        
        Returns:
            (count_expired, None) - number of sessions marked as expired
            (None, error_message) on failure
        """
        try:
            collection = get_sessions_collection()
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=max_age_hours)
            
            result = collection.update_many(
                {
                    "status": {"$in": ["active", "open"]},
                    "created_at": {"$lt": cutoff}
                },
                {
                    "$set": {
                        "status": "expired",
                        "state": ConversationState.EXPIRED.value,
                        "closed_at": now,
                    }
                },
            )
            
            if result.modified_count:
                logger.info(
                    "old_sessions_expired",
                    extra={"count": result.modified_count, "max_age_hours": max_age_hours}
                )
            
            return result.modified_count, None

        except Exception as e:
            logger.error(f"[❌] Failed to expire old sessions: {e}")
            return None, f"Failed to expire old sessions: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # TURN TRACKING & COOLDOWN
    # ════════════════════════════════════════════════════════════════════════════════

    def increment_turn_count(
        self,
        user_id: int | str,
        session_id: str,
    ) -> Tuple[int, None] | Tuple[None, str]:
        """Increment the turn count for a session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
        
        Returns:
            (new_turn_count, None) on success
            (None, error_message) on failure
        """
        try:
            collection = get_sessions_collection()
            
            result = collection.find_one_and_update(
                {
                    "user_id": str(user_id),
                    "session_id": session_id
                },
                {
                    "$inc": {"turn_count": 1},
                    "$set": {"last_message_at": datetime.now(timezone.utc)}
                },
                return_document=True
            )
            
            if not result:
                return None, f"Session {session_id} not found"
            
            new_turn_count = result.get("turn_count", 0)
            return new_turn_count, None

        except Exception as e:
            logger.error(f"[❌] Failed to increment turn count: {e}")
            return None, f"Failed to increment turn count: {str(e)}"

    def set_cooldown(
        self,
        user_id: int | str,
        session_id: str,
        cooldown_minutes: int,
    ) -> Tuple[bool, None] | Tuple[None, str]:
        """Set a cooldown period for a session (e.g., after hitting turn limit).
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            cooldown_minutes: Cooldown duration in minutes
        
        Returns:
            (True, None) on success
            (None, error_message) on failure
        """
        try:
            collection = get_sessions_collection()
            now = datetime.now(timezone.utc)
            cooldown_until = now + timedelta(minutes=cooldown_minutes)
            
            result = collection.update_one(
                {
                    "user_id": str(user_id),
                    "session_id": session_id
                },
                {
                    "$set": {
                        "state": ConversationState.COOLDOWN.value,
                        "cooldown_until": cooldown_until
                    }
                },
            )
            
            if result.matched_count == 0:
                return None, f"Session {session_id} not found"
            
            logger.debug(
                "cooldown_set",
                extra={"user_id": str(user_id), "session_id": session_id, "minutes": cooldown_minutes}
            )
            return True, None

        except Exception as e:
            logger.error(f"[❌] Failed to set cooldown: {e}")
            return None, f"Failed to set cooldown: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # STATISTICS & QUERIES
    # ════════════════════════════════════════════════════════════════════════════════

    def get_session_stats(
        self,
        user_id: int | str,
        guild_id: Optional[int | str] = None,
    ) -> Tuple[Dict[str, Any], None] | Tuple[None, str]:
        """Get conversation statistics for a user.
        
        Args:
            user_id: User identifier
            guild_id: Optional guild filter
        
        Returns:
            (stats_dict, None) with keys:
                - total_sessions: Total sessions ever created
                - active_sessions: Currently active sessions
                - closed_sessions: Closed/completed sessions
                - expired_sessions: Expired sessions
                - total_exchanges: Total messages recorded
                - avg_session_length: Average session duration
            (None, error_message) on failure
        """
        try:
            user_id = str(user_id)
            collection = get_sessions_collection()
            
            filter_doc = {"user_id": user_id}
            if guild_id is not None:
                filter_doc["guild_id"] = str(guild_id)
            
            # Count by status
            total = collection.count_documents(filter_doc)
            active = collection.count_documents({**filter_doc, "status": "active"})
            closed = collection.count_documents({**filter_doc, "status": "completed"})
            expired = collection.count_documents({**filter_doc, "status": "expired"})
            
            # Approximate total exchanges (rough average)
            sessions = list(collection.find(filter_doc, {"turn_count": 1}))
            total_exchanges = sum(s.get("turn_count", 0) for s in sessions) if sessions else 0
            avg_session_length = total_exchanges / len(sessions) if sessions else 0
            
            stats = {
                "total_sessions": total,
                "active_sessions": active,
                "closed_sessions": closed,
                "expired_sessions": expired,
                "total_exchanges": total_exchanges,
                "avg_session_length": round(avg_session_length, 2),
            }
            
            return stats, None

        except Exception as e:
            logger.error(f"[❌] Failed to get session stats: {e}")
            return None, f"Failed to retrieve statistics: {str(e)}"

    def list_sessions(
        self,
        user_id: int | str,
        status: Optional[str] = None,
        guild_id: Optional[int | str] = None,
        limit: int = 10,
    ) -> Tuple[list, None] | Tuple[None, str]:
        """List sessions for a user.
        
        Args:
            user_id: User identifier
            status: Optional status filter (active, closed, expired, etc.)
            guild_id: Optional guild filter
            limit: Maximum sessions to return (default 10)
        
        Returns:
            (sessions_list, None) on success
            (None, error_message) on failure
        """
        try:
            user_id = str(user_id)
            collection = get_sessions_collection()
            
            filter_doc = {"user_id": user_id}
            if status:
                filter_doc["status"] = status
            if guild_id:
                filter_doc["guild_id"] = str(guild_id)
            
            sessions = list(
                collection.find(filter_doc)
                .sort("created_at", -1)
                .limit(limit)
            )
            
            # Remove MongoDB _id for consistency
            for session in sessions:
                if "_id" in session:
                    del session["_id"]
            
            return sessions, None

        except Exception as e:
            logger.error(f"[❌] Failed to list sessions: {e}")
            return None, f"Failed to list sessions: {str(e)}"

    # ════════════════════════════════════════════════════════════════════════════════
    # LLM CONVERSATION GENERATION
    # ════════════════════════════════════════════════════════════════════════════════

    async def generate_response(
        self,
        user_message: str,
        context: Any,  # ConversationContext from abby_core.llm.context
        *,
        max_retries: int = 3,
        max_tokens: int = 1500,
        operator_id: str = "system:llm",
    ) -> Tuple[str, None] | Tuple[None, str]:
        """Generate LLM response with full conversation context.
        
        Unified entry point for all conversation generation. Wraps internal
        conversation.respond() with consistent error handling pattern.
        
        Args:
            user_message: The user's message to respond to
            context: ConversationContext with persona, history, user profile
            max_retries: Number of retry attempts on failure (default 3)
            max_tokens: Maximum tokens in response (default 1500)
            operator_id: Audit trail identifier (default "system:llm")
        
        Returns:
            (response_text, None) on success
            (None, error_message) on failure
        
        Usage:
            conversation_service = get_conversation_service()
            response, error = await conversation_service.generate_response(
                user_message="Hello!",
                context=context
            )
            if error:
                logger.error(f"Generation failed: {error}")
                return
        """
        try:
            # Import here to avoid circular dependency
            from abby_core.llm.conversation import respond
            
            response = await respond(
                user_message=user_message,
                context=context,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )
            
            # respond() returns string directly, wraps errors internally
            # If we got here, it succeeded (even if fallback message)
            return response, None
            
        except Exception as e:
            logger.error(f"[❌] Conversation generation failed: {e}")
            return None, f"Conversation generation failed: {str(e)}"

    async def generate_summary(
        self,
        chat_session: List[Dict] | str,
        *,
        max_tokens: int = 300,
        max_retries: int = 3,
        operator_id: str = "system:llm",
    ) -> Tuple[str, None] | Tuple[None, str]:
        """Generate summary from chat history.
        
        Unified entry point for summarization operations. Wraps internal
        conversation.summarize() with consistent error handling pattern.
        
        Args:
            chat_session: List of dicts with 'input'/'response' keys, or string
            max_tokens: Maximum tokens in summary (default 300)
            max_retries: Number of retry attempts on failure (default 3)
            operator_id: Audit trail identifier (default "system:llm")
        
        Returns:
            (summary_text, None) on success
            (None, error_message) on failure
        
        Usage:
            conversation_service = get_conversation_service()
            summary, error = await conversation_service.generate_summary(
                chat_session=history
            )
            if error:
                logger.error(f"Summarization failed: {error}")
                return
        """
        try:
            # Import here to avoid circular dependency
            from abby_core.llm.conversation import summarize
            
            summary = await summarize(
                chat_session=chat_session,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )
            
            return summary, None
            
        except Exception as e:
            logger.error(f"[❌] Summarization failed: {e}")
            return None, f"Summarization failed: {str(e)}"

    async def generate_analysis(
        self,
        content: str,
        context: Any,  # ConversationContext from abby_core.llm.context
        *,
        max_tokens: int = 3000,
        max_retries: int = 3,
        operator_id: str = "system:llm",
    ) -> Tuple[str, None] | Tuple[None, str]:
        """Generate detailed analysis with persona-aware feedback.
        
        Unified entry point for content analysis operations. Wraps internal
        conversation.analyze() with consistent error handling pattern.
        
        Args:
            content: Content to analyze (chat history, idea, proposal, etc.)
            context: ConversationContext with persona and user info
            max_tokens: Maximum tokens in analysis (default 3000)
            max_retries: Number of retry attempts on failure (default 3)
            operator_id: Audit trail identifier (default "system:llm")
        
        Returns:
            (analysis_text, None) on success
            (None, error_message) on failure
        
        Usage:
            conversation_service = get_conversation_service()
            analysis, error = await conversation_service.generate_analysis(
                content=proposal,
                context=context
            )
            if error:
                logger.error(f"Analysis failed: {error}")
                return
        """
        try:
            # Import here to avoid circular dependency
            from abby_core.llm.conversation import analyze
            
            analysis = await analyze(
                content=content,
                context=context,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )
            
            return analysis, None
            
        except Exception as e:
            logger.error(f"[❌] Analysis generation failed: {e}")
            return None, f"Analysis generation failed: {str(e)}"
