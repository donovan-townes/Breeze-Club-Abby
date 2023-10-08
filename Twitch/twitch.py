import os
from dotenv import load_dotenv
import requests
from utils.log_config import setup_logging, logging
from utils.mongo_db import connect_to_mongodb
from datetime import datetime
import re
setup_logging
logger = logging.getLogger(__name__)

# Change the current working directory to the Discord directory
os.chdir('/home/Abby/Discord/')
# Load the .env file
load_dotenv()

CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')


def get_oauth_token(client_id, client_secret):
    url = 'https://id.twitch.tv/oauth2/token'
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=payload)
    return response.json()['access_token']


def is_user_live(user_login, oauth_token):
    url = 'https://api.twitch.tv/helix/streams'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {oauth_token}'
    }
    params = {'user_login': user_login}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()['data']
    return len(data) > 0 and data[0]['type'] == 'live'


async def handle_live_command(message, args):
    if not args:
        await message.channel.send("Please provide a Twitch username or a Discord user mention.")
        return

    user_input = args[0]

    # Check if the user input is a Discord mention
    if user_input.startswith('<@') and user_input.endswith('>'):
        # Extract the Discord ID from the mention
        user_id = re.search(r'\d+', user_input).group()  # Match the first number in the mention string
        user_login = get_user_twitch_handle(user_id)
        if not user_login:
            await message.channel.send("No associated Twitch handle found.")
            return
    else:
        # If it's not a mention, use the input directly as the Twitch username
        user_login = user_input

    oauth_token = get_oauth_token(CLIENT_ID, CLIENT_SECRET)
    twitch_url = 'https://twitch.tv/'
    if is_user_live(user_login, oauth_token):
        await message.channel.send(f'{user_login} is live! Tune in now at {twitch_url}{user_login}')
    else:
        await message.channel.send(f'{user_login} is not live.')

async def handle_add_twitch_command(message, args):
    if len(args) < 2:
        await message.channel.send("Please provide a Discord user and a Twitch username.")
        return

    # Assume the user is mentioned as the first argument and Twitch handle is the second
    discord_mention = args[0]
    twitch_handle = args[1]

    # Extract the Discord ID from the mention
    user_id = re.search(r'\d+', discord_mention).group()  # Match the first number in the mention string

    add_twitch_handle(user_id, twitch_handle)

    await message.channel.send(f"Successfully added Twitch handle {twitch_handle} for {discord_mention}!")

def add_twitch_handle(user_id, twitch_handle):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]

        # Specify the collection
        users_collection = db["Discord Profile"]

        # Define the user's Twitch handle document
        user_twitch_handle = {
            'discord_id': user_id,
            'twitch_handle': twitch_handle,
            'last_updated': datetime.utcnow()
        }

        # Add the user's Twitch handle to the database
        users_collection.update_one({'discord_id': user_id}, {
                                    '$set': user_twitch_handle}, upsert=True)
        logger.info(f"[✅] Successfully added Twitch handle for user {user_id}!")
    except Exception as e:
        logger.warning("[❌] add_twitch_handle error")
        logger.warning(str(e))

def get_user_twitch_handle(user_id):
    try:
        # Specify the database
        client = connect_to_mongodb()
        db = client[f"User_{user_id}"]

        # Specify the collection
        users_collection = db["Discord Profile"]

        # Query the user's Twitch handle from the database
        user_document = users_collection.find_one({'discord_id': str(user_id)})

        # Return the Twitch handle if found, None otherwise
        return user_document['twitch_handle'] if user_document and 'twitch_handle' in user_document else None

    except Exception as e:
        logger.warning("get_user_twitch_handle error")
        logger.warning(str(e))
        return None

