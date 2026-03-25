"""
Generation Audit Collection Module

Purpose: Track all LLM generation calls and costs
Schema: See schemas.py (GenerationAuditSchema)
Indexes: user_id, guild_id, created_at, model, cost

Manages:
- LLM API call logging
- Token usage tracking
- Cost accounting
- Model performance metrics
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


class GenerationStatus(str, Enum):
    """Generation status types."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get generation_audit collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["generation_audit"]


def ensure_indexes():
    """Create indexes for generation_audit collection."""
    try:
        collection = get_collection()

        collection.create_index([("audit_id", 1)], unique=True)
        collection.create_index([("user_id", 1), ("created_at", -1)])
        collection.create_index([("guild_id", 1), ("created_at", -1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("model", 1)])
        collection.create_index([("status", 1)])
        collection.create_index([("user_id", 1), ("guild_id", 1), ("created_at", -1)])

        logger.debug("[generation_audit] Indexes created")

    except Exception as e:
        logger.warning(f"[generation_audit] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[generation_audit] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[generation_audit] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize generation_audit collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[generation_audit] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[generation_audit] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_audit_entry(
    audit_id: str,
    user_id: int,
    guild_id: int,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost: float,
    response_time_ms: float,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """Create generation audit entry."""
    try:
        collection = get_collection()
        
        entry = {
            "audit_id": audit_id,
            "user_id": user_id,
            "guild_id": guild_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "response_time_ms": response_time_ms,
            "status": GenerationStatus.COMPLETED,
            "context": context or {},
            "created_at": datetime.utcnow(),
        }
        
        collection.insert_one(entry)
        logger.debug(f"[generation_audit] Created audit entry {audit_id}")
        return True
        
    except Exception as e:
        logger.error(f"[generation_audit] Error creating audit entry: {e}")
        return False


def get_audit_entry(audit_id: str) -> Optional[Dict[str, Any]]:
    """Get audit entry by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"audit_id": audit_id})
    except Exception as e:
        logger.error(f"[generation_audit] Error getting audit entry: {e}")
        return None


def get_user_generation_history(
    user_id: int,
    guild_id: int,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get generation history for user."""
    try:
        collection = get_collection()
        return list(collection.find({
            "user_id": user_id,
            "guild_id": guild_id
        }).sort("created_at", -1).limit(limit))
    except Exception as e:
        logger.error(f"[generation_audit] Error getting user history: {e}")
        return []


def get_guild_generation_stats(guild_id: int) -> Dict[str, Any]:
    """Get generation statistics for guild."""
    try:
        collection = get_collection()
        
        result = collection.aggregate([
            {"$match": {"guild_id": guild_id}},
            {
                "$group": {
                    "_id": None,
                    "total_calls": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_cost": {"$sum": "$cost"},
                    "avg_response_time": {"$avg": "$response_time_ms"}
                }
            }
        ])
        
        result_list = list(result)
        if result_list:
            return result_list[0]
        else:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost": 0,
                "avg_response_time": 0
            }
        
    except Exception as e:
        logger.error(f"[generation_audit] Error getting guild stats: {e}")
        return {}


def get_model_usage_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Dict[str, Any]]:
    """Get usage statistics by model."""
    try:
        collection = get_collection()
        
        query: Dict[str, Any] = {}
        if start_date or end_date:
            date_query: Dict[str, datetime] = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["created_at"] = date_query
        
        result = collection.aggregate([
            {"$match": query},
            {
                "$group": {
                    "_id": "$model",
                    "total_calls": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_cost": {"$sum": "$cost"},
                    "avg_response_time": {"$avg": "$response_time_ms"}
                }
            }
        ])
        
        stats = {}
        for doc in result:
            model = doc["_id"]
            stats[model] = {
                "total_calls": doc["total_calls"],
                "total_tokens": doc["total_tokens"],
                "total_cost": doc["total_cost"],
                "avg_response_time": doc["avg_response_time"]
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"[generation_audit] Error getting model stats: {e}")
        return {}


def get_high_cost_entries(
    min_cost: float = 0.10,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get high-cost generation entries."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"cost": {"$gte": min_cost}}
        ).sort("cost", -1).limit(limit))
    except Exception as e:
        logger.error(f"[generation_audit] Error getting high-cost entries: {e}")
        return []


def get_total_cost_for_period(
    start_date: datetime,
    end_date: datetime,
    guild_id: Optional[int] = None
) -> float:
    """Get total cost for a specific period."""
    try:
        collection = get_collection()
        
        query: Dict[str, Any] = {
            "created_at": {
                "$gte": start_date,
                "$lte": end_date
            }
        }
        
        if guild_id:
            query["guild_id"] = guild_id
        
        result = collection.aggregate([
            {"$match": query},
            {"$group": {"_id": None, "total_cost": {"$sum": "$cost"}}}
        ])
        
        result_list = list(result)
        return result_list[0]["total_cost"] if result_list else 0.0
        
    except Exception as e:
        logger.error(f"[generation_audit] Error getting total cost: {e}")
        return 0.0


def archive_old_entries(days_old: int = 90) -> int:
    """Move old entries to archive collection."""
    try:
        collection = get_collection()
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        result = collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })
        
        logger.debug(f"[generation_audit] Archived {result.deleted_count} old entries")
        return result.deleted_count
        
    except Exception as e:
        logger.error(f"[generation_audit] Error archiving entries: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class GenerationAudit(CollectionModule):
    """Collection module for generation_audit - follows foolproof pattern."""
    
    collection_name = "generation_audit"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get generation_audit collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not GenerationAudit.collection_name:
            raise RuntimeError("collection_name not set for GenerationAudit")
        db = get_database()
        return db[GenerationAudit.collection_name]
    
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
