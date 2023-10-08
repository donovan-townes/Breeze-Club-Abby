import discord
from discord.ext import commands, tasks
import asyncio
import datetime
from utils.log_config import logging,setup_logging

setup_logging()
logger = logging.getLogger(__name__)
CHANNEL = 802512963519905852
ABBY_IDLE = "<a:Abby_idle:1135376647495884820>"
class NudgeHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_message_timestamps = {}
        self.last_nudge_timestamps = {}

    async def cog_unload(self) -> None:
        self.nudge_users.cancel()
        logger.info("[👈] Nudge Handler Unloaded")

    async def cog_load(self) -> None:
        logger.info("[👈] Nudge Handler Loaded - DISABLED UNTIL FURTHER NOTICE!")
        # self.nudge_users.start()

    @tasks.loop(hours=1)
    async def nudge_users(self):
            logger.info("[👈] Hourly Check! - Checking to Nudge Users (within last 24 hours)..." )
            for user_id, timestamp in self.last_message_timestamps.items():
                if (datetime.datetime.utcnow() - timestamp).total_seconds() > 24*60*60:
                    last_nudge_timestamp = self.last_nudge_timestamps.get(user_id)
                    if last_nudge_timestamp and (datetime.datetime.utcnow() - last_nudge_timestamp).total_seconds() < 24*60*60:
                        continue

                    member = discord.utils.find(
                        lambda m: m.id == user_id, self.bot.get_all_members())
                    if member:
                        channel = self.bot.get_channel(CHANNEL)
                        await channel.send(f"It's been a while since we've heard from you <@{user_id}>! How are you doing? {ABBY_IDLE}")
                        self.last_nudge_timestamps[user_id] = datetime.datetime.utcnow()
                        self.last_message_timestamps[user_id] = datetime.datetime.utcnow()  # Add this line
                        # Add a log message for checking to nudge users
                        logger.info(f"[👈] Checking to nudge user {user_id}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        self.last_message_timestamps[message.author.id] = datetime.datetime.utcnow()
        # logger.info(f"[👈] Updated last message timestamp for user {message.author.id}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.last_message_timestamps[member.id] = datetime.datetime.utcnow()
        logger.info(f"[👈] [New Member] Updated last message timestamp for user {member.id}")

async def setup(bot):
    await bot.add_cog(NudgeHandler(bot))
    