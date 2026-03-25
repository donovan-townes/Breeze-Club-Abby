"""
Scheduler Jobs Collection Module

Purpose: Track platform scheduler jobs and their execution state
Schema: Job definitions, execution history, status
Indexes: job_id (unique), status, next_run_at

Manages:
- Scheduled job definitions
- Job execution tracking
- Retry logic and failure tracking
- Next execution scheduling
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get scheduler_jobs collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["scheduler_jobs"]


def ensure_indexes():
    """Create indexes for scheduler_jobs collection."""
    try:
        collection = get_collection()

        collection.create_index(
            [("job_id", 1)],
            unique=True,
            sparse=True,
        )
        collection.create_index([("status", 1)])
        collection.create_index([("next_run_at", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("last_executed_at", -1)])

        logger.debug("[scheduler_jobs] Indexes created")

    except Exception as e:
        logger.warning(f"[scheduler_jobs] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[scheduler_jobs] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[scheduler_jobs] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize scheduler_jobs collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[scheduler_jobs] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[scheduler_jobs] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class SchedulerJobs(CollectionModule):
    """Collection module for scheduler_jobs - follows foolproof pattern."""
    
    collection_name = "scheduler_jobs"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get scheduler_jobs collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not SchedulerJobs.collection_name:
            raise RuntimeError("collection_name not set for SchedulerJobs")
        db = get_database()
        return db[SchedulerJobs.collection_name]
    
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
