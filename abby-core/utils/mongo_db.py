"""
Unified MongoDB Client for Abby (TDOS v1.5 Compliant)

This module provides a tenant-aware MongoDB client for the unified Abby database.
All operations enforce tenant_id scoping per TDOS v1.5 invariants.

Collections:
- users: Discord user profiles + LLM preferences
- sessions: Chat sessions with encrypted messages
- xp: Experience/level tracking
- economy: Wallet/bank balances + transactions
- submissions: User submissions (demos, images, text)
- rag_documents: RAG corpus documents with embeddings

Design principles:
- Single database ("Abby") with 6 collections
- All documents include tenant_id field
- Connection pooling via MongoClient singleton
- Encryption for sensitive data (sessions.messages)
- Proper indexes for tenant-scoped queries
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv
from utils.log_config import logging, setup_logging

setup_logging()
logger = logging.getLogger(__name__)
load_dotenv()

# Singleton MongoDB client
_mongo_client: Optional[MongoClient] = None
_current_tenant_id: str = os.getenv("TDOS_TENANT_ID", "TENANT:BREEZE_CLUB")


def get_mongo_client() -> MongoClient:
    """
    Get or create MongoDB client singleton.
    
    Returns:
        MongoClient instance with connection pooling
    
    Raises:
        ConnectionFailure: If MongoDB connection fails
    """
    global _mongo_client
    
    if _mongo_client is None:
        mongodb_uri = os.getenv("MONGODB_URI")
        
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable not set")
        
        try:
            _mongo_client = MongoClient(
                mongodb_uri,
                server_api=ServerApi('1'),
                maxPoolSize=50,
                minPoolSize=10,
                connectTimeoutMS=5000,
                serverSelectionTimeoutMS=5000,
            )
            
            # Test connection
            _mongo_client.admin.command('ping')
            logger.info("[MongoDB] Connected successfully")
        
        except ConnectionFailure as e:
            logger.error(f"[MongoDB] Connection failed: {e}")
            raise
    
    return _mongo_client


def get_database():
    """
    Get unified Abby database.
    
    Returns:
        Database instance
    """
    client = get_mongo_client()
    db_name = os.getenv("MONGODB_DB", "Abby")
    return client[db_name]


def get_tenant_id() -> str:
    """
    Get current tenant ID for queries.
    
    Returns:
        Tenant ID string (e.g., "TENANT:BREEZE_CLUB")
    """
    return _current_tenant_id


def set_tenant_id(tenant_id: str):
    """
    Override default tenant ID (for multi-tenant scenarios).
    
    Args:
        tenant_id: New tenant ID
    """
    global _current_tenant_id
    _current_tenant_id = tenant_id
    logger.info(f"[MongoDB] Tenant ID set to: {tenant_id}")


# ========== Collection Accessors ==========

def get_users_collection():
    """Get users collection."""
    return get_database()["users"]


def get_sessions_collection():
    """Get sessions collection."""
    return get_database()["sessions"]


def get_xp_collection():
    """Get xp collection."""
    return get_database()["xp"]


def get_economy_collection():
    """Get economy collection."""
    return get_database()["economy"]


def get_submissions_collection():
    """Get submissions collection."""
    return get_database()["submissions"]


def get_rag_documents_collection():
    """Get rag_documents collection."""
    return get_database()["rag_documents"]


# ========== Index Creation ==========

def create_indexes():
    """
    Create all required indexes for unified schema.
    
    This should be run once during migration or on first startup.
    All indexes include tenant_id for isolation.
    """
    db = get_database()
    
    # Users collection indexes
    users = get_users_collection()
    users.create_indexes([
        IndexModel([("_id", ASCENDING)]),  # Discord user ID (PK)
        IndexModel([("tenant_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("last_active_at", DESCENDING)]),
    ])
    logger.info("[MongoDB] Created indexes for 'users'")
    
    # Sessions collection indexes
    sessions = get_sessions_collection()
    sessions.create_indexes([
        IndexModel([("_id", ASCENDING)]),  # Session UUID (PK)
        IndexModel([("tenant_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("user_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("tags", ASCENDING)]),
    ])
    logger.info("[MongoDB] Created indexes for 'sessions'")
    
    # XP collection indexes
    xp = get_xp_collection()
    xp.create_indexes([
        IndexModel([("_id", ASCENDING)]),  # User ID (PK)
        IndexModel([("tenant_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("points", DESCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("level", DESCENDING)]),
    ])
    logger.info("[MongoDB] Created indexes for 'xp'")
    
    # Economy collection indexes
    economy = get_economy_collection()
    economy.create_indexes([
        IndexModel([("_id", ASCENDING)]),  # User ID (PK)
        IndexModel([("tenant_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("wallet_balance", DESCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("bank_balance", DESCENDING)]),
    ])
    logger.info("[MongoDB] Created indexes for 'economy'")
    
    # Submissions collection indexes
    submissions = get_submissions_collection()
    submissions.create_indexes([
        IndexModel([("_id", ASCENDING)]),  # Submission UUID (PK)
        IndexModel([("tenant_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("user_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("type", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("score", DESCENDING)]),
    ])
    logger.info("[MongoDB] Created indexes for 'submissions'")
    
    # RAG documents collection indexes
    rag_docs = get_rag_documents_collection()
    rag_docs.create_indexes([
        IndexModel([("_id", ASCENDING)]),  # Doc UUID (PK)
        IndexModel([("tenant_id", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("source", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("metadata.tags", ASCENDING)]),
        IndexModel([("tenant_id", ASCENDING), ("embedding_key", ASCENDING)]),
    ])
    logger.info("[MongoDB] Created indexes for 'rag_documents'")
    
    logger.info("[MongoDB] All indexes created successfully")


# ========== User Operations ==========

def upsert_user(user_id: str, username: str, roles: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Create or update user profile.
    
    Args:
        user_id: Discord user ID
        username: Discord username
        roles: Optional list of user roles
    
    Returns:
        Updated user document
    """
    tenant_id = get_tenant_id()
    users = get_users_collection()
    
    now = datetime.utcnow()
    user_doc = {
        "_id": user_id,
        "tenant_id": tenant_id,
        "username": username,
        "roles": roles or [],
        "last_active_at": now,
    }
    
    result = users.update_one(
        {"_id": user_id, "tenant_id": tenant_id},
        {
            "$set": user_doc,
            "$setOnInsert": {"created_at": now}
        },
        upsert=True
    )
    
    logger.debug(f"[MongoDB] Upserted user {user_id}")
    return user_doc


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user by ID.
    
    Args:
        user_id: Discord user ID
    
    Returns:
        User document or None
    """
    tenant_id = get_tenant_id()
    users = get_users_collection()
    return users.find_one({"_id": user_id, "tenant_id": tenant_id})


def update_user_llm_prefs(user_id: str, persona: Optional[str] = None, personality: Optional[float] = None):
    """
    Update user LLM preferences.
    
    Args:
        user_id: Discord user ID
        persona: Persona ID (e.g., "bunny", "kitten")
        personality: Personality float (0-1)
    """
    tenant_id = get_tenant_id()
    users = get_users_collection()
    
    update_doc = {}
    if persona is not None:
        update_doc["llm_prefs.persona"] = persona
    if personality is not None:
        update_doc["llm_prefs.personality"] = personality
    
    if update_doc:
        users.update_one(
            {"_id": user_id, "tenant_id": tenant_id},
            {"$set": update_doc}
        )
        logger.debug(f"[MongoDB] Updated LLM prefs for user {user_id}")


# ========== Session Operations ==========

def create_session(user_id: str, session_id: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Create new chat session.
    
    Args:
        user_id: Discord user ID
        session_id: Unique session UUID
        tags: Optional session tags
    
    Returns:
        Session document
    """
    tenant_id = get_tenant_id()
    sessions = get_sessions_collection()
    
    session_doc = {
        "_id": session_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "messages": [],
        "summary": None,
        "status": "active",
        "tags": tags or [],
        "created_at": datetime.utcnow(),
    }
    
    sessions.insert_one(session_doc)
    logger.debug(f"[MongoDB] Created session {session_id} for user {user_id}")
    return session_doc


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get session by ID.
    
    Args:
        session_id: Session UUID
    
    Returns:
        Session document or None
    """
    tenant_id = get_tenant_id()
    sessions = get_sessions_collection()
    return sessions.find_one({"_id": session_id, "tenant_id": tenant_id})


def append_session_message(session_id: str, role: str, content: str):
    """
    Append message to session.
    
    Args:
        session_id: Session UUID
        role: Message role ('user', 'assistant', 'system')
        content: Message content (will be encrypted if needed)
    """
    tenant_id = get_tenant_id()
    sessions = get_sessions_collection()
    
    message = {
        "role": role,
        "content": content,  # TODO: Encrypt with bdcrypt
        "ts": datetime.utcnow(),
    }
    
    sessions.update_one(
        {"_id": session_id, "tenant_id": tenant_id},
        {"$push": {"messages": message}}
    )
    logger.debug(f"[MongoDB] Appended {role} message to session {session_id}")


def close_session(session_id: str, summary: Optional[str] = None):
    """
    Close session and optionally set summary.
    
    Args:
        session_id: Session UUID
        summary: Optional session summary
    """
    tenant_id = get_tenant_id()
    sessions = get_sessions_collection()
    
    update_doc = {"status": "closed"}
    if summary:
        update_doc["summary"] = summary
    
    sessions.update_one(
        {"_id": session_id, "tenant_id": tenant_id},
        {"$set": update_doc}
    )
    logger.debug(f"[MongoDB] Closed session {session_id}")


# ========== XP Operations ==========

def get_xp(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user XP data.
    
    Args:
        user_id: Discord user ID
    
    Returns:
        XP document or None
    """
    tenant_id = get_tenant_id()
    xp = get_xp_collection()
    return xp.find_one({"_id": user_id, "tenant_id": tenant_id})


def add_xp(user_id: str, delta: int, source: str):
    """
    Add XP to user.
    
    Args:
        user_id: Discord user ID
        delta: XP delta (positive or negative)
        source: XP source description
    """
    tenant_id = get_tenant_id()
    xp_col = get_xp_collection()
    
    xp_entry = {
        "type": source,
        "delta": delta,
        "ts": datetime.utcnow(),
    }
    
    xp_col.update_one(
        {"_id": user_id, "tenant_id": tenant_id},
        {
            "$inc": {"points": delta},
            "$push": {"sources": xp_entry},
            "$set": {"last_award_at": datetime.utcnow()},
            "$setOnInsert": {"level": 1}
        },
        upsert=True
    )
    logger.debug(f"[MongoDB] Added {delta} XP to user {user_id} (source: {source})")


# ========== Economy Operations ==========

def get_economy(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user economy data.
    
    Args:
        user_id: Discord user ID
    
    Returns:
        Economy document or None
    """
    tenant_id = get_tenant_id()
    economy = get_economy_collection()
    return economy.find_one({"_id": user_id, "tenant_id": tenant_id})


def update_balance(user_id: str, wallet_delta: int = 0, bank_delta: int = 0, note: Optional[str] = None):
    """
    Update user wallet/bank balance.
    
    Args:
        user_id: Discord user ID
        wallet_delta: Wallet balance change
        bank_delta: Bank balance change
        note: Optional transaction note
    """
    tenant_id = get_tenant_id()
    economy_col = get_economy_collection()
    
    transaction = {
        "amount": wallet_delta + bank_delta,
        "type": "adjust",
        "ts": datetime.utcnow(),
        "note": note,
    }
    
    update_doc = {"$push": {"transactions": transaction}}
    
    if wallet_delta != 0:
        update_doc["$inc"] = update_doc.get("$inc", {})
        update_doc["$inc"]["wallet_balance"] = wallet_delta
    
    if bank_delta != 0:
        update_doc["$inc"] = update_doc.get("$inc", {})
        update_doc["$inc"]["bank_balance"] = bank_delta
    
    economy_col.update_one(
        {"_id": user_id, "tenant_id": tenant_id},
        update_doc,
        upsert=True
    )
    logger.debug(f"[MongoDB] Updated balance for user {user_id}: wallet={wallet_delta}, bank={bank_delta}")
