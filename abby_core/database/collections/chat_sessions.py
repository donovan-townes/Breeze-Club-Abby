"""
Chat Sessions Collection Module

Purpose: Store user conversation sessions with auto-cleanup
Schema: See schemas.py (ChatSessionSchema)
Indexes: session_id (unique), user_id+guild_id, created_at (TTL)

Manages:
- Conversation history
- Session metadata
- User message context
- Auto-expiration after 7 days
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# COLLECTION ACCESS (Singleton Pattern)
# ═══════════════════════════════════════════════════════════════

def get_collection() -> "Collection[Dict[str, Any]]":
    """Get chat_sessions collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["chat_sessions"]


# ═══════════════════════════════════════════════════════════════
# INDEXES
# ═══════════════════════════════════════════════════════════════

def ensure_indexes():
    """Create indexes for chat_sessions collection."""
    try:
        collection = get_collection()

        # Primary queries
        collection.create_index([("session_id", 1)], unique=True)
        collection.create_index([("user_id", 1), ("guild_id", 1), ("status", 1)])
        collection.create_index([("user_id", 1), ("created_at", -1)])

        # TTL index: Auto-delete sessions after 7 days
        collection.create_index([("created_at", 1)], expireAfterSeconds=604800)

        logger.debug("[chat_sessions] Indexes created (with 7-day TTL)")

    except Exception as e:
        logger.warning(f"[chat_sessions] Error creating indexes: {e}")


# ═══════════════════════════════════════════════════════════════
# DEFAULTS / SEEDING
# ═══════════════════════════════════════════════════════════════

def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        collection = get_collection()

        # Sessions are created on-demand, no system defaults
        logger.debug("[chat_sessions] No defaults to seed (on-demand creation)")
        return True

    except Exception as e:
        logger.error(f"[chat_sessions] Error seeding: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════

def initialize_collection() -> bool:
    """
    Initialize chat_sessions collection.

    Called automatically at platform startup.

    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_indexes()
        seed_defaults()

        logger.debug("[chat_sessions] Collection initialized")
        return True

    except Exception as e:
        logger.error(f"[chat_sessions] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_session(session_id: str, user_id: int, guild_id: int) -> bool:
    """Create a new chat session."""
    try:
        collection = get_collection()
        
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "guild_id": guild_id,
            "status": "active",
            "messages": [],
            "metadata": {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        }
        
        collection.insert_one(session)
        logger.debug(f"[chat_sessions] Created session {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"[chat_sessions] Error creating session: {e}")
        return False


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific session."""
    try:
        collection = get_collection()
        return collection.find_one({"session_id": session_id})
    except Exception as e:
        logger.error(f"[chat_sessions] Error getting session {session_id}: {e}")
        return None


def add_message(session_id: str, message: Dict[str, Any]) -> bool:
    """Add a message to a session."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},
                "$set": {"metadata.updated_at": datetime.utcnow()}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[chat_sessions] Session {session_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[chat_sessions] Error adding message to {session_id}: {e}")
        return False


def get_active_session(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get the active session for a user in a guild."""
    try:
        collection = get_collection()
        return collection.find_one(
            {"user_id": user_id, "guild_id": guild_id, "status": "active"},
            sort=[("metadata.created_at", -1)]
        )
    except Exception as e:
        logger.error(f"[chat_sessions] Error getting active session: {e}")
        return None


def close_session(session_id: str) -> bool:
    """Close (end) a session."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"session_id": session_id},
            {"$set": {"status": "closed", "metadata.updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[chat_sessions] Session {session_id} not found")
            return False
            
        logger.debug(f"[chat_sessions] Closed session {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"[chat_sessions] Error closing session {session_id}: {e}")
        return False


def get_recent_sessions(user_id: str, guild_id: Optional[str], limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent sessions for a user (optionally scoped to a guild)."""
    try:
        collection = get_collection()
        query: Dict[str, Any] = {"user_id": str(user_id)}
        if guild_id:
            query["guild_id"] = str(guild_id)

        return list(collection.find(query).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[chat_sessions] Error getting recent sessions for {user_id}: {e}")
        return []


def count_sessions(user_id: str, guild_id: Optional[str]) -> int:
    """Return total session count for a user (optionally scoped to a guild)."""
    try:
        collection = get_collection()
        query: Dict[str, Any] = {"user_id": str(user_id)}
        if guild_id:
            query["guild_id"] = str(guild_id)
        return collection.count_documents(query)
    except Exception as e:
        logger.error(f"[chat_sessions] Error counting sessions for {user_id}: {e}")
        return 0


def get_guild_session_stats(guild_id: str) -> Dict[str, int]:
    """Return total sessions and total messages for a guild."""
    try:
        collection = get_collection()
        query = {"guild_id": str(guild_id)}
        total_sessions = collection.count_documents(query)

        pipeline = [
            {"$match": query},
            {"$project": {"message_count": {"$size": {"$ifNull": ["$messages", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$message_count"}}}
        ]
        result = list(collection.aggregate(pipeline))
        total_messages = result[0].get("total", 0) if result else 0

        return {"total_sessions": total_sessions, "total_messages": total_messages}
    except Exception as e:
        logger.error(f"[chat_sessions] Error getting guild session stats: {e}")
        return {"total_sessions": 0, "total_messages": 0}


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class ChatSessions(CollectionModule):
    """Collection module for chat_sessions - follows foolproof pattern."""
    
    collection_name = "chat_sessions"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get chat_sessions collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not ChatSessions.collection_name:
            raise RuntimeError("collection_name not set for ChatSessions")
        db = get_database()
        return db[ChatSessions.collection_name]
    
    @staticmethod
    def ensure_indexes():
        """Create all indexes for efficient querying."""
        ensure_indexes()
    
    @staticmethod
    def seed_defaults() -> bool:
        """Seed default data if needed."""
        return seed_defaults()
    
    @staticmethod
    def initialize_collection() -> bool:
        """Orchestrate initialization."""
        return initialize_collection()
