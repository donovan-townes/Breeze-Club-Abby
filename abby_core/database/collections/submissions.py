"""
Submissions Collection Module

Purpose: User-submitted content and artwork
Schema: See schemas.py (SubmissionSchema)
Indexes: user_id, guild_id, status, created_at

Manages:
- User submissions (art, content, etc)
- Submission metadata
- Voting and scoring
- Moderation status
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
    """Get submissions collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["submissions"]


def ensure_indexes():
    """Create indexes for submissions collection."""
    try:
        collection = get_collection()

        collection.create_index([("submission_id", 1)], unique=True)
        collection.create_index([("user_id", 1), ("created_at", -1)])
        collection.create_index([("guild_id", 1), ("status", 1)])
        collection.create_index([("status", 1), ("created_at", -1)])
        collection.create_index([("votes", -1)])

        logger.debug("[submissions] Indexes created")

    except Exception as e:
        logger.warning(f"[submissions] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[submissions] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[submissions] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize submissions collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[submissions] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[submissions] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_submission(
    submission_id: str,
    user_id: int,
    guild_id: int,
    content_url: str,
    title: str = "",
    description: str = ""
) -> bool:
    """Create new submission."""
    try:
        collection = get_collection()
        
        submission = {
            "submission_id": submission_id,
            "user_id": user_id,
            "guild_id": guild_id,
            "content_url": content_url,
            "title": title,
            "description": description,
            "status": "pending",
            "votes": 0,
            "voters": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        collection.insert_one(submission)
        logger.debug(f"[submissions] Created submission {submission_id}")
        return True
        
    except Exception as e:
        logger.error(f"[submissions] Error creating submission: {e}")
        return False


def get_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    """Get submission by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"submission_id": submission_id})
    except Exception as e:
        logger.error(f"[submissions] Error getting submission: {e}")
        return None


def update_submission_status(submission_id: str, status: str) -> bool:
    """Update submission status (pending, approved, rejected)."""
    try:
        valid_statuses = ["pending", "approved", "rejected"]
        if status not in valid_statuses:
            logger.warning(f"[submissions] Invalid status: {status}")
            return False
            
        collection = get_collection()
        
        result = collection.update_one(
            {"submission_id": submission_id},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[submissions] Submission {submission_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[submissions] Error updating status: {e}")
        return False


def add_vote(submission_id: str, voter_id: int) -> bool:
    """Add vote to submission."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"submission_id": submission_id},
            {
                "$inc": {"votes": 1},
                "$addToSet": {"voters": voter_id},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[submissions] Submission {submission_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[submissions] Error adding vote: {e}")
        return False


def get_user_submissions(user_id: int, guild_id: int) -> List[Dict[str, Any]]:
    """Get all submissions from user in guild."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"user_id": user_id, "guild_id": guild_id},
            sort=[("created_at", -1)]
        ))
    except Exception as e:
        logger.error(f"[submissions] Error getting user submissions: {e}")
        return []


def get_pending_submissions(guild_id: int) -> List[Dict[str, Any]]:
    """Get all pending submissions in guild."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"guild_id": guild_id, "status": "pending"},
            sort=[("created_at", 1)]
        ))
    except Exception as e:
        logger.error(f"[submissions] Error getting pending submissions: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class Submissions(CollectionModule):
    """Collection module for submissions - follows foolproof pattern."""
    
    collection_name = "submissions"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get submissions collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not Submissions.collection_name:
            raise RuntimeError("collection_name not set for Submissions")
        db = get_database()
        return db[Submissions.collection_name]
    
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
