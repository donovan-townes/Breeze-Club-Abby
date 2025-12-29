"""
MongoDB Migration Script: Per-User DBs → Unified Schema

This script migrates Abby's legacy per-user database structure to the new
unified schema with tenant_id scoping (TDOS v1.5 compliant).

Migration flow:
1. Connect to online MongoDB Atlas
2. Discover all User_{id} databases
3. For each user database:
   - Extract user profile → users collection
   - Extract chat logs → sessions collection
   - Extract XP data → xp collection
   - Extract economy data → economy collection
4. Verify migration counts and data integrity
5. Create indexes on unified collections

CRITICAL: Run this script against a TEST database first!

Usage:
    # Dry run (no writes)
    python docs/migration_script.py --dry-run
    
    # Production migration
    python docs/migration_script.py --source-uri "mongodb+srv://user:pass@cluster" --target-uri "mongodb://localhost:27017"
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

# Add abby-core to path
REPO_ROOT = Path(__file__).parent.parent
ABBY_CORE_PATH = REPO_ROOT / "abby-core"
if str(ABBY_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ABBY_CORE_PATH))

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from utils.log_config import logging, setup_logging
import utils.bdcrypt as bdcrypt

setup_logging()
logger = logging.getLogger(__name__)

# Migration configuration
DEFAULT_TENANT_ID = "TENANT:BREEZE_CLUB"
MIGRATION_BATCH_SIZE = 100


class MigrationStats:
    """Track migration statistics."""
    
    def __init__(self):
        self.users_migrated = 0
        self.sessions_migrated = 0
        self.xp_migrated = 0
        self.economy_migrated = 0
        self.errors = []
        self.start_time = datetime.utcnow()
    
    def log_error(self, context: str, error: Exception):
        """Log migration error."""
        error_entry = {
            "context": context,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow(),
        }
        self.errors.append(error_entry)
        logger.error(f"[Migration Error] {context}: {error}")
    
    def print_summary(self):
        """Print migration summary."""
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        logger.info("\n" + "=" * 70)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Users migrated: {self.users_migrated}")
        logger.info(f"Sessions migrated: {self.sessions_migrated}")
        logger.info(f"XP records migrated: {self.xp_migrated}")
        logger.info(f"Economy records migrated: {self.economy_migrated}")
        logger.info(f"Errors: {len(self.errors)}")
        
        if self.errors:
            logger.warning("\nErrors encountered:")
            for err in self.errors[:10]:  # Show first 10 errors
                logger.warning(f"  - {err['context']}: {err['error_type']} - {err['error_message']}")
            if len(self.errors) > 10:
                logger.warning(f"  ... and {len(self.errors) - 10} more errors")
        
        logger.info("=" * 70)


def discover_user_databases(source_client: MongoClient) -> List[str]:
    """
    Discover all User_{id} databases in source MongoDB.
    
    Args:
        source_client: Source MongoDB client
    
    Returns:
        List of User_{id} database names
    """
    logger.info("Discovering per-user databases...")
    
    all_dbs = source_client.list_database_names()
    user_dbs = [db for db in all_dbs if db.startswith("User_")]
    
    logger.info(f"Found {len(user_dbs)} per-user databases")
    return user_dbs


def extract_user_id_from_db_name(db_name: str) -> str:
    """Extract Discord user ID from database name (User_{id})."""
    return db_name.replace("User_", "")


def migrate_user_profile(
    source_db,
    target_users_collection,
    user_id: str,
    tenant_id: str,
    stats: MigrationStats,
    dry_run: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Migrate user profile from legacy database to unified users collection.
    
    Args:
        source_db: Source user database
        target_users_collection: Target users collection
        user_id: Discord user ID
        tenant_id: TDOS tenant ID
        stats: Migration statistics
        dry_run: If True, don't write to target
    
    Returns:
        Migrated user document or None
    """
    try:
        # Extract user profile from legacy "Discord Profile" collection
        profile_coll = source_db["Discord Profile"]
        legacy_profile = profile_coll.find_one({"discord_id": user_id})
        
        if not legacy_profile:
            logger.warning(f"No profile found for user {user_id}")
            return None
        
        # Build unified user document
        user_doc = {
            "_id": user_id,
            "tenant_id": tenant_id,
            "username": legacy_profile.get("username", f"User_{user_id}"),
            "roles": legacy_profile.get("roles", []),
            "created_at": legacy_profile.get("created_at", datetime.utcnow()),
            "last_active_at": legacy_profile.get("last_updated", datetime.utcnow()),
            "llm_prefs": {
                "persona": legacy_profile.get("persona", "bunny"),
                "personality": legacy_profile.get("personality", 0.8),
            },
        }
        
        if not dry_run:
            target_users_collection.update_one(
                {"_id": user_id, "tenant_id": tenant_id},
                {"$set": user_doc},
                upsert=True
            )
        
        stats.users_migrated += 1
        logger.debug(f"Migrated user profile: {user_id}")
        return user_doc
    
    except Exception as e:
        stats.log_error(f"migrate_user_profile({user_id})", e)
        return None


def migrate_user_sessions(
    source_db,
    target_sessions_collection,
    user_id: str,
    tenant_id: str,
    stats: MigrationStats,
    dry_run: bool = False
):
    """
    Migrate user chat sessions from legacy database to unified sessions collection.
    
    Args:
        source_db: Source user database
        target_sessions_collection: Target sessions collection
        user_id: Discord user ID
        tenant_id: TDOS tenant ID
        stats: Migration statistics
        dry_run: If True, don't write to target
    """
    try:
        # Extract chat logs from legacy collections (may vary by user)
        # Common collection names: "Conversations", "Chat Logs", "Messages"
        possible_collections = ["Conversations", "Chat Logs", "Messages", "chat_logs"]
        
        for coll_name in possible_collections:
            if coll_name not in source_db.list_collection_names():
                continue
            
            chat_coll = source_db[coll_name]
            
            # Group messages by session (if sessions exist) or create single session
            legacy_sessions = list(chat_coll.find({}))
            
            if not legacy_sessions:
                continue
            
            # For simplicity, create one session per user with all messages
            # TODO: Improve session grouping logic based on timestamp gaps
            session_id = str(uuid.uuid4())
            
            messages = []
            for msg in legacy_sessions:
                # Extract message content (may be encrypted)
                content = msg.get("content") or msg.get("chat_response") or msg.get("message", "")
                role = msg.get("role", "user")
                ts = msg.get("timestamp") or msg.get("ts") or datetime.utcnow()
                
                messages.append({
                    "role": role,
                    "content": content,  # Preserve encryption if present
                    "ts": ts,
                })
            
            # Build unified session document
            session_doc = {
                "_id": session_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "messages": messages,
                "summary": None,
                "status": "closed",  # Mark legacy sessions as closed
                "tags": ["legacy_migration"],
                "created_at": messages[0]["ts"] if messages else datetime.utcnow(),
            }
            
            if not dry_run:
                target_sessions_collection.insert_one(session_doc)
            
            stats.sessions_migrated += 1
            logger.debug(f"Migrated session {session_id} for user {user_id} ({len(messages)} messages)")
    
    except Exception as e:
        stats.log_error(f"migrate_user_sessions({user_id})", e)


def migrate_user_xp(
    source_db,
    target_xp_collection,
    user_id: str,
    tenant_id: str,
    stats: MigrationStats,
    dry_run: bool = False
):
    """
    Migrate user XP data from legacy database to unified xp collection.
    
    Args:
        source_db: Source user database
        target_xp_collection: Target xp collection
        user_id: Discord user ID
        tenant_id: TDOS tenant ID
        stats: Migration statistics
        dry_run: If True, don't write to target
    """
    try:
        # Extract XP from legacy collections (may vary)
        possible_collections = ["XP", "Experience", "Levels"]
        
        for coll_name in possible_collections:
            if coll_name not in source_db.list_collection_names():
                continue
            
            xp_coll = source_db[coll_name]
            legacy_xp = xp_coll.find_one({"user_id": user_id})
            
            if not legacy_xp:
                continue
            
            # Build unified XP document
            xp_doc = {
                "_id": user_id,
                "tenant_id": tenant_id,
                "points": legacy_xp.get("points", 0),
                "level": legacy_xp.get("level", 1),
                "last_award_at": legacy_xp.get("last_award_at", datetime.utcnow()),
                "sources": legacy_xp.get("sources", []),
            }
            
            if not dry_run:
                target_xp_collection.update_one(
                    {"_id": user_id, "tenant_id": tenant_id},
                    {"$set": xp_doc},
                    upsert=True
                )
            
            stats.xp_migrated += 1
            logger.debug(f"Migrated XP for user {user_id}: {xp_doc['points']} points, level {xp_doc['level']}")
            break
    
    except Exception as e:
        stats.log_error(f"migrate_user_xp({user_id})", e)


def migrate_user_economy(
    source_db,
    target_economy_collection,
    user_id: str,
    tenant_id: str,
    stats: MigrationStats,
    dry_run: bool = False
):
    """
    Migrate user economy data from legacy database to unified economy collection.
    
    Args:
        source_db: Source user database
        target_economy_collection: Target economy collection
        user_id: Discord user ID
        tenant_id: TDOS tenant ID
        stats: Migration statistics
        dry_run: If True, don't write to target
    """
    try:
        # Extract economy from legacy collections (may vary)
        possible_collections = ["Economy", "Bank", "Wallet"]
        
        for coll_name in possible_collections:
            if coll_name not in source_db.list_collection_names():
                continue
            
            economy_coll = source_db[coll_name]
            legacy_economy = economy_coll.find_one({"user_id": user_id})
            
            if not legacy_economy:
                continue
            
            # Build unified economy document
            economy_doc = {
                "_id": user_id,
                "tenant_id": tenant_id,
                "wallet_balance": legacy_economy.get("wallet_balance", 0),
                "bank_balance": legacy_economy.get("bank_balance", 0),
                "last_daily": legacy_economy.get("last_daily"),
                "transactions": legacy_economy.get("transactions", []),
            }
            
            if not dry_run:
                target_economy_collection.update_one(
                    {"_id": user_id, "tenant_id": tenant_id},
                    {"$set": economy_doc},
                    upsert=True
                )
            
            stats.economy_migrated += 1
            logger.debug(f"Migrated economy for user {user_id}: wallet={economy_doc['wallet_balance']}, bank={economy_doc['bank_balance']}")
            break
    
    except Exception as e:
        stats.log_error(f"migrate_user_economy({user_id})", e)


def migrate_single_user(
    source_client: MongoClient,
    target_db,
    user_db_name: str,
    tenant_id: str,
    stats: MigrationStats,
    dry_run: bool = False
):
    """
    Migrate single user database to unified schema.
    
    Args:
        source_client: Source MongoDB client
        target_db: Target unified database
        user_db_name: Source user database name (User_{id})
        tenant_id: TDOS tenant ID
        stats: Migration statistics
        dry_run: If True, don't write to target
    """
    user_id = extract_user_id_from_db_name(user_db_name)
    source_db = source_client[user_db_name]
    
    logger.info(f"Migrating user database: {user_db_name} (user_id={user_id})")
    
    # Migrate user profile
    migrate_user_profile(
        source_db,
        target_db["users"],
        user_id,
        tenant_id,
        stats,
        dry_run
    )
    
    # Migrate sessions
    migrate_user_sessions(
        source_db,
        target_db["sessions"],
        user_id,
        tenant_id,
        stats,
        dry_run
    )
    
    # Migrate XP
    migrate_user_xp(
        source_db,
        target_db["xp"],
        user_id,
        tenant_id,
        stats,
        dry_run
    )
    
    # Migrate economy
    migrate_user_economy(
        source_db,
        target_db["economy"],
        user_id,
        tenant_id,
        stats,
        dry_run
    )


def main():
    """Main migration execution."""
    parser = argparse.ArgumentParser(description="Migrate Abby MongoDB from per-user DBs to unified schema")
    parser.add_argument("--source-uri", required=True, help="Source MongoDB URI (Atlas)")
    parser.add_argument("--target-uri", required=True, help="Target MongoDB URI (local or remote)")
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID, help="TDOS tenant ID")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no writes to target)")
    parser.add_argument("--limit", type=int, help="Limit migration to N users (for testing)")
    
    args = parser.parse_args()
    
    stats = MigrationStats()
    
    try:
        logger.info("=" * 70)
        logger.info("ABBY MONGODB MIGRATION: Per-User DBs → Unified Schema")
        logger.info("=" * 70)
        logger.info(f"Source URI: {args.source_uri[:30]}...")
        logger.info(f"Target URI: {args.target_uri[:30]}...")
        logger.info(f"Tenant ID: {args.tenant_id}")
        logger.info(f"Dry run: {args.dry_run}")
        if args.limit:
            logger.info(f"Migration limit: {args.limit} users")
        logger.info("=" * 70)
        
        # Connect to source and target
        logger.info("Connecting to source MongoDB...")
        source_client = MongoClient(args.source_uri, server_api=ServerApi('1'))
        source_client.admin.command('ping')
        logger.info("Source connection successful")
        
        logger.info("Connecting to target MongoDB...")
        target_client = MongoClient(args.target_uri, server_api=ServerApi('1'))
        target_client.admin.command('ping')
        logger.info("Target connection successful")
        
        target_db_name = "Abby"
        target_db = target_client[target_db_name]
        logger.info(f"Target database: {target_db_name}")
        
        # Discover user databases
        user_dbs = discover_user_databases(source_client)
        
        if args.limit:
            user_dbs = user_dbs[:args.limit]
            logger.info(f"Limited to {len(user_dbs)} users for testing")
        
        # Migrate each user database
        for i, user_db_name in enumerate(user_dbs, 1):
            logger.info(f"\n[{i}/{len(user_dbs)}] Processing {user_db_name}...")
            
            migrate_single_user(
                source_client,
                target_db,
                user_db_name,
                args.tenant_id,
                stats,
                args.dry_run
            )
        
        # Print summary
        stats.print_summary()
        
        if not args.dry_run:
            logger.info("\n✅ Migration complete! Next steps:")
            logger.info("1. Run index initialization: python -m abby-core.utils.init_indexes")
            logger.info("2. Verify data integrity and counts")
            logger.info("3. Update .env MONGODB_URI to point to new database")
            logger.info("4. Test Abby with unified schema")
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    
    finally:
        if 'source_client' in locals():
            source_client.close()
        if 'target_client' in locals():
            target_client.close()


if __name__ == "__main__":
    main()
