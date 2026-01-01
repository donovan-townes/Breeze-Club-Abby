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
from abby_core.database.mongodb import connect_to_mongodb
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


def create_indexes():
    """Create all necessary indexes for the unified database."""
    try:
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        
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
        
        
        # ==================== Discord Profiles Collection ====================
        discord_profiles = db["discord_profiles"]
        
        # Unique index on user_id (one profile per user)
        discord_profiles.create_index([("user_id", ASCENDING)], unique=True)
        logger.info("[✅] Created unique index: discord_profiles.user_id")
        
        
        # ==================== RAG Documents Collection ====================
        rag_documents = db["rag_documents"]
        
        # Index for finding user's documents
        rag_documents.create_index([("user_id", ASCENDING)])
        logger.info("[✅] Created index: rag_documents.user_id")
        
        # Index for finding guild documents
        rag_documents.create_index([("guild_id", ASCENDING)])
        logger.info("[✅] Created index: rag_documents.guild_id")
        
        # Compound index for user + guild documents
        rag_documents.create_index([
            ("user_id", ASCENDING),
            ("guild_id", ASCENDING)
        ])
        logger.info("[✅] Created compound index: rag_documents(user_id, guild_id)")
        
        # Unique index on document_id
        rag_documents.create_index([("document_id", ASCENDING)], unique=True)
        logger.info("[✅] Created unique index: rag_documents.document_id")
        
        
        logger.info("\n[🎉] Database initialization complete!")
        logger.info("[📗] All indexes created successfully.")
        logger.info("[📗] Database is ready for production use.")
        
        return True
        
    except Exception as e:
        logger.error(f"[❌] Failed to create indexes: {e}")
        return False


def verify_indexes():
    """Verify that all indexes were created correctly."""
    try:
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        
        logger.info("\n[🔍] Verifying indexes...")
        
        collections = ["chat_sessions", "user_xp", "discord_profiles", "rag_documents"]
        
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
        # Verify indexes
        verify_indexes()
        logger.info("\n[✅] Database initialization successful!")
    else:
        logger.error("\n[❌] Database initialization failed!")
        sys.exit(1)
