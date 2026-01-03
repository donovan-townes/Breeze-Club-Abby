"""
Mod Notification System for Guild Assistants

Provides utilities for sending styled notifications to guild mod channels.
Integrates with Discord.py and logging system for error/critical event forwarding.

Usage:
    from abby_adapters.discord.core.mod_notifications import send_mod_notification
    
    await send_mod_notification(
        bot=bot,
        guild_id=123456789,
        level="INFO",
        title="Memory Maintenance",
        description="Weekly maintenance complete",
        fields={"Facts Decayed": "156", "Facts Pruned": "23"}
    )
"""

import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional, Dict, Any
import logging

try:
    from abby_core.database.memory_settings import get_guild_setting
except ImportError:
    def get_guild_setting(guild_id, key, default=None):
        return default


async def send_mod_notification(
    bot: commands.Bot,
    guild_id: int,
    level: str,
    title: str,
    description: str,
    fields: Optional[Dict[str, str]] = None,
    color: Optional[discord.Color] = None,
    tag_mods: bool = False
) -> bool:
    """
    Send a styled notification to guild's mod channel.
    
    Args:
        bot: Discord bot instance
        guild_id: Target guild ID
        level: Notification level ("INFO", "WARNING", "ERROR", "CRITICAL")
        title: Embed title
        description: Embed description
        fields: Optional dict of field names and values
        color: Optional embed color (defaults based on level)
        tag_mods: Whether to mention mods (for critical alerts)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Get mod channel ID from guild settings
        mod_channel_id = get_guild_setting(guild_id, "mod_channel_id")
        
        if not mod_channel_id:
            return False
        
        # Get channel
        channel = bot.get_channel(int(mod_channel_id))
        if not channel:
            return False
        
        # Determine color based on level
        if color is None:
            level_colors = {
                "INFO": discord.Color.blue(),
                "WARNING": discord.Color.gold(),
                "ERROR": discord.Color.red(),
                "CRITICAL": discord.Color.red(),
            }
            color = level_colors.get(level, discord.Color.blue())
        
        # Create embed
        embed = discord.Embed(
            title=f"[{level}] {title}",
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Add fields if provided
        if fields:
            for field_name, field_value in fields.items():
                embed.add_field(
                    name=field_name,
                    value=str(field_value),
                    inline=True
                )
        
        # Add footer
        embed.set_footer(text="Guild Assistant 🤖")
        
        # Build message content
        content = ""
        if tag_mods and level == "CRITICAL":
            # Only tag for critical alerts
            # Get mod role if available (would need guild config)
            pass
        
        # Send message
        await channel.send(content=content or None, embed=embed)
        return True
    
    except Exception as e:
        logging.error(f"[mod_notifications] Failed to send notification: {e}")
        return False


class ModNotificationHandler(logging.Handler):
    """
    Custom logging handler that forwards ERROR/CRITICAL logs to mod channel.
    
    Integrate with logging system:
        logger = logging.getLogger("abby_core")
        handler = ModNotificationHandler(bot)
        logger.addHandler(handler)
    """
    
    def __init__(self, bot: commands.Bot, min_level: int = logging.ERROR):
        """
        Initialize handler.
        
        Args:
            bot: Discord bot instance
            min_level: Minimum log level to forward (default ERROR)
        """
        super().__init__(min_level)
        self.bot = bot
        self.queue = []
    
    def emit(self, record: logging.LogRecord):
        """
        Handle a log record.
        
        Args:
            record: LogRecord to process
        """
        try:
            # Extract guild_id from log record if available
            guild_id = record.__dict__.get("guild_id")
            
            if not guild_id:
                return
            
            # Format message
            msg = self.format(record)
            level_name = record.levelname
            
            # Queue for async sending
            self.queue.append({
                "guild_id": guild_id,
                "level": level_name,
                "title": record.name,
                "description": msg
            })
        except Exception:
            self.handleError(record)


async def process_notification_queue(bot: commands.Bot, handler: ModNotificationHandler):
    """
    Process queued notifications asynchronously.
    
    Intended to run as a background task:
        @tasks.loop(seconds=10)
        async def process_mod_notifications():
            await process_notification_queue(bot, notification_handler)
    """
    while handler.queue:
        notification = handler.queue.pop(0)
        
        try:
            await send_mod_notification(
                bot=bot,
                guild_id=notification["guild_id"],
                level=notification["level"],
                title=notification["title"],
                description=notification["description"]
            )
        except Exception as e:
            logging.error(f"[mod_notifications] Failed to process queued notification: {e}")
