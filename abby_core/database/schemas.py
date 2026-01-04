"""
MongoDB Collection Schemas for Unified Abby Database

This module defines the structure and validation rules for all 6 collections
in the unified Abby database. Used for documentation and migration reference.

All schemas enforce tenant_id presence per TDOS v1.5 invariants.
"""

from datetime import datetime
from typing import TypedDict, List, Optional, Dict, Any


# ========== Users Collection ==========

class UserSchema(TypedDict):
    """
    Users collection schema.
    
    Stores Discord user profiles + LLM preferences.
    """
    _id: str  # Discord user ID
    tenant_id: str  # TDOS tenant scope
    username: str  # Discord username
    roles: List[str]  # User roles within tenant
    created_at: datetime  # User first seen
    last_active_at: datetime  # Last activity timestamp
    llm_prefs: Dict[str, Any]  # {"persona": str, "personality": float}


# ========== Sessions Collection ==========

class SessionMessageSchema(TypedDict):
    """Session message structure."""
    role: str  # 'user' | 'assistant' | 'system'
    content: str  # Message content (encrypted)
    ts: datetime  # Message timestamp


class SessionSchema(TypedDict):
    """
    Sessions collection schema.
    
    Stores chat sessions with encrypted messages.
    """
    _id: str  # Session UUID
    tenant_id: str  # TDOS tenant scope
    user_id: str  # Discord user ID
    messages: List[SessionMessageSchema]  # Session messages
    summary: Optional[str]  # Optional session summary
    status: str  # 'active' | 'closed'
    tags: List[str]  # Session tags
    created_at: datetime  # Session start


# ========== XP Collection ==========

class XPSourceSchema(TypedDict):
    """XP source entry."""
    type: str  # Source type (e.g., 'message', 'command', 'reward')
    delta: int  # XP delta
    ts: datetime  # Award timestamp


class XPSchema(TypedDict):
    """
    XP collection schema.
    
    Stores experience/level tracking.
    """
    _id: str  # User ID
    tenant_id: str  # TDOS tenant scope
    points: int  # Total XP points
    level: int  # Current level
    last_award_at: datetime  # Last XP award timestamp
    sources: List[XPSourceSchema]  # XP history


# ========== Economy Collection ==========

class TransactionSchema(TypedDict):
    """Transaction entry."""
    amount: int  # Transaction amount
    type: str  # 'deposit' | 'withdraw' | 'reward' | 'purchase'
    ts: datetime  # Transaction timestamp
    note: Optional[str]  # Optional transaction note


class EconomySchema(TypedDict):
    """
    Economy collection schema.
    
    Stores wallet/bank balances + transactions.
    """
    _id: str  # User ID
    tenant_id: str  # TDOS tenant scope
    wallet_balance: int  # Wallet balance
    bank_balance: int  # Bank balance
    last_daily: Optional[datetime]  # Last daily bonus claim
    tip_budget_used: int  # Amount of daily tipping budget used
    tip_budget_reset: Optional[datetime]  # Last time tipping budget was reset
    transactions: List[TransactionSchema]  # Transaction history


# ========== Submissions Collection ==========

class VoteSchema(TypedDict):
    """Vote entry."""
    user_id: str  # Voter Discord user ID
    vote: int  # Vote value
    ts: datetime  # Vote timestamp


class SubmissionSchema(TypedDict):
    """
    Submissions collection schema.
    
    Stores user submissions (demos, images, text).
    """
    _id: str  # Submission UUID
    tenant_id: str  # TDOS tenant scope
    user_id: str  # Discord user ID
    type: str  # 'demo' | 'image' | 'text' | 'other'
    title: str  # Submission title
    metadata: Dict[str, Any]  # {"genre": str, "link": str, "file_ref": str, ...}
    status: str  # 'draft' | 'submitted' | 'approved' | 'rejected'
    score: int  # Submission score
    votes: List[VoteSchema]  # Vote history
    created_at: datetime  # Submission creation timestamp


# ========== RAG Documents Collection ==========

class RAGDocumentSchema(TypedDict):
    """
    RAG documents collection schema.
    
    Stores RAG corpus documents with embeddings.
    """
    _id: str  # Doc UUID
    tenant_id: str  # TDOS tenant scope
    source: str  # 'label_docs' | 'guidelines' | 'artist_profiles' | 'discord_threads' | 'other'
    title: str  # Document title
    text: str  # Document text content
    metadata: Dict[str, Any]  # {"submission_id": str, "tags": List[str], "ts_ingested": datetime}
    embedding_key: str  # External key in Chroma/Qdrant


# ========== Index Specifications ==========

INDEX_SPECS = {
    "users": [
        {"keys": [("_id", 1)], "name": "pk_user_id"},
        {"keys": [("tenant_id", 1)], "name": "idx_tenant"},
        {"keys": [("tenant_id", 1), ("last_active_at", -1)], "name": "idx_tenant_activity"},
    ],
    "sessions": [
        {"keys": [("_id", 1)], "name": "pk_session_id"},
        {"keys": [("tenant_id", 1)], "name": "idx_tenant"},
        {"keys": [("tenant_id", 1), ("user_id", 1)], "name": "idx_tenant_user"},
        {"keys": [("tenant_id", 1), ("status", 1)], "name": "idx_tenant_status"},
        {"keys": [("tenant_id", 1), ("tags", 1)], "name": "idx_tenant_tags"},
    ],
    "xp": [
        {"keys": [("_id", 1)], "name": "pk_user_id"},
        {"keys": [("tenant_id", 1)], "name": "idx_tenant"},
        {"keys": [("tenant_id", 1), ("points", -1)], "name": "idx_tenant_points"},
        {"keys": [("tenant_id", 1), ("level", -1)], "name": "idx_tenant_level"},
    ],
    "economy": [
        {"keys": [("_id", 1)], "name": "pk_user_id"},
        {"keys": [("tenant_id", 1)], "name": "idx_tenant"},
        {"keys": [("tenant_id", 1), ("wallet_balance", -1)], "name": "idx_tenant_wallet"},
        {"keys": [("tenant_id", 1), ("bank_balance", -1)], "name": "idx_tenant_bank"},
    ],
    "submissions": [
        {"keys": [("_id", 1)], "name": "pk_submission_id"},
        {"keys": [("tenant_id", 1)], "name": "idx_tenant"},
        {"keys": [("tenant_id", 1), ("user_id", 1)], "name": "idx_tenant_user"},
        {"keys": [("tenant_id", 1), ("type", 1)], "name": "idx_tenant_type"},
        {"keys": [("tenant_id", 1), ("status", 1)], "name": "idx_tenant_status"},
        {"keys": [("tenant_id", 1), ("created_at", -1)], "name": "idx_tenant_created"},
        {"keys": [("tenant_id", 1), ("score", -1)], "name": "idx_tenant_score"},
    ],
    "rag_documents": [
        {"keys": [("_id", 1)], "name": "pk_doc_id"},
        {"keys": [("tenant_id", 1)], "name": "idx_tenant"},
        {"keys": [("tenant_id", 1), ("source", 1)], "name": "idx_tenant_source"},
        {"keys": [("tenant_id", 1), ("metadata.tags", 1)], "name": "idx_tenant_tags"},
        {"keys": [("tenant_id", 1), ("embedding_key", 1)], "name": "idx_tenant_embedding"},
    ],
}


# ========== Sample Documents ==========

SAMPLE_USER = {
    "_id": "123456789012345678",
    "tenant_id": "TENANT:BREEZE_CLUB",
    "username": "TestUser#1234",
    "roles": ["member"],
    "created_at": datetime.utcnow(),
    "last_active_at": datetime.utcnow(),
    "llm_prefs": {
        "persona": "bunny",
        "personality": 0.8,
    },
}

SAMPLE_SESSION = {
    "_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant_id": "TENANT:BREEZE_CLUB",
    "user_id": "123456789012345678",
    "messages": [
        {
            "role": "user",
            "content": "Hello Abby!",
            "ts": datetime.utcnow(),
        },
        {
            "role": "assistant",
            "content": "Hi! How can I help you today?",
            "ts": datetime.utcnow(),
        },
    ],
    "summary": None,
    "status": "active",
    "tags": ["general"],
    "created_at": datetime.utcnow(),
}

SAMPLE_XP = {
    "_id": "123456789012345678",
    "tenant_id": "TENANT:BREEZE_CLUB",
    "points": 1500,
    "level": 5,
    "last_award_at": datetime.utcnow(),
    "sources": [
        {"type": "message", "delta": 10, "ts": datetime.utcnow()},
        {"type": "command", "delta": 50, "ts": datetime.utcnow()},
    ],
}

SAMPLE_ECONOMY = {
    "_id": "123456789012345678",
    "tenant_id": "TENANT:BREEZE_CLUB",
    "wallet_balance": 500,
    "bank_balance": 2000,
    "last_daily": datetime.utcnow(),
    "transactions": [
        {"amount": 100, "type": "reward", "ts": datetime.utcnow(), "note": "Daily bonus"},
        {"amount": -50, "type": "purchase", "ts": datetime.utcnow(), "note": "Extra image generation"},
    ],
}

SAMPLE_SUBMISSION = {
    "_id": "550e8400-e29b-41d4-a716-446655440001",
    "tenant_id": "TENANT:BREEZE_CLUB",
    "user_id": "123456789012345678",
    "type": "demo",
    "title": "My First Track",
    "metadata": {
        "genre": "electronic",
        "link": "https://soundcloud.com/user/track",
        "file_ref": None,
    },
    "status": "submitted",
    "score": 15,
    "votes": [
        {"user_id": "987654321098765432", "vote": 1, "ts": datetime.utcnow()},
    ],
    "created_at": datetime.utcnow(),
}

SAMPLE_RAG_DOC = {
    "_id": "550e8400-e29b-41d4-a716-446655440002",
    "tenant_id": "TENANT:BREEZE_CLUB",
    "source": "label_docs",
    "title": "Submission Guidelines",
    "text": "All submissions must be original work...",
    "metadata": {
        "submission_id": None,
        "tags": ["guidelines", "policy"],
        "ts_ingested": datetime.utcnow(),
    },
    "embedding_key": "chroma_doc_001",
}
