"""
Database Initialization Script for Unified MongoDB Architecture

This script creates the proper database structure with indexes for optimal performance.
Run this once after migrating to the new unified database architecture.

Usage:
    python scripts/initialize_database.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import ASCENDING, DESCENDING
from abby_core.database.mongodb import connect_to_mongodb, _get_db_name
from abby_core.observability.logging import setup_logging, logging
from abby_core.system.system_state import initialize_predefined_seasons

setup_logging()
logger = logging.getLogger(__name__)


def create_indexes():
    """Create all necessary indexes for the unified database."""
    try:
        client = connect_to_mongodb()
        db = client[_get_db_name()]
        
        logger.info("[📗] Creating indexes for unified database...")
        
        # ==================== Chat Sessions Collection ====================
        chat_sessions = db["chat_sessions"]
        
        # Index for finding user's sessions
        chat_sessions.create_index([("user_id", ASCENDING)])
        logger.info("[✅] Created index: chat_sessions.user_id")
        
        # Index for finding guild-specific sessions
        chat_sessions.create_index([("guild_id", ASCENDING)])
        logger.info("[✅] Created index: chat_sessions.guild_id")
        
        # Compound index for user + guild queries (most common)
        chat_sessions.create_index([
            ("user_id", ASCENDING),
            ("guild_id", ASCENDING),
            ("closed_at", DESCENDING)
        ])
        logger.info("[✅] Created compound index: chat_sessions(user_id, guild_id, closed_at DESC)")
        
        # Index for finding active sessions
        chat_sessions.create_index([("status", ASCENDING)])
        logger.info("[✅] Created index: chat_sessions.status")
        
        # Unique index on session_id
        chat_sessions.create_index([("session_id", ASCENDING)], unique=True)
        logger.info("[✅] Created unique index: chat_sessions.session_id")
        
        
        # ==================== User XP Collection ====================
        user_xp = db["user_xp"]
        
        # Index for finding user XP
        user_xp.create_index([("user_id", ASCENDING)])
        logger.info("[✅] Created index: user_xp.user_id")
        
        # Compound index for user + guild queries
        user_xp.create_index([
            ("user_id", ASCENDING),
            ("guild_id", ASCENDING)
        ], unique=True)
        logger.info("[✅] Created compound unique index: user_xp(user_id, guild_id)")
        
        # Index for leaderboards (sorted by points)
        user_xp.create_index([("points", DESCENDING)])
        logger.info("[✅] Created index: user_xp.points DESC")
        
        # Index for level-based queries
        user_xp.create_index([("level", DESCENDING)])
        logger.info("[✅] Created index: user_xp.level DESC")
        
        
        # ==================== System State Collection ====================
        system_state = db["system_state"]
        
        # Index for finding active states
        system_state.create_index([("active", ASCENDING)])
        logger.info("[✅] Created index: system_state.active")
        
        # Compound index for type + active queries
        system_state.create_index([
            ("state_type", ASCENDING),
            ("active", ASCENDING)
        ])
        logger.info("[✅] Created compound index: system_state(state_type, active)")
        
        # Unique index on state_id
        system_state.create_index([("state_id", ASCENDING)], unique=True)
        logger.info("[✅] Created unique index: system_state.state_id")
        
        # Index for date range queries (season boundary lookups)
        system_state.create_index([
            ("start_at", ASCENDING),
            ("end_at", ASCENDING)
        ])
        logger.info("[✅] Created compound index: system_state(start_at, end_at)")
        
        
        # ==================== Users Collection (Primary Storage) ====================
        users = db["users"]
        
        # Unique index on user_id (one profile per user)
        users.create_index([("user_id", ASCENDING)], unique=True)
        logger.info("[✅] Created unique index: users.user_id")
        
        
        # ==================== RAG Documents Collection ====================
        rag_documents = db["rag_documents"]
        
        # Tenant scoping and retrieval indexes
        rag_documents.create_index([("tenant_id", ASCENDING)])
        rag_documents.create_index([("tenant_id", ASCENDING), ("source", ASCENDING)])
        rag_documents.create_index([("tenant_id", ASCENDING), ("metadata.tags", ASCENDING)])
        rag_documents.create_index([("tenant_id", ASCENDING), ("embedding_key", ASCENDING)])
        rag_documents.create_index([("tenant_id", ASCENDING), ("title", ASCENDING)])
        logger.info("[✅] Created indexes for rag_documents (tenant, source, tags, embedding_key, title)")
        
        # ==================== Users Collection (TDOS Memory - Primary Storage) ====================
        users = db["users"]

        # Unique compound index for multi-tenant isolation (user_id, guild_id)
        # This ensures each user can have only one profile per guild/global context
        try:
            users.create_index(
                [("user_id", ASCENDING), ("guild_id", ASCENDING)],
                unique=True,
                name="unique_user_guild"
            )
            logger.info("[✅] Created unique compound index: users(user_id, guild_id)")
        except Exception as e:
            # Index may already exist from runtime creation
            logger.warning(f"[⚠️] Index unique_user_guild may already exist: {e}")
        
        
        logger.info("\n[🎉] Database initialization complete!")
        logger.info("[📗] All indexes created successfully.")
        logger.info("[📗] Database is ready for production use.")
        
        return True
        
    except Exception as e:
        logger.error(f"[❌] Failed to create indexes: {e}")
        return False


def initialize_canonical_data():
    """Initialize canonical platform data (seasons, states, etc)."""
    try:
        logger.info("\n[📋] Initializing canonical platform data...")
        initialize_predefined_seasons()
        logger.info("[✅] Predefined seasons initialized")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to initialize canonical data: {e}")
        return False


def verify_indexes():
    """Verify that all indexes were created correctly."""
    try:
        client = connect_to_mongodb()
        db = client[_get_db_name()]
        
        logger.info("\n[🔍] Verifying indexes...")
        
        collections = ["chat_sessions", "user_xp", "users", "rag_documents", "system_state"]
        
        for collection_name in collections:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())
            logger.info(f"\n[📗] {collection_name} indexes:")
            for index in indexes:
                logger.info(f"  - {index['name']}: {index.get('key', {})}")
        
        return True
        
    except Exception as e:
        logger.error(f"[❌] Failed to verify indexes: {e}")
        return False


if __name__ == "__main__":
    logger.info("[🚀] Starting database initialization...")
    logger.info("[📗] This script will create indexes for the unified MongoDB architecture.")
    
    # Create indexes
    if create_indexes():
        # Initialize canonical data
        if initialize_canonical_data():
            # Verify indexes
            verify_indexes()
            logger.info("\n[✅] Database initialization successful!")
        else:
            logger.error("\n[❌] Canonical data initialization failed!")
            sys.exit(1)
    else:
        logger.error("\n[❌] Database initialization failed!")
        sys.exit(1)
