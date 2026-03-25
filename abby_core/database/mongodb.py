# from bson import Binary
import base64
import os
from datetime import datetime
from typing import Optional

import pymongo
import abby_core.security.encryption as encryption
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from abby_core.observability.logging import logging, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Load the environment variables from .env file (if not already loaded by launch.py)
# In production, launch.py loads from /srv/tserver/compose/abby.env
# In development, it loads from .env in the root directory
# This is a fallback for direct imports of this module
try:
    load_dotenv()
except:
    pass

# Global MongoDB client (singleton pattern for connection pooling)
_mongodb_client = None
_mongodb_available = None  # Cache health check result
_db_name_logged = False  # Track if we've logged the DB name to reduce noise


def _get_db_name():
    """Return the configured DB name, respecting dev environment."""
    global _db_name_logged
    
    # Check if running in dev mode (MONGODB_DB_DEV takes precedence in dev only)
    # CRITICAL: Only check MONGODB_DB_DEV if explicitly in dev mode
    mode = os.getenv("ABBY_MODE", "prod")
    if mode == "dev":
        dev_db = os.getenv("MONGODB_DB_DEV")
        if dev_db:
            # Only log once during startup to avoid spam
            if not _db_name_logged:
                logger.debug(f"[📗] Using dev database: {dev_db}")
                _db_name_logged = True
            return dev_db
    
    # Fallback to MONGODB_DB or default (production path)
    db_name = os.getenv("MONGODB_DB", "Abby_Database")
    if not _db_name_logged:
        logger.debug(f"[📗] Using database: {db_name}")
        _db_name_logged = True
    return db_name

def connect_to_mongodb():
    """Get or create a shared MongoDB client connection with proper write concern.
    
    Note: MongoClient is lazy - it doesn't actually connect until first operation.
    Use check_mongodb_health() to verify connectivity.
    """
    global _mongodb_client
    
    if _mongodb_client is None:
        # Prefer explicit URI if provided (local or custom clusters)
        explicit_uri = os.getenv("MONGODB_URI")
        if explicit_uri:
            uri = explicit_uri.strip()
        else:
            # Fallback to legacy SRV using user/pass
            mongodb_user = os.getenv("MONGODB_USER")
            mongodb_pass = os.getenv("MONGODB_PASS")
            # Cloud MongoDB URI with write concern
            uri = f"mongodb+srv://{mongodb_user}:{mongodb_pass}@breeze.idnmz9k.mongodb.net/?retryWrites=true&w=majority"

        _mongodb_client = MongoClient(uri, server_api=ServerApi('1'))
        logger.debug("[📗] MongoDB client object created (connection lazy, not yet verified)")
    
    return _mongodb_client


def get_database():
    """Get the main Abby database from MongoDB connection."""
    client = connect_to_mongodb()
    return client[_get_db_name()]


# Alias for backward compatibility
get_db = get_database


def get_profile(user_id):
    from abby_core.database.collections.users import Users
    try:
        # Use Users collection as source of truth
        return Users.get_collection().find_one({"user_id": str(user_id)})
    except Exception as e:
        logger.error(f"[❌] Failed to fetch profile for {user_id}: {e}")
        return None


def get_genres():
    client = connect_to_mongodb()
    try:
        client.admin.command('ping')
        logger.info("[📗] [get_genres] Successfully connected to MongoDB!")
    except Exception as e:
        logger.warning(e)

    try:
        db = client[_get_db_name()]
        genre_collection = db["music_genres"]

        # Retrieve the first document from the collection
        document = genre_collection.find_one()
        if document is None:
            # If the collection is empty, return None
            return None

        # Remove the _id field from the document
        document.pop('_id', None)
        return document
    except:
        # Handle the case where the collection doesn't exist
        return None


def get_promo_session(session_length='1_week'):
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db['music_promo_sessions']
    # Assuming there's only one document in the collection
    session = collection.find_one({})
    return session[session_length] if session and session_length in session else None


def get_personality():
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["bot_settings"]
    # Fetch the personality document from MongoDB
    return collection.find_one({"_id": "personality"})


def update_personality(new_personality):
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["bot_settings"]
    # Update the personality document in MongoDB
    collection.update_one({"_id": "personality"}, {
                          "$set": {"personality_number": new_personality}}, upsert=True)
    
# Tasks

def get_user_tasks(user_id):
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["user_tasks"]
    #If the collection is empty, return None
    if collection.count_documents({}) == 0:
        return None
    # Fetch the tasks document from MongoDB
    return collection.find_one({"_id": "tasks"})

def add_task(user_id, task_description, task_time):
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["user_tasks"]

    task = {
        'user_id': str(user_id),  # Standardized field name
        'taskDescription': task_description,
        'taskTime': task_time,
    }

    collection.insert_one(task)

def delete_task(task_id):
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["user_tasks"]

    collection.delete_one({"_id": task_id})

# ==================== Session Management Functions ====================
# NOTE: Deprecated session helpers (create_session, append_session_message, close_session) have been removed.
# Session management now goes through unified content_delivery pipeline and session_repository.py data layer.
# Legacy session.py module has been deleted as it was unused.
# See AUDIT.md for deprecation details.

def get_sessions_collection():
    """Get the unified chat sessions collection from Abby_Database."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["chat_sessions"]


# ==================== User Management ====================


def upsert_user(user_id: int, username: str, **kwargs):
    """Create or update user profile in the universal users collection."""
    try:
        from abby_core.database.collections.users import Users

        collection = Users.get_collection()

        platform = kwargs.pop("_platform", "discord")

        # Universal schema: platform-specific fields must be nested
        set_doc = {
            "user_id": str(user_id),
            "updated_at": datetime.utcnow(),
        }

        if platform == "discord":
            set_doc.update({
                "discord.discord_id": str(user_id),
                "discord.username": username,
            })

            # Map known discord fields from kwargs into the discord object
            discord_fields = {
                "discriminator": "discord.discriminator",
                "display_name": "discord.display_name",
                "avatar_url": "discord.avatar_url",
                "last_seen": "discord.last_seen",
                "joined_at": "discord.joined_at",
            }
            for key, target in discord_fields.items():
                if key in kwargs:
                    set_doc[target] = kwargs.pop(key)

        # Preserve any explicitly passed nested discord object (merge safely)
        if "discord" in kwargs and isinstance(kwargs["discord"], dict):
            for key, value in kwargs.pop("discord").items():
                set_doc[f"discord.{key}"] = value

        # Pass through any remaining kwargs as-is (non-platform fields only)
        for key, value in kwargs.items():
            set_doc[key] = value

        # Remove old root-level platform fields if they exist
        unset_doc = {
            "username": 1,
            "last_updated": 1,
            "discriminator": 1,
            "display_name": 1,
            "avatar_url": 1,
            "last_seen": 1,
            "joined_at": 1,
        }

        collection.update_one(
            {"user_id": str(user_id)},
            {
                "$set": set_doc,
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$unset": unset_doc,
            },
            upsert=True,
        )
        logger.debug(f"[📗] Upserted user {username} ({user_id})")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to upsert user: {e}")
        return False


# ==================== Economy Management ====================

def get_economy(user_id, guild_id=None):
    """Get user's economy data (wallet/bank) scoped by guild."""
    client = connect_to_mongodb()
    try:
        db = client[_get_db_name()]
        collection = db["economy"]
        query = {"user_id": str(user_id)}
        if guild_id is not None:
            query["guild_id"] = str(guild_id)
        return collection.find_one(query)
    except Exception as e:
        logger.error(f"[❌] Failed to fetch economy for {user_id}: {e}")
        return None


def update_balance(user_id, wallet_delta=0, bank_delta=0, guild_id=None):
    """Update user's wallet and/or bank balance using canonical field names."""
    client = connect_to_mongodb()
    try:
        db = client[_get_db_name()]
        collection = db["economy"]

        update_doc = {}
        
        # Use $inc for balance changes; MongoDB treats missing fields as 0
        inc_doc = {}
        if wallet_delta != 0:
            inc_doc['wallet_balance'] = wallet_delta
        if bank_delta != 0:
            inc_doc['bank_balance'] = bank_delta
        if inc_doc:
            update_doc['$inc'] = inc_doc

        # Ensure guild/user identifiers exist on first insert; do NOT include wallet/bank to avoid conflict
        set_on_insert = {
            "user_id": str(user_id),
            "guild_id": str(guild_id) if guild_id is not None else None,
            "transactions": [],
            "last_daily": None,
        }
        update_doc['$setOnInsert'] = set_on_insert

        if update_doc:
            collection.update_one(
                {"user_id": str(user_id), "guild_id": str(guild_id) if guild_id is not None else None},
                update_doc,
                upsert=True
            )
            logger.debug(f"[💰] Updated balance for {user_id} (guild {guild_id}): wallet_delta={wallet_delta}, bank_delta={bank_delta}")
            return True
        return False
    except Exception as e:
        logger.error(f"[❌] Failed to update balance for {user_id}: {e}")
        return False


def list_economies(batch_size=500, guild_id=None):
    """Yield economy documents in batches for periodic tasks (guild-scoped if provided)."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["economy"]
    query = {}
    if guild_id is not None:
        query["guild_id"] = str(guild_id)

    cursor = collection.find(query, batch_size=batch_size)
    for doc in cursor:
        yield doc


def get_active_sessions_count():
    """Return count of active chat sessions for dashboard/heartbeat."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["chat_sessions"]
    return collection.count_documents({"status": {"$in": ["active", "open"]}})


def get_pending_submissions_count():
    """Return count of pending submissions for dashboard/heartbeat."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    collection = db["submissions"]
    return collection.count_documents({"status": {"$in": ["submitted", "pending"]}})


def check_mongodb_health(timeout_ms: int = 2000) -> bool:
    """Check if MongoDB is accessible and responsive.
    
    Args:
        timeout_ms: Connection timeout in milliseconds (default 2s)
        
    Returns:
        True if MongoDB is healthy, False otherwise
    """
    global _mongodb_available
    
    try:
        # Create a quick health check client with short timeout
        # (Don't use the global client since it has long default timeouts)
        explicit_uri = os.getenv("MONGODB_URI")
        if explicit_uri:
            uri = explicit_uri.strip()
        else:
            mongodb_user = os.getenv("MONGODB_USER")
            mongodb_pass = os.getenv("MONGODB_PASS")
            uri = f"mongodb+srv://{mongodb_user}:{mongodb_pass}@breeze.idnmz9k.mongodb.net/?retryWrites=true&w=majority"
        
        # Create temporary client with aggressive timeouts for health check
        health_client = MongoClient(
            uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms
        )
        
        # Quick ping
        health_client.admin.command('ping')
        health_client.close()
        
        _mongodb_available = True
        logger.debug("[📗] MongoDB health check: OK")
        return True
    except Exception as e:
        _mongodb_available = False
        # Log concise error message without full traceback
        error_msg = str(e).split(',')[0] if ',' in str(e) else str(e)
        logger.warning(f"[📗] MongoDB health check: FAILED ({error_msg})")
        return False


def is_mongodb_available() -> bool:
    """Return cached MongoDB availability status.
    
    Returns:
        True if MongoDB was available at last health check, False/None otherwise
    """
    return _mongodb_available if _mongodb_available is not None else False


def log_transaction(user_id, guild_id, transaction_type, amount, balance_after, description=None):
    """Log a bank transaction (deposit/withdraw/transfer/interest/etc.)."""
    from datetime import datetime
    client = connect_to_mongodb()
    try:
        db = client[_get_db_name()]
        collection = db["transactions"]
        doc = {
            "user_id": str(user_id),
            "guild_id": str(guild_id) if guild_id else None,
            "type": transaction_type,
            "amount": amount,
            "balance_after": balance_after,
            "description": description,
            "timestamp": datetime.utcnow(),
        }
        collection.insert_one(doc)
        logger.debug(f"[💰] Logged {transaction_type} for {user_id}: {amount}")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to log transaction for {user_id}: {e}")
        return False


def get_transaction_history(user_id, guild_id=None, limit=10):
    """Retrieve recent transactions for a user (guild-scoped if provided)."""
    client = connect_to_mongodb()
    try:
        db = client[_get_db_name()]
        collection = db["transactions"]
        query = {"user_id": str(user_id)}
        if guild_id is not None:
            query["guild_id"] = str(guild_id)
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        return list(cursor)
    except Exception as e:
        logger.error(f"[❌] Failed to fetch transaction history for {user_id}: {e}")
        return []


def get_tip_budget_remaining(user_id, guild_id=None, daily_limit=1000):
    """
    Get the remaining daily tipping budget for a user.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID (server)
        daily_limit: Maximum coins that can be tipped per day (default: 1000)
    
    Returns:
        int: Remaining budget amount (0 if budget exhausted)
    """
    from datetime import datetime, timedelta
    economy = get_economy(user_id, guild_id)
    
    if not economy:
        return daily_limit  # New user has full budget
    
    tip_budget_reset = economy.get('tip_budget_reset')
    tip_budget_used = economy.get('tip_budget_used', 0)
    
    # Check if budget needs reset (24 hours elapsed)
    now = datetime.utcnow()
    if tip_budget_reset is None or (now - tip_budget_reset) >= timedelta(hours=24):
        return daily_limit  # Budget has reset
    
    # Calculate remaining budget
    remaining = daily_limit - tip_budget_used
    return max(0, remaining)


def reset_tip_budget_if_needed(user_id, guild_id=None):
    """
    Reset user's tipping budget if 24 hours have elapsed.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID (server)
    
    Returns:
        bool: True if budget was reset, False otherwise
    """
    from datetime import datetime, timedelta
    client = connect_to_mongodb()
    try:
        db = client[_get_db_name()]
        collection = db["economy"]
        
        economy = get_economy(user_id, guild_id)
        if not economy:
            return False
        
        tip_budget_reset = economy.get('tip_budget_reset')
        now = datetime.utcnow()
        
        # Check if 24 hours have elapsed
        if tip_budget_reset is None or (now - tip_budget_reset) >= timedelta(hours=24):
            query = {"user_id": str(user_id)}
            if guild_id is not None:
                query["guild_id"] = str(guild_id)
            
            collection.update_one(
                query,
                {
                    "$set": {
                        "tip_budget_used": 0,
                        "tip_budget_reset": now
                    }
                },
                upsert=True
            )
            logger.debug(f"[💸] Reset tip budget for {user_id} (guild {guild_id})")
            return True
        
        return False
    except Exception as e:
        logger.error(f"[❌] Failed to reset tip budget for {user_id}: {e}")
        return False


def increment_tip_budget_used(user_id, guild_id, amount):
    """
    Increment the user's daily tipping budget usage.
    
    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID (server)
        amount: Amount to add to budget usage
    
    Returns:
        bool: True if successful, False otherwise
    """
    from datetime import datetime
    client = connect_to_mongodb()
    try:
        db = client[_get_db_name()]
        collection = db["economy"]
        
        query = {"user_id": str(user_id)}
        if guild_id is not None:
            query["guild_id"] = str(guild_id)
        
        # Initialize budget tracking on first use
        update_doc = {
            "$inc": {"tip_budget_used": amount},
            "$setOnInsert": {
                "user_id": str(user_id),
                "guild_id": str(guild_id) if guild_id is not None else None,
                "tip_budget_reset": datetime.utcnow(),
                "wallet_balance": 0,
                "bank_balance": 0,
                "transactions": [],
                "last_daily": None,
            }
        }
        
        collection.update_one(query, update_doc, upsert=True)
        logger.debug(f"[💸] Incremented tip budget for {user_id} (guild {guild_id}): +{amount}")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to increment tip budget for {user_id}: {e}")
        return False


# ==================== RAG Document Management ====================
def get_rag_documents_collection():
    """Get the unified RAG documents collection (respects dev/prod database)."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]  # Respects MONGODB_DB env var
    return db["rag_documents"]


# ==================== CANON COLLECTION HELPERS ====================
def get_canon_staging_collection():
    """Mutable staging artifacts pending review."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["canon_staging"]


def get_canon_commits_collection():
    """Immutable audit log of canon writes."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["canon_commits"]


def get_canon_lore_collection():
    """Canonical lore documents (append-only)."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["lore_documents"]


def get_canon_persona_identity_collection():
    """Canonical persona identity documents (append-only)."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["persona_identity"]


def get_canon_frontmatter_collection():
    """Canonical book/frontmatter documents (append-only)."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["book_frontmatter"]


def get_canon_appendix_collection():
    """Canonical appendix documents (append-only)."""
    client = connect_to_mongodb()
    db = client[_get_db_name()]
    return db["canon_appendix"]
