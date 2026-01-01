import discord
from discord.ext import commands, tasks
import asyncio
import datetime
from abby_core.observability.logging import logging,setup_logging
import os
from dotenv import load_dotenv

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)
CHANNEL = int(os.getenv("NUDGE_CHANNEL_ID", "0")) or None
ABBY_IDLE = "<a:Abby_idle:1135376647495884820>"
class NudgeHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_message_timestamps = {}
        self.last_nudge_timestamps = {}
        self.enabled = os.getenv("NUDGE_ENABLED", "false").lower() == "true"
        self.interval_hours = int(os.getenv("NUDGE_INTERVAL_HOURS", "24"))

    async def cog_unload(self) -> None:
        self.nudge_users.cancel()
        logger.info("[👈] Nudge Handler Unloaded")

    async def cog_load(self) -> None:
        logger.info(f"[👈] Nudge Handler Loaded (enabled={self.enabled}, interval={self.interval_hours}h)")
        if self.enabled:
            self.nudge_users.change_interval(hours=self.interval_hours)
            self.nudge_users.start()

    @tasks.loop(hours=1)
    async def nudge_users(self):
            logger.info("[👈] Nudge check running...")
            for user_id, timestamp in self.last_message_timestamps.items():
                if (datetime.datetime.utcnow() - timestamp).total_seconds() > self.interval_hours*60*60:
                    last_nudge_timestamp = self.last_nudge_timestamps.get(user_id)
                    if last_nudge_timestamp and (datetime.datetime.utcnow() - last_nudge_timestamp).total_seconds() < self.interval_hours*60*60:
                        continue

                    member = discord.utils.find(
                        lambda m: m.id == user_id, self.bot.get_all_members())
                    if member:
                        if not CHANNEL:
                            logger.warning("[👈] NUDGE_CHANNEL_ID not configured")
                            continue
                        channel = self.bot.get_channel(CHANNEL)
                        await channel.send(f"Hey <@{user_id}> — we miss you! How are things? {ABBY_IDLE}")
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
    