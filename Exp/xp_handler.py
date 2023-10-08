
from pymongo import MongoClient
import discord
from discord.ext import commands
from utils.mongo_db import connect_to_mongodb
from utils.log_config import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


# Assuming you already have a MongoClient instance.
client = connect_to_mongodb()

def get_user_exp(user_id):
    db = client[f"User_{user_id}"]
    return db["EXP"]

def initialize_xp(user_id):
    exp = get_user_exp(user_id)
    # Initialize with 0 points. Add other fields as needed.
    exp.insert_one({"points": 0, "level": 1})

def get_user_level(user_id):
    exp = get_user_exp(user_id)
    user_data = exp.find_one({})
    if not user_data or 'level' not in user_data:
        # If the user does not exist or does not have a level field, return a default value
        return 1
    return user_data["level"]

def reset_exp(user_id):
    exp = get_user_exp(user_id)

    exp_data = exp.find_one({})
    if not exp_data:
        # If there is no experience data for this user, initialize it
        initialize_xp(user_id)
    else:
        # If experience data exists, reset points to zero
        exp.update_one({}, {"$set": {"level": 1, "points": 0}})
        logger.info(
            f"[💰] Level & Experience points RESET for user {user_id}.")


def increment_xp(user_id, increment):
    exp = get_user_exp(user_id)
    exp_data = exp.find_one({})
    if not exp_data:
        initialize_xp(user_id)
        exp_data = {"points": 0}

    new_xp = exp_data["points"] + increment
    exp.update_one({}, {"$set": {"points": new_xp}})
    logger.info(f"[💰] User: {user_id} New EXP is {new_xp}")
    leveled_up = check_thresholds(user_id, new_xp)
    return leveled_up


def decrement_xp(user_id, increment):
    exp = get_user_exp(user_id)

    exp_data = exp.find_one({})
    if not exp_data:
        initialize_xp(user_id)
        exp_data = {"points": 0}

    new_xp = exp_data["points"] - increment
    if new_xp < 0:  # if new XP is below zero, set it to zero
        new_xp = 0

    exp.update_one({}, {"$set": {"points": new_xp}})
    logger.info(f"[💰] User: {user_id} New EXP is {new_xp}")
    check_thresholds(user_id, new_xp)

def get_level_from_xp(xp):
    # Calculate level from xp
    base_xp = 1000
    factor = 1.5
    level = int((xp / base_xp) ** (1 / factor))
    return level

def get_xp(user_id):
    exp = get_user_exp(user_id)

    exp_data = exp.find_one({})
    if not exp_data:
        initialize_xp(user_id)
        return 0

    return exp_data["points"]


def update_old_users():
    all_databases = client.list_database_names()
    user_databases = [db for db in all_databases if db.startswith("User_")]

    for user_db in user_databases:
        db = client[user_db]
        exp = db["EXP"]

        user_data = exp.find_one({})
        if 'level' not in user_data:
            exp.update_one({}, {"$set": {"level": 1}})


def check_thresholds(user_id, new_xp):
    exp = get_user_exp(user_id)
    user_data = exp.find_one({})
    if 'level' not in user_data:
        exp.update_one({}, {"$set": {"level": 1}})
        user_data = exp.find_one({})

    current_level = user_data["level"]

    # Calculate the new level based on the new_xp using the get_level_from_xp function
    new_level = get_level_from_xp(new_xp)

    if new_level > current_level:
        exp.update_one({}, {"$set": {"level": new_level}})
        logger.info(f"[💰] User {user_id} leveled up to level {new_level}!")
        return True  # Indicate that the user leveled up

    return False  # Indicate that the user didn't level up


def get_xp_required(level):
    base_xp = 1000
    factor = 1.5

    xp_required = round(base_xp * (level ** factor))
    prev_xp_required = round(base_xp * ((level - 1) ** factor))

    relative_xp_required = xp_required - prev_xp_required
    relative_xp_required = 0 if relative_xp_required != relative_xp_required else relative_xp_required

    return {
        "level": level,
        "xp_required": xp_required,
        "relative_xp_required": relative_xp_required
    }

def fetch_all_users_exp():
    """
    Fetches the experience points of all users from the MongoDB database.
    
    Args:
    - client (MongoClient): The MongoDB client instance.
    
    Returns:
    - dict: A dictionary with user IDs as keys and experience points as values.
    """
    client = connect_to_mongodb()
    all_databases = client.list_database_names()
    user_databases = [db for db in all_databases if db.startswith("User_")]

    exp_data = {}
    for user_db in user_databases:
        user_id = int(user_db.split("_")[1])  # Extract user ID from database name
        db = client[user_db]
        exp_collection = db["EXP"]
        
        user_exp_data = exp_collection.find_one({})
        if user_exp_data and "points" in user_exp_data:
            exp_data[user_id] = user_exp_data["points"]

    return exp_data

# This function can be added to xp_handler.py or wherever you manage the database logic.
