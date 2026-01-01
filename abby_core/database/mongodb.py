# from bson import Binary
import base64
import os
from datetime import datetime

import pymongo
import abby_core.security.encryption as encryption
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from abby_core.observability.logging import logging, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Load the environment variables from .env file
load_dotenv()

# Global MongoDB client (singleton pattern for connection pooling)
_mongodb_client = None

def connect_to_mongodb():
    """Get or create a shared MongoDB client connection with proper write concern."""
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
        logger.info("[📗] MongoDB client connection established (singleton)")
    
    return _mongodb_client


def get_database():
    """Get the main Abby database from MongoDB connection."""
    client = connect_to_mongodb()
    return client["Abby_Database"]


def get_profile(user_id):
    client = connect_to_mongodb()
    try:
        db = client["Abby_Database"]
        collection = db["discord_profiles"]
        # Profiles are keyed by user_id in the unified database
        return collection.find_one({"user_id": str(user_id)})
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
        db = client["Abby_Database"]
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
    db = client['Abby_Database']
    collection = db['music_promo_sessions']
    # Assuming there's only one document in the collection
    session = collection.find_one({})
    return session[session_length] if session and session_length in session else None


def get_personality():
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Fetch the personality document from MongoDB
    return collection.find_one({"_id": "personality"})


def update_personality(new_personality):
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Update the personality document in MongoDB
    collection.update_one({"_id": "personality"}, {
                          "$set": {"personality_number": new_personality}}, upsert=True)
    
# Tasks

def get_user_tasks(user_id):
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["user_tasks"]
    #If the collection is empty, return None
    if collection.count_documents({}) == 0:
        return None
    # Fetch the tasks document from MongoDB
    return collection.find_one({"_id": "tasks"})

def add_task(user_id, task_description, task_time):
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["user_tasks"]

    task = {
        'user_id': str(user_id),  # Standardized field name
        'taskDescription': task_description,
        'taskTime': task_time,
    }

    collection.insert_one(task)

def delete_task(task_id):
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["user_tasks"]

    collection.delete_one({"_id": task_id})

# ==================== Session Management Functions ====================
def get_sessions_collection():
    """Get the unified chat sessions collection from Abby_Database."""
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    return db["chat_sessions"]


def create_session(user_id: int, session_id: str, channel_id: int = None, guild_id: int = None):
    """Create a new chat session in the unified collection."""
    try:
        collection = get_sessions_collection()
        session_doc = {
            "user_id": str(user_id),
            "guild_id": str(guild_id) if guild_id else None,
            "session_id": session_id,
            "channel_id": str(channel_id) if channel_id else None,
            "interactions": [],
            "summary": None,
            "status": "active",
            "created_at": datetime.utcnow(),
            "closed_at": None
        }
        collection.insert_one(session_doc)
        logger.info(f"[📗] Created session {session_id} for user {user_id}")
        return session_doc
    except Exception as e:
        logger.error(f"[❌] Failed to create session: {e}")
        return None


def append_session_message(user_id: int, session_id: str, role: str, content: str):
    """Append a message to an existing session in the unified collection."""
    try:
        collection = get_sessions_collection()
        encrypted_content = encryption.encrypt(content, user_id)
        
        message = {
            "role": role,
            "content": encrypted_content,
            "timestamp": datetime.utcnow()
        }
        
        result = collection.update_one(
            {"session_id": session_id, "user_id": str(user_id)},
            {"$push": {"interactions": message}}
        )
        
        if result.modified_count > 0:
            logger.info(f"[📗] Appended {role} message to session {session_id}")
        else:
            logger.warning(f"[⚠️] No session found to append {role} message: {session_id}")
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"[❌] Failed to append message: {e}")
        return False


def close_session(user_id: int, session_id: str, summary: str = None):
    """Close a chat session and optionally add a summary in the unified collection."""
    try:
        collection = get_sessions_collection()
        update_doc = {
            "status": "completed",
            "closed_at": datetime.utcnow()
        }
        if summary:
            # Encrypt summary for security
            encrypted_summary = encryption.encrypt(summary, user_id)
            update_doc["summary"] = encrypted_summary
            logger.info(f"[📗] Closing session {session_id} with summary")
        else:
            logger.info(f"[📗] Closing session {session_id} without summary")
            
        result = collection.update_one(
            {"session_id": session_id, "user_id": str(user_id)},
            {"$set": update_doc}
        )
        
        if result.modified_count > 0:
            logger.info(f"[📗] Closed session {session_id}")
        else:
            logger.warning(f"[⚠️] No session found to close: {session_id}")
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"[❌] Failed to close session: {e}")
        return False


def upsert_user(user_id: int, username: str, **kwargs):
    """Create or update user profile in the unified discord_profiles collection."""
    try:
        client = connect_to_mongodb()
        db = client["Abby_Database"]
        collection = db["discord_profiles"]
        
        user_doc = {
            'user_id': str(user_id),
            'username': username,
            'last_updated': datetime.utcnow()
        }
        user_doc.update(kwargs)
        
        collection.update_one(
            {'user_id': str(user_id)},
            {'$set': user_doc},
            upsert=True
        )
        logger.debug(f"[📗] Upserted user {username} ({user_id})")
        return True
    except Exception as e:
        logger.error(f"[❌] Failed to upsert user: {e}")
        return False


# ==================== Economy Management ====================

def get_economy(user_id):
    """Get user's economy data (wallet, bank balance)."""
    client = connect_to_mongodb()
    try:
        db = client["Abby_Database"]
        collection = db["economy"]
        return collection.find_one({"user_id": str(user_id)})
    except Exception as e:
        logger.error(f"[❌] Failed to fetch economy for {user_id}: {e}")
        return None


def update_balance(user_id, wallet_delta=0, bank_delta=0):
    """Update user's wallet and/or bank balance."""
    client = connect_to_mongodb()
    try:
        db = client["Abby_Database"]
        collection = db["economy"]
        
        update_doc = {}
        if wallet_delta != 0:
            update_doc['$inc'] = update_doc.get('$inc', {})
            update_doc['$inc']['wallet'] = wallet_delta
        if bank_delta != 0:
            update_doc['$inc'] = update_doc.get('$inc', {})
            update_doc['$inc']['bank'] = bank_delta
        
        if update_doc:
            collection.update_one(
                {"user_id": str(user_id)},
                update_doc,
                upsert=True
            )
            logger.debug(f"[💰] Updated balance for {user_id}: wallet_delta={wallet_delta}, bank_delta={bank_delta}")
            return True
        return False
    except Exception as e:
        logger.error(f"[❌] Failed to update balance for {user_id}: {e}")
        return False


# ==================== RAG Document Management ====================
def get_rag_documents_collection():
    """Get the unified RAG documents collection from Abby_Database."""
    client = connect_to_mongodb()
    db = client["Abby_Database"]
    return db["rag_documents"]
