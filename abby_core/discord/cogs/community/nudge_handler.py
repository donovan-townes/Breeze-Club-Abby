"""
User engagement nudge system.

Periodically reminds inactive users that the server misses them.
Tracks message activity and sends friendly nudge messages after
a configurable period of inactivity.

Features:
- Automatic nudge notifications
- Inactivity tracking
- Configurable interval
"""

import discord
from discord.ext import commands
import datetime
from tdos_intelligence.observability import logging
from abby_core.discord.config import BotConfig

logger = logging.getLogger(__name__)
config = BotConfig()


class NudgeHandler(commands.Cog):
    """Handle user engagement nudges for inactive members."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_message_timestamps = {}
        self.last_nudge_timestamps = {}
        
        # Load config
        self.enabled = config.features.nudge_enabled
        self.interval_hours = config.timing.nudge_interval_hours
        self.nudge_channel_id = config.channels.nudge_channel
        
        # ISSUE-005: Validate nudge channel is configured if feature is enabled
        if self.enabled and (not self.nudge_channel_id or self.nudge_channel_id <= 0):
            raise ValueError(
                "NUDGE_ENABLED=true but NUDGE_CHANNEL_ID is not configured. "
                "Either set NUDGE_CHANNEL_ID to a valid Discord channel ID, "
                "or disable the nudge feature by setting NUDGE_ENABLED=false."
            )
        
        # Rate-limiting for configuration warnings (once per tick, not per user)
        self._config_warning_logged_this_tick = False
        
        logger.debug(f"[👈] Nudge handler initialized (enabled={self.enabled}, interval={self.interval_hours}h, channel={self.nudge_channel_id})")

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""

        logger.info("[👈] Nudge Handler Unloaded")

    async def cog_load(self) -> None:
        """Initialize nudge task when cog loads."""
        logger.debug(f"[👈] Nudge Handler loaded (enabled={self.enabled}, interval={self.interval_hours}h)")

    async def nudge_users_tick(self):
        """Platform scheduler entrypoint for nudges."""
        logger.debug("[👈] Nudge check running...")
        # ISSUE-005: Reset rate-limit flag at start of each tick
        self._config_warning_logged_this_tick = False
        
        for user_id, timestamp in self.last_message_timestamps.items():
            if (datetime.datetime.utcnow() - timestamp).total_seconds() > self.interval_hours * 60 * 60:
                last_nudge_timestamp = self.last_nudge_timestamps.get(user_id)
                if last_nudge_timestamp and (datetime.datetime.utcnow() - last_nudge_timestamp).total_seconds() < self.interval_hours * 60 * 60:
                    continue

                member = discord.utils.find(
                    lambda m: m.id == user_id, self.bot.get_all_members())
                if member:
                    if not self.nudge_channel_id:
                        # ISSUE-005: Log warning only once per tick, not per user
                        if not self._config_warning_logged_this_tick:
                            logger.warning("[👈] NUDGE_CHANNEL_ID not configured")
                            self._config_warning_logged_this_tick = True
                        continue
                    try:
                        channel = self.bot.get_channel(self.nudge_channel_id)
                        if channel and isinstance(channel, discord.TextChannel):
                            await channel.send(f"Hey <@{user_id}> — we miss you! How are things? {config.emojis.abby_idle}")
                            self.last_nudge_timestamps[user_id] = datetime.datetime.utcnow()
                            self.last_message_timestamps[user_id] = datetime.datetime.utcnow()
                            logger.info(f"[👈] Nudged user {user_id}")
                        elif not channel:
                            logger.warning(f"[👈] Nudge channel {self.nudge_channel_id} not found")
                        else:
                            logger.warning(f"[👈] Nudge channel is not a text channel: {type(channel).__name__}")
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
