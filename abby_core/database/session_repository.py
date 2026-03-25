"""Shared session repository to break circular dependencies.

Extracted session queries from conversation_service.py and usage_gate_service.py
to provide a neutral data access layer for both services.

Architecture Benefit:
- Breaks circular dependency: usage_gate ↔ conversation_service
- Single source of truth for session queries
- Testable, mockable data access
- Both services use shared repository (no imports between them)

Previous Architecture (Circular Risk):
    usage_gate_service.py → conversation_service.py → [potential circle]
    
New Architecture (Decoupled):
    usage_gate_service.py ↘
                           session_repository.py (shared)
    conversation_service.py ↗
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from abby_core.database.mongodb import get_sessions_collection

logger = logging.getLogger(__name__)


def get_active_session(user_id: int | str, guild_id: Optional[int | str] = None) -> Optional[Dict[str, Any]]:
    """Get active session for user in guild.
    
    Args:
        user_id: User identifier
        guild_id: Optional guild identifier (None for DMs)
        
    Returns:
        Active session document or None if no active session exists
    """
    try:
        collection = get_sessions_collection()
        query = {
            "user_id": str(user_id),
            "status": "active"
        }
        if guild_id is not None:
            query["guild_id"] = str(guild_id)
        
        logger.debug(f"[session_repo] Querying active session: user_id={user_id}, guild_id={guild_id}, query={query}")
        session = collection.find_one(query)
        logger.debug(f"[session_repo] Query result: {'found' if session else 'not found'}")
        
        if session and "_id" in session:
            del session["_id"]
        return session
    except Exception as exc:
        logger.error(f"[session_repo] Error fetching active session for user {user_id}: {exc}")
        return None


def get_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session by session ID.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session document or None if not found
    """
    try:
        collection = get_sessions_collection()
        session = collection.find_one({"session_id": session_id})
        if session and "_id" in session:
            del session["_id"]
        return session
    except Exception as exc:
        logger.error(f"[session_repo] Error fetching session {session_id}: {exc}")
        return None


def count_active_sessions(user_id: int | str, guild_id: Optional[int | str] = None) -> int:
    """Count active sessions for user in guild.
    
    Args:
        user_id: User identifier
        guild_id: Optional guild identifier
        
    Returns:
        Number of active sessions
    """
    try:
        collection = get_sessions_collection()
        query = {
            "user_id": str(user_id),
            "status": "active"
        }
        if guild_id is not None:
            query["guild_id"] = str(guild_id)
        
        return collection.count_documents(query)
    except Exception as exc:
        logger.error(f"[session_repo] Error counting sessions for user {user_id}: {exc}")
        return 0


def find_expired_sessions(before: datetime, limit: int = 100) -> List[Dict[str, Any]]:
    """Find sessions that expired before a given timestamp.
    
    Args:
        before: Timestamp threshold (sessions updated before this are expired)
        limit: Maximum sessions to return
        
    Returns:
        List of expired session documents
    """
    try:
        collection = get_sessions_collection()
        query = {
            "status": "active",
            "last_interaction_at": {"$lt": before}
        }
        return list(collection.find(query).limit(limit))
    except Exception as exc:
        logger.error(f"[session_repo] Error finding expired sessions: {exc}")
        return []


def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
    """Update session fields.
    
    Args:
        session_id: Session identifier
        updates: Dictionary of fields to update
        
    Returns:
        True if updated successfully, False otherwise
    """
    try:
        collection = get_sessions_collection()
        logger.debug(f"[session_repo] Using collection: {collection.name} in database: {collection.database.name}")
        query = {"session_id": session_id}
        logger.debug(f"[session_repo] Attempting update with query: {query}")
        
        exists = collection.find_one(query)
        logger.debug(f"[session_repo] Session exists before update: {'yes' if exists else 'NO'}")
        if exists:
            logger.debug(f"[session_repo] Existing session_id in DB: {exists.get('session_id')}")
        
        result = collection.update_one(query, {"$set": updates})
        logger.debug(f"[session_repo] Updated session {session_id}: matched={result.matched_count}, modified={result.modified_count}, updates={updates}")
        return result.modified_count > 0
    except Exception as exc:
        logger.error(f"[session_repo] Error updating session {session_id}: {exc}")
        return False


def create_session(session_doc: Dict[str, Any]) -> bool:
    """Create a new session document.
    
    Args:
        session_doc: Complete session document to insert
        
    Returns:
        True if created successfully, False otherwise
    """
    try:
        collection = get_sessions_collection()
        collection.insert_one(session_doc)
        return True
    except Exception as exc:
        logger.error(f"[session_repo] Error creating session: {exc}")
        return False


def close_session(session_id: str, close_reason: str = "normal") -> bool:
    """Close a session by updating its status.
    
    Args:
        session_id: Session identifier
        close_reason: Reason for closure (normal, timeout, error, etc.)
        
    Returns:
        True if closed successfully, False otherwise
    """
    try:
        collection = get_sessions_collection()
        result = collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.utcnow(),
                    "close_reason": close_reason
                }
            }
        )
        return result.modified_count > 0
    except Exception as exc:
        logger.error(f"[session_repo] Error closing session {session_id}: {exc}")
        return False
