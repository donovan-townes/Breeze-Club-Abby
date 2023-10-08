
from discord.ext import commands, tasks
from Twitch.twitch import get_user_twitch_handle, is_user_live
import os
from dotenv import load_dotenv
import requests
from utils.log_config import setup_logging, logging
import asyncio
from utils.mongo_db import connect_to_mongodb
import discord

setup_logging
logger = logging.getLogger(__name__)

os.chdir('/home/Abby/Discord/')
load_dotenv()


TEST_CHANNEL = 1103490012500201632
BREEZE_TV = 1131791657810022510

def fetch_users_with_twitch_handles():
    user_handles = {}
    client = connect_to_mongodb()
    
    try:
        # Loop through all databases in the client
        for db_name in client.list_database_names():
            if db_name.startswith("User_"):
                db = client[db_name]
                user_doc = db["Discord Profile"].find_one({"twitch_handle": {"$exists": True}})
                
                if user_doc:
                    # Extracting the Discord ID from the database name
                    discord_id = db_name.split("_")[1]
                    user_handles[discord_id] = user_doc["twitch_handle"]
    except Exception as e:
        # Log any exceptions that might occur
        logger.error(f"Error fetching users with Twitch handles: {e}")
    finally:
        # Ensure the client connection is closed regardless of whether an error occurred or not
        client.close()
                
    return user_handles

class Twitch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CHANNEL_ID = BREEZE_TV  # Breeze-TV Channel
        self.user_handles = fetch_users_with_twitch_handles()
        self.live_messages = {}
        self.is_live_prev = {}
        

    def get_oauth_token(self):
        client_id=os.getenv('TWITCH_CLIENT_ID')
        client_secret=os.getenv('TWITCH_CLIENT_SECRET')
        url = 'https://id.twitch.tv/oauth2/token'
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url, params=payload)
        return response.json()['access_token']

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"[🎥] Starting Twitch Live Scheduler")
        await self.check_live_twitch.start(self.bot)

    @commands.command(name='livedatabase', help='Lists all users with a valid Twitch handle in the database.')
    async def live_database(self, ctx):
        if not self.user_handles:
            await ctx.send("No users with valid Twitch handles found.")
            return

        message = "Users with valid Twitch handles:\n"
        for discord_id, twitch_handle in self.user_handles.items():
            user = self.bot.get_user(int(discord_id))
            if user:
                display_name = user.display_name
            else:
                display_name = "Unknown User"
            message += f"**{display_name}** | Twitch Handle: *{twitch_handle}*\n"

        await ctx.send(message)

    async def send_live_notification(self, bot, twitch_handle):
        channel = bot.get_channel(self.CHANNEL_ID)
        message = await channel.send(f"{twitch_handle} has just gone live! Let's tune in and support at https://twitch.tv/{twitch_handle}")
        self.live_messages[twitch_handle] = message

    async def delete_live_notification(self, twitch_handle):
        if twitch_handle in self.live_messages:
            try:
                await self.live_messages[twitch_handle].delete()
                del self.live_messages[twitch_handle]
            except discord.errors.NotFound:
                logger.warning(f"Message for {twitch_handle} not found. It might have been already deleted.")
                if twitch_handle in self.live_messages:
                    del self.live_messages[twitch_handle]

    @tasks.loop(minutes=15)
    async def check_live_twitch(self, bot):
        try:
            logger.info(" [🎥] Checking for USERS Live on Twitch!")
            for discord_id, twitch_handle in self.user_handles.items():
                is_live = is_user_live(twitch_handle, self.get_oauth_token())

                # Use the discord_id instead of the old user for the is_live_prev check
                if discord_id not in self.is_live_prev or is_live != self.is_live_prev[discord_id]:
                    self.is_live_prev[discord_id] = is_live
                    
                    if is_live:
                        await self.send_live_notification(bot, twitch_handle)
                    else:
                        await self.delete_live_notification(twitch_handle)

                if not is_live:
                    # logger.info(f"User {twitch_handle} is NOT LIVE")
                    pass

        except Exception as e:
            logger.error(f"Unexpected error during check_live_twitch loop: {e}")

async def setup(bot):
    await bot.add_cog(Twitch(bot))



    