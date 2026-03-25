"""
Economy Collection Module

Purpose: Unified balance and transaction tracking
Schema: See schemas.py (EconomySchema)
Indexes: user_id+guild_id, guild_id+balance (leaderboard), created_at

Manages:
- Wallet and bank balances
- Transaction history
- User economic data
- Balance transfers
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pymongo.collection import Collection

from abby_core.database.base import CollectionModule
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# COLLECTION ACCESS (Singleton Pattern)
# ═══════════════════════════════════════════════════════════════

def get_collection() -> "Collection[Dict[str, Any]]":
    """Get economy collection (singleton)."""
    if not get_database:
        raise RuntimeError("MongoDB connection not available")
    db = get_database()
    return db["economy"]


# ═══════════════════════════════════════════════════════════════
# INDEXES
# ═══════════════════════════════════════════════════════════════

def ensure_indexes():
    """Create indexes for economy collection."""
    try:
        collection = get_collection()

        # Primary queries
        collection.create_index([("user_id", 1), ("guild_id", 1)])
        
        # Leaderboard queries
        collection.create_index([("guild_id", 1), ("wallet_balance", -1)])
        collection.create_index([("guild_id", 1), ("bank_balance", -1)])
        
        # Time-based queries
        collection.create_index([("created_at", -1)])
        
        # Transaction queries
        collection.create_index([("user_id", 1), ("transactions.ts", -1)])

        logger.debug("[economy] Indexes created")

    except Exception as e:
        logger.warning(f"[economy] Error creating indexes: {e}")


# ═══════════════════════════════════════════════════════════════
# DEFAULTS / SEEDING
# ═══════════════════════════════════════════════════════════════

def seed_defaults() -> bool:
    """Seed default data if needed."""
    try:
        collection = get_collection()

        # Economy data is created on-demand for each user
        logger.debug("[economy] No defaults to seed (on-demand creation)")
        return True

    except Exception as e:
        logger.error(f"[economy] Error seeding: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════

def initialize_collection() -> bool:
    """
    Initialize economy collection.

    Called automatically at platform startup.

    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_indexes()
        seed_defaults()

        logger.debug("[economy] Collection initialized")
        return True

    except Exception as e:
        logger.error(f"[economy] Error initializing: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# CRUD OPERATIONS
# ═══════════════════════════════════════════════════════════════

def get_user_balance(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Get user's balance information."""
    try:
        collection = get_collection()
        return collection.find_one({"user_id": user_id, "guild_id": guild_id})
    except Exception as e:
        logger.error(f"[economy] Error getting balance for user {user_id}: {e}")
        return None


def initialize_user_economy(user_id: int, guild_id: int, starting_balance: int = 0) -> bool:
    """Initialize economy record for a new user."""
    try:
        collection = get_collection()
        
        economy_data = {
            "user_id": user_id,
            "guild_id": guild_id,
            "wallet_balance": starting_balance,
            "bank_balance": 0,
            "total_earned": 0,
            "total_spent": 0,
            "transactions": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        collection.insert_one(economy_data)
        logger.debug(f"[economy] Initialized economy for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[economy] Error initializing economy for user {user_id}: {e}")
        return False


def add_balance(user_id: int, guild_id: int, amount: int, reason: str = "") -> bool:
    """Add balance to user's wallet."""
    try:
        if amount < 0:
            logger.warning(f"[economy] Negative amount for add_balance: {amount}")
            return False
            
        collection = get_collection()
        
        transaction = {
            "type": "credit",
            "amount": amount,
            "reason": reason,
            "ts": datetime.utcnow(),
        }
        
        result = collection.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {
                "$inc": {
                    "wallet_balance": amount,
                    "total_earned": amount,
                },
                "$push": {"transactions": transaction},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[economy] User {user_id} not found in {guild_id}")
            return False
            
        logger.debug(f"[economy] Added {amount} to user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[economy] Error adding balance: {e}")
        return False


def remove_balance(user_id: int, guild_id: int, amount: int, reason: str = "") -> bool:
    """Remove balance from user's wallet."""
    try:
        if amount < 0:
            logger.warning(f"[economy] Negative amount for remove_balance: {amount}")
            return False
            
        collection = get_collection()
        
        # Check sufficient balance
        user_data = get_user_balance(user_id, guild_id)
        if not user_data or user_data.get("wallet_balance", 0) < amount:
            logger.warning(f"[economy] Insufficient balance for user {user_id}")
            return False
        
        transaction = {
            "type": "debit",
            "amount": amount,
            "reason": reason,
            "ts": datetime.utcnow(),
        }
        
        result = collection.update_one(
            {"user_id": user_id, "guild_id": guild_id},
            {
                "$inc": {
                    "wallet_balance": -amount,
                    "total_spent": amount,
                },
                "$push": {"transactions": transaction},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"[economy] User {user_id} not found in {guild_id}")
            return False
            
        logger.debug(f"[economy] Removed {amount} from user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"[economy] Error removing balance: {e}")
        return False


def get_guild_leaderboard(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by balance in a guild."""
    try:
        collection = get_collection()
        return list(collection.find(
            {"guild_id": guild_id},
            sort=[("wallet_balance", -1)],
            limit=limit
        ))
    except Exception as e:
        logger.error(f"[economy] Error getting leaderboard: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# COLLECTION MODULE PATTERN (Foolproof)
# ═══════════════════════════════════════════════════════════════

class Economy(CollectionModule):
    """Collection module for economy - follows foolproof pattern."""
    
    collection_name = "economy"
    
    @staticmethod
    def get_collection() -> "Collection[Dict[str, Any]]":
        """Get economy collection."""
        if not get_database:
            raise RuntimeError("MongoDB connection not available")
        if not Economy.collection_name:
            raise RuntimeError("collection_name not set for Economy")
        db = get_database()
        return db[Economy.collection_name]
    
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
