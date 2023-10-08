# from bson import Binary
import base64
import os
from datetime import datetime

import pymongo
import utils.bdcrypt as bdcrypt
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from utils.log_config import logging, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Load the environment variables from .env file
load_dotenv()


def connect_to_mongodb():
    # Retrieve the values from environment variables
    mongodb_user = os.getenv("MONGODB_USER")
    mongodb_pass = os.getenv("MONGODB_PASS")

    # Construct the connection string using f-strings
    uri = f"mongodb+srv://{mongodb_user}:{mongodb_pass}@breeze.idnmz9k.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(uri, server_api=ServerApi('1'))

    return client


def update_user_metadata(user_id, username):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]

        # Specify the collection
        users_collection = db["Discord Profile"]

        # Define the metadata document
        user_metadata = {
            'discord_id': user_id,
            'username': username,
            'last_updated': datetime.utcnow()
            # Add other fields here as necessary
        }

        # Update the user's metadata in the database
        users_collection.update_one({'discord_id': user_id}, {
                                    '$set': user_metadata}, upsert=True)
        logger.info("[📗] Successfully Updated User Metadata!")
    except Exception as e:
        logger.warning("[❌] update_user_metadata error")
        logger.warning(str(e))


def insert_interaction(user_id, session_id, chat_input, chat_response):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]
        # Specify the collection
        sessions_collection = db["Chat Sessions"]

        encrypted_message = bdcrypt.encrypt(chat_input, user_id)
        encrypted_response = bdcrypt.encrypt(chat_response, user_id)
        # Create the interaction to insert
        interaction = {
            "input": encrypted_message,
            "response": encrypted_response
        }

        # Check if a document for this session exists
        session_doc = sessions_collection.find_one({"session_id": session_id})
        if session_doc:
            # If it exists, append the interaction to the interactions array
            result = sessions_collection.update_one(
                {"session_id": session_id},
                {"$push": {"interactions": interaction}}
            )
        else:
            # If it does not exist, create a new document
            new_object = {
                "user_id": user_id,
                "session_id": session_id,
                "interactions": [interaction],
                "summary": None
            }
            result = sessions_collection.insert_one(new_object)

        # Check if the operation was successful
        if result:
            logger.info("[📗] Interaction inserted/updated successfully!")
        else:
            logger.warning("[❌] Failed to insert/update interaction.")

    except Exception as e:
        logger.warning(e)


def get_session(user_id, session_id):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]

        # Specify the collection
        sessions_collection = db["Chat Sessions"]

        # Retrieve the document for this session
        session_doc = sessions_collection.find_one({"session_id": session_id})

        if session_doc:
            # Decrypt all interactions
            session = []
            for interaction in session_doc["interactions"]:
                chat_input = bdcrypt.decrypt(interaction["input"], user_id)
                chat_response = bdcrypt.decrypt(
                    interaction["response"], user_id)

                session.append({
                    "input": chat_input,
                    "response": chat_response
                })

            # Return the session as a JSON object
            return {
                "session": session
            }

        else:
            # Handle the case where there are no documents
            return None

    except Exception as e:
        logger.warning("get_session error")
        logger.warning(str(e))


def update_summary(user_id, session_id, summary):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]
        # Specify the collection
        sessions_collection = db["Chat Sessions"]
        # logger.info(f"[📗] Summary of last session: {summary}")
        encrypted_summary = bdcrypt.encrypt(summary, user_id)

        # Update the summary field in the document for this session
        result = sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"summary": encrypted_summary}}
        )

        # Check if the operation was successful
        if result:
            logger.info("[📗] Summary updated successfully!")
        else:
            logger.warning("[❌] Failed to update summary.")

    except Exception as e:
        logger.warning("[❌] update_summary error")
        logger.warning(str(e))


def get_last_summary(user_id):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]
        # Specify the collection
        sessions_collection = db["Chat Sessions"]

        # Fetch the most recent document by sorting in descending order based on _id
        last_session = sessions_collection.find_one(
            sort=[('_id', pymongo.DESCENDING)])

        # Extract summary if exists
        if last_session and "summary" in last_session:
            decrypted_summary = bdcrypt.decrypt(
                last_session["summary"], user_id)
            # logger.info(f"Summary found: {decrypted_summary}")
            return decrypted_summary
        else:
            logger.warning("[❌] No Summary found!")
            return None

    except Exception as e:
        logger.warning("[❌] get_last_summary error")
        logger.warning(str(e))


def get_profile(user_id):
    client = connect_to_mongodb()
    try:
        client.admin.command('ping')
        # logger.info("[📗] [get_profile] Successfully connected to MongoDB!")
    except Exception as e:
        logger.warning(e)

    try:
        db = client[f"User_{user_id}"]
        users_collection = db["Profiles"]

        # Retrieve all documents from the collection and convert the cursor to a list
        documents = list(users_collection.find())
        # Check if there are any documents
        if documents:
            # Get the last document from the list
            last_entry = documents[-1]

            # Do something with the last entry
            return last_entry
        else:
            # Handle the case where there are no documents
            return None
    except pymongo.errors.CollectionInvalid:
        # Handle the case where the collection doesn't exist
        return None


def get_genres():
    client = connect_to_mongodb()
    try:
        client.admin.command('ping')
        logger.info("[📗] [get_genres] Successfully connected to MongoDB!")
    except Exception as e:
        logger.warning(e)

    try:
        db = client[f"Music"]
        genre_collection = db["Genres"]

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
    db = client['Music']
    collection = db['promo_sessions']
    # Assuming there's only one document in the collection
    session = collection.find_one({})
    return session[session_length] if session and session_length in session else None


def get_personality():
    client = connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personality"]
    # Fetch the personality document from MongoDB
    return collection.find_one({"_id": "personality"})


def update_personality(new_personality):
    client = connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personality"]
    # Update the personality document in MongoDB
    collection.update_one({"_id": "personality"}, {
                          "$set": {"personality_number": new_personality}}, upsert=True)
    
# Tasks

def get_user_tasks(user_id):
    client = connect_to_mongodb()
    db = client[f"Abbys_Tasks"]
    collection = db[f"{user_id}"]
    #If the collection is empty, return None
    if collection.count_documents({}) == 0:
        return None
    # Fetch the tasks document from MongoDB
    return collection.find_one({"_id": "tasks"})

def add_task(user_id, task_description, task_time):
    client = connect_to_mongodb()
    db = client["Abbys_Tasks"]
    collection = db["tasks"]

    task = {
        'userID': user_id,
        'taskDescription': task_description,
        'taskTime': task_time,
    }

    collection.insert_one(task)

def delete_task(task_id):
    client = connect_to_mongodb()
    db = client["Abbys_Tasks"]
    collection = db["tasks"]

    collection.delete_one({"_id": task_id})