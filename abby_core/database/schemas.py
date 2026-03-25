"""
MongoDB Collection Schemas for Unified Abby Database

This module documents current collection schemas.
See docs/UNIVERSAL_USER_SCHEMA.md for Users collection details.
"""

from datetime import datetime
from typing import TypedDict, List, Optional, Dict, Any


# ========== Users Collection ==========

class CooldownSchema(TypedDict):
    """Cooldown tracking for a specific feature."""
    last_used_at: datetime


class UserCooldownsSchema(TypedDict):
    """User-level temporal state - global per user per day cooldowns."""
    daily_bonus: Optional[CooldownSchema]  # Once per user per day globally
    daily_login: Optional[CooldownSchema]  # Future: login bonus
    daily_quest: Optional[CooldownSchema]  # Future: quest reward


class DiscordPlatformSchema(TypedDict):
    """Discord platform data for user."""
    discord_id: str
    username: str
    display_name: str
    discriminator: str
    avatar_url: str
    joined_at: datetime
    last_seen: datetime


class UserSchema(TypedDict):
    """
    Users collection - Universal user profile nexus.
    
    Multi-platform user identity + user-level temporal state (cooldowns, bonuses).
    See docs/UNIVERSAL_USER_SCHEMA.md for full documentation.
    
    COOLDOWN TRACKING (User-level, not guild-scoped):
    - Stored in: cooldowns.{feature_name}.last_used_at
    - Helper functions in users collection module:
      * check_user_cooldown(user_id, cooldown_name) -> bool
      * record_user_cooldown(user_id, cooldown_name) -> bool
    """
    _id: str
    user_id: str  # Primary key (Discord ID or UUID v4)
    discord: DiscordPlatformSchema
    cooldowns: UserCooldownsSchema  # User-level temporal state
    guilds: List[Dict[str, Any]]
    creative_profile: Dict[str, Any]
    social_accounts: List[Dict[str, Any]]
    creative_accounts: List[Dict[str, Any]]
    artist_profile: Dict[str, Any]
    collaborations: List[Dict[str, Any]]
    releases: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


# ========== Reserved for Future Use ==========
# Sessions, Memory, and other future collections documented separately


# ========== XP Collection ==========

class XPRecordSchema(TypedDict):
    """
    XP collection - Guild-scoped experience and leveling.
    
    Composite key: user_id + guild_id (see users.py for implementation)
    Does NOT contain daily bonus tracking (that's in Users.cooldowns).
    """
    _id: str
    user_id: str  # Discord ID or UUID v4
    guild_id: int  # Guild where XP earned
    xp: int  # Total XP in guild
    level: int  # Current level in guild
    xp_last_message: datetime  # Last message XP reward time (anti-spam)
    created_at: datetime
    updated_at: datetime


# ========== Guild Configuration ==========

class GuildConfigSchema(TypedDict):
    """
    Guild configuration - Guild-specific bot settings.
    
    Stores channel IDs, role configurations, feature flags per guild.
    """
    _id: str
    guild_id: int
    xp_channel_id: Optional[int]  # Channel for XP notifications
    xp_enabled: bool  # Whether XP rewards enabled in guild
    economy_enabled: bool  # Whether economy features enabled
    created_at: datetime
    updated_at: datetime


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
