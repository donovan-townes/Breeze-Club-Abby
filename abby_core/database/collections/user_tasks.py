"""
User Tasks Collection Module

Purpose: Manage user daily/weekly tasks and goals
Schema: See schemas.py (UserTaskSchema)
Indexes: user_id, guild_id, task_id, status, due_date

Manages:
- User task tracking
- Progress tracking
- Task rewards
- Task completion history
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status types."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get user_tasks collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["user_tasks"]


def ensure_indexes():
    """Create indexes for user_tasks collection."""
    try:
        collection = get_collection()

        collection.create_index([("task_id", 1)], unique=True)
        collection.create_index([("user_id", 1), ("guild_id", 1)])
        collection.create_index([("user_id", 1), ("status", 1)])
        collection.create_index([("guild_id", 1), ("status", 1)])
        collection.create_index([("due_date", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("completed_at", -1)])

        logger.debug("[user_tasks] Indexes created")

    except Exception as e:
        logger.warning(f"[user_tasks] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[user_tasks] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[user_tasks] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize user_tasks collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[user_tasks] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[user_tasks] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_task(
    task_id: str,
    user_id: int,
    guild_id: int,
    title: str,
    description: str,
    reward: float,
    due_date: datetime,
    difficulty: str = "medium",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create a new user task."""
    try:
        collection = get_collection()
        
        task = {
            "task_id": task_id,
            "user_id": user_id,
            "guild_id": guild_id,
            "title": title,
            "description": description,
            "reward": reward,
            "due_date": due_date,
            "difficulty": difficulty,
            "status": TaskStatus.ACTIVE,
            "progress": 0,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "completed_at": None,
        }
        
        collection.insert_one(task)
        logger.debug(f"[user_tasks] Created task {task_id} for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[user_tasks] Error creating task: {e}")
        return False


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"task_id": task_id})
    except Exception as e:
        logger.error(f"[user_tasks] Error getting task: {e}")
        return None


def get_user_active_tasks(user_id: int, guild_id: int) -> List[Dict[str, Any]]:
    """Get active tasks for user in guild."""
    try:
        collection = get_collection()
        return list(collection.find({
            "user_id": user_id,
            "guild_id": guild_id,
            "status": TaskStatus.ACTIVE
        }).sort("due_date", 1))
    except Exception as e:
        logger.error(f"[user_tasks] Error getting active tasks: {e}")
        return []


def get_user_completed_tasks(
    user_id: int,
    guild_id: int,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get completed tasks for user."""
    try:
        collection = get_collection()
        return list(collection.find({
            "user_id": user_id,
            "guild_id": guild_id,
            "status": TaskStatus.COMPLETED
        }).sort("completed_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[user_tasks] Error getting completed tasks: {e}")
        return []


def get_guild_tasks_by_status(
    guild_id: int,
    status: str
) -> List[Dict[str, Any]]:
    """Get all tasks for guild with specific status."""
    try:
        collection = get_collection()
        return list(collection.find({
            "guild_id": guild_id,
            "status": status
        }))
    except Exception as e:
        logger.error(f"[user_tasks] Error getting guild tasks: {e}")
        return []


def update_task_progress(
    task_id: str,
    progress: float
) -> bool:
    """Update task progress (0-100)."""
    try:
        collection = get_collection()
        
        # Clamp progress to 0-100
        progress = max(0, min(100, progress))
        
        result = collection.update_one(
            {"task_id": task_id},
            {"$set": {"progress": progress}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[user_tasks] Task {task_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[user_tasks] Error updating progress: {e}")
        return False


def complete_task(task_id: str) -> bool:
    """Mark task as completed."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": TaskStatus.COMPLETED,
                    "progress": 100,
                    "completed_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[user_tasks] Task {task_id} not found")
            return False
            
        logger.debug(f"[user_tasks] Completed task {task_id}")
        return True
        
    except Exception as e:
        logger.error(f"[user_tasks] Error completing task: {e}")
        return False


def abandon_task(task_id: str) -> bool:
    """Mark task as abandoned."""
    try:
        collection = get_collection()
        
        result = collection.update_one(
            {"task_id": task_id},
            {"$set": {"status": TaskStatus.ABANDONED}}
        )
        
        if result.matched_count == 0:
            logger.warning(f"[user_tasks] Task {task_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[user_tasks] Error abandoning task: {e}")
        return False


def delete_task(task_id: str) -> bool:
    """Delete task."""
    try:
        collection = get_collection()
        
        result = collection.delete_one({"task_id": task_id})
        
        if result.deleted_count == 0:
            logger.warning(f"[user_tasks] Task {task_id} not found")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"[user_tasks] Error deleting task: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class UserTasks(CollectionModule):
    """Collection module for user_tasks - follows foolproof pattern."""
    
    collection_name = "user_tasks"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get user_tasks collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not UserTasks.collection_name:
            raise RuntimeError("collection_name not set for UserTasks")
        db = get_database()
        return db[UserTasks.collection_name]
    
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
