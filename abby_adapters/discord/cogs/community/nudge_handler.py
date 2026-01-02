"""
User engagement nudge system.

Periodically reminds inactive users that the server misses them.
Tracks message activity and sends friendly nudge messages after
a configurable period of inactivity.

Features:
- Automatic nudge notifications
- Inactivity tracking
- Configurable interval
- Enable/disable via environment variable
"""

import discord
from discord.ext import commands, tasks
import datetime
from abby_core.observability.logging import logging, setup_logging
from abby_adapters.discord.config import BotConfig

setup_logging()
logger = logging.getLogger(__name__)

ABBY_IDLE = "<a:Abby_idle:1135376647495884820>"


class NudgeHandler(commands.Cog):
    """Handle user engagement nudges for inactive members."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_message_timestamps = {}
        self.last_nudge_timestamps = {}
        
        # Load config
        try:
            self.config = BotConfig()
            # Note: These would need to be added to BotConfig if they don't exist
            # For now, we'll use getenv as fallback with centralized config pattern
            self.enabled = self.config.features.nudge_enabled if hasattr(self.config, 'features') else False
            self.interval_hours = 24  # Default interval
            self.nudge_channel_id = None  # Will be loaded from config
        except Exception as e:
            logger.error(f"Error loading nudge config: {e}")
            self.enabled = False
            self.interval_hours = 24
            self.nudge_channel_id = None

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        self.nudge_users.cancel()
        logger.info("[👈] Nudge Handler Unloaded")

    async def cog_load(self) -> None:
        """Initialize nudge task when cog loads."""
        logger.info(f"[👈] Nudge Handler Loaded (enabled={self.enabled}, interval={self.interval_hours}h)")
        if self.enabled:
            self.nudge_users.change_interval(hours=self.interval_hours)
            self.nudge_users.start()

    @tasks.loop(hours=1)
    async def nudge_users(self):
        """Periodically check for and nudge inactive users."""
        logger.info("[👈] Nudge check running...")
        for user_id, timestamp in self.last_message_timestamps.items():
            if (datetime.datetime.utcnow() - timestamp).total_seconds() > self.interval_hours * 60 * 60:
                last_nudge_timestamp = self.last_nudge_timestamps.get(user_id)
                if last_nudge_timestamp and (datetime.datetime.utcnow() - last_nudge_timestamp).total_seconds() < self.interval_hours * 60 * 60:
                    continue

                member = discord.utils.find(
                    lambda m: m.id == user_id, self.bot.get_all_members())
                if member:
                    if not self.nudge_channel_id:
                        logger.warning("[👈] NUDGE_CHANNEL_ID not configured")
                        continue
                    try:
                        channel = self.bot.get_channel(self.nudge_channel_id)
                        if channel:
                            await channel.send(f"Hey <@{user_id}> — we miss you! How are things? {ABBY_IDLE}")
                            self.last_nudge_timestamps[user_id] = datetime.datetime.utcnow()
                            self.last_message_timestamps[user_id] = datetime.datetime.utcnow()
                            logger.info(f"[👈] Nudged user {user_id}")
                    except Exception as e:
                        logger.error(f"Error nudging user {user_id}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track message activity for active users."""
        if message.author.bot:
            return
        self.last_message_timestamps[message.author.id] = datetime.datetime.utcnow()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Reset inactivity timer for new members."""
        self.last_message_timestamps[member.id] = datetime.datetime.utcnow()
        logger.info(f"[👈] [New Member] Initialized nudge tracking for {member.id}")


async def setup(bot: commands.Bot) -> None:
    """Load the NudgeHandler cog."""
    await bot.add_cog(NudgeHandler(bot))
    logger.info("[✅] NudgeHandler cog loaded")
