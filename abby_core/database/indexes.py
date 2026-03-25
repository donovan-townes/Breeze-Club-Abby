"""
MongoDB Index and Constraint Initialization Script

Run this script once after migration or on first startup to create all
required indexes and unique constraints for the unified Abby database.

Usage:
    python -m abby_core.database.indexes

Phase 5 Hardening:
- Added unique constraint on system_state_instances(state_id, state_type) to prevent duplicate instances
- Ensures state-instance sync integrity
"""

import sys
from pathlib import Path

from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging, setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def create_system_state_indexes(db):
    """Create indexes and constraints for system state collections.
    
    Phase 5 Hardening: Unique constraint prevents duplicate instances of the same state.
    This prevents orphaned state instances that could never be deactivated properly.
    """
    try:
        # Unique constraint: no two active instances of the same (state_id, state_type)
        instances_coll = db["system_state_instances"]
        
        try:
            instances_coll.create_index(
                [("state_id", 1), ("state_type", 1)],
                unique=True,
                name="idx_state_id_type_unique"
            )
            logger.info("[✓] Created unique index on system_state_instances(state_id, state_type)")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("[ℹ️] Unique index on system_state_instances(state_id, state_type) already exists")
            else:
                raise
        
        # Compound index for querying by state_type + active
        instances_coll.create_index(
            [("state_type", 1), ("active", 1)],
            name="idx_state_type_active"
        )
        logger.info("[✓] Created index on system_state_instances(state_type, active)")
        
        # Index for efficient lookup by state_id
        instances_coll.create_index(
            [("state_id", 1)],
            name="idx_state_id"
        )
        logger.info("[✓] Created index on system_state_instances(state_id)")
        
        # Timestamp index for cleanup/archival operations
        instances_coll.create_index(
            [("activated_at", 1)],
            name="idx_activated_at"
        )
        logger.info("[✓] Created index on system_state_instances(activated_at)")
        
        # Index for system_state collection
        states_coll = db["system_state"]
        states_coll.create_index(
            [("state_id", 1)],
            unique=True,
            name="idx_state_id_unique"
        )
        logger.info("[✓] Created unique index on system_state(state_id)")
        
    except Exception as e:
        logger.error(f"[❌] Failed to create system state indexes: {e}")
        raise


def main():
    """Initialize all MongoDB indexes for unified schema."""
    try:
        logger.info("=" * 60)
        logger.info("MongoDB Index Initialization for Unified Abby Database")
        logger.info("=" * 60)
        
        # Verify database connection
        db = get_database()
        logger.info(f"Connected to database: {db.name}")
        
        # Create all indexes
        logger.info("\nCreating indexes for all collections...")
        create_system_state_indexes(db)
        
        # Verify indexes created
        logger.info("\nVerifying indexes...")
        collections = ["system_state", "system_state_instances", "users", "sessions", "xp", "economy", "submissions", "rag_documents"]
        
        for coll_name in collections:
            coll = db[coll_name]
            try:
                indexes = list(coll.list_indexes())
                logger.info(f"\n{coll_name}: {len(indexes)} indexes")
                for idx in indexes:
                    logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
            except Exception as e:
                logger.warning(f"Could not list indexes for {coll_name}: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Index initialization complete!")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Index initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()
