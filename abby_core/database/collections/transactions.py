"""
Transactions Collection Module

Purpose: Audit trail for all economy transactions
Schema: See schemas.py (TransactionSchema)
Indexes: user_id, guild_id, transaction_type, created_at

Manages:
- Transaction history
- Economy audit trail
- Transaction analytics
- Dispute tracking
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


class TransactionType(str, Enum):
    """Transaction types."""
    TRANSFER = "transfer"
    EARN = "earn"
    SPEND = "spend"
    REFUND = "refund"
    PENALTY = "penalty"
    BONUS = "bonus"


def get_collection() -> "Collection[Dict[str, Any]]":
    """Get transactions collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["transactions"]


def ensure_indexes():
    """Create indexes for transactions collection."""
    try:
        collection = get_collection()

        def _ensure_unique_partial_index(name: str, key: list[tuple[str, int]], filter_expr: Dict[str, Any]) -> None:
            existing = next((idx for idx in collection.list_indexes() if idx.get("name") == name), None)
            if existing:
                existing_key = dict(existing.get("key", {}))
                if existing_key == dict(key):
                    if existing.get("partialFilterExpression") != filter_expr:
                        collection.drop_index(name)
            collection.create_index(
                key,
                unique=True,
                partialFilterExpression=filter_expr,
                name=name,
            )

        _ensure_unique_partial_index(
            "transaction_id_1",
            [("transaction_id", 1)],
            {"transaction_id": {"$type": "string"}},
        )
        collection.create_index([("user_id", 1), ("created_at", -1)])
        collection.create_index([("guild_id", 1), ("created_at", -1)])
        collection.create_index([("transaction_type", 1)])
        collection.create_index([("created_at", -1)])
        collection.create_index([("user_id", 1), ("guild_id", 1), ("created_at", -1)])

        logger.debug("[transactions] Indexes created")

    except Exception as e:
        logger.warning(f"[transactions] Error creating indexes: {e}")


def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        logger.debug("[transactions] No defaults to seed (on-demand creation)")
        return True
    except Exception as e:
        logger.error(f"[transactions] Error seeding: {e}")
        return False


def initialize_collection() -> bool:
    """Initialize transactions collection."""
    try:
        ensure_indexes()
        seed_defaults()
        logger.debug("[transactions] Collection initialized")
        return True
    except Exception as e:
        logger.error(f"[transactions] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def create_transaction(
    transaction_id: str,
    user_id: int,
    guild_id: int,
    amount: float,
    transaction_type: str,
    description: str,
    from_user_id: Optional[int] = None,
    to_user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Create transaction record."""
    try:
        collection = get_collection()
        
        transaction = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "guild_id": guild_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "description": description,
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
        }
        
        collection.insert_one(transaction)
        logger.debug(f"[transactions] Created transaction {transaction_id}")
        return True
        
    except Exception as e:
        logger.error(f"[transactions] Error creating transaction: {e}")
        return False


def get_transaction(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Get transaction by ID."""
    try:
        collection = get_collection()
        return collection.find_one({"transaction_id": transaction_id})
    except Exception as e:
        logger.error(f"[transactions] Error getting transaction: {e}")
        return None


def get_user_transactions(
    user_id: int,
    guild_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get recent transactions for user."""
    try:
        collection = get_collection()
        
        query: Dict[str, Any] = {"user_id": user_id}
        if guild_id:
            query["guild_id"] = guild_id
        
        return list(collection.find(query)
                   .sort("created_at", -1)
                   .limit(limit))
    except Exception as e:
        logger.error(f"[transactions] Error getting user transactions: {e}")
        return []


def get_guild_transactions(
    guild_id: int,
    transaction_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get recent transactions for guild."""
    try:
        collection = get_collection()
        
        query: Dict[str, Any] = {"guild_id": guild_id}
        if transaction_type:
            query["transaction_type"] = transaction_type
        
        return list(collection.find(query)
                   .sort("created_at", -1)
                   .limit(limit))
    except Exception as e:
        logger.error(f"[transactions] Error getting guild transactions: {e}")
        return []


def get_transfer_history(
    from_user_id: int,
    to_user_id: int,
    guild_id: int
) -> List[Dict[str, Any]]:
    """Get transfer history between two users."""
    try:
        collection = get_collection()
        
        return list(collection.find({
            "guild_id": guild_id,
            "transaction_type": TransactionType.TRANSFER,
            "$or": [
                {"from_user_id": from_user_id, "to_user_id": to_user_id},
                {"from_user_id": to_user_id, "to_user_id": from_user_id}
            ]
        }).sort("created_at", -1))
    except Exception as e:
        logger.error(f"[transactions] Error getting transfer history: {e}")
        return []


def get_total_user_earnings(
    user_id: int,
    guild_id: int
) -> float:
    """Get total earnings for user in guild."""
    try:
        collection = get_collection()
        
        result = collection.aggregate([
            {
                "$match": {
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "transaction_type": {"$in": [TransactionType.EARN, TransactionType.BONUS]}
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ])
        
        result_list = list(result)
        return result_list[0]["total"] if result_list else 0.0
        
    except Exception as e:
        logger.error(f"[transactions] Error getting earnings: {e}")
        return 0.0


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class Transactions(CollectionModule):
    """Collection module for transactions - follows foolproof pattern."""
    
    collection_name = "transactions"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get transactions collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not Transactions.collection_name:
            raise RuntimeError("collection_name not set for Transactions")
        db = get_database()
        return db[Transactions.collection_name]
    
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
