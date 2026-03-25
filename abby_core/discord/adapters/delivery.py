"""Discord Adapter: Announcement Delivery

Implements announcement delivery to Discord channels.

Architecture:
    Platform-Agnostic AnnouncementService (generates/queues announcements)
                      ↓
    IAnnouncementDelivery interface (abstract contract)
                      ↓
    DiscordAnnouncementDelivery (this module) - sends to channels
                      ↓
    Discord Channels (actual message delivery)

This adapter is responsible for:
- Finding the target channel in a guild
- Formatting messages as Discord embeds (when needed for length)
- Handling delivery errors
- Logging successful/failed deliveries

The core service (AnnouncementService) remains platform-agnostic.
"""

from typing import Optional, Tuple
import discord
from datetime import datetime

from abby_core.database.collections.guild_configuration import get_guild_config
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


async def send_announcement_to_guild(
    bot: discord.Client,
    guild_id: int,
    announcement_message: str,
    channel_type: str = "announcements"
) -> Tuple[bool, Optional[int], Optional[int], Optional[str]]:
    """Send announcement to a guild's configured channel.
    
    Tries the configured channel first (e.g., announcements), then falls back
    to mod channel. Uses embeds for messages longer than 1800 characters to
    exceed Discord's 2000 character plain text limit.
    
    Args:
        bot: Discord bot instance
        guild_id: Target guild ID
        announcement_message: Message to send (plain text or generated)
        channel_type: Channel type to try first ("announcements" or "mod")
    
    Returns:
        Tuple of (success, channel_id, message_id, error_msg):
            - success (bool): Whether message was sent
            - channel_id (int|None): ID of channel message was sent to
            - message_id (int|None): ID of sent message
            - error_msg (str|None): Error message if failed
    
    Example:
        success, ch_id, msg_id, error = await send_announcement_to_guild(
            bot, 
            guild_id=123456789,
            announcement_message="Season 3 has begun!"
        )
        if not success:
            logger.error(f"Delivery failed: {error}")
    """
    try:
        # Fetch guild
        guild = bot.get_guild(guild_id)
        if not guild:
            return False, None, None, f"Guild {guild_id} not found"
        
        # Get guild configuration
        guild_config = get_guild_config(guild_id)
        
        # Try configured channel first
        channels = guild_config.get("channels", {})
        target_channel_id = None
        
        if channel_type == "announcements":
            target_channel_id = channels.get("announcements", {}).get("id")
        elif channel_type == "mod":
            target_channel_id = channels.get("mod", {}).get("id")
        
        # Fall back to alternate channel if first not found
        if not target_channel_id:
            if channel_type == "announcements":
                target_channel_id = channels.get("mod", {}).get("id")
            else:
                target_channel_id = channels.get("announcements", {}).get("id")
        
        if not target_channel_id:
            logger.warning(f"[📢] No announcement or mod channel configured for guild {guild_id}")
            return False, None, None, "No announcement channel configured"
        
        # Fetch channel
        channel = bot.get_channel(target_channel_id)
        if not channel:
            try:
                channel = await bot.fetch_channel(target_channel_id)
            except discord.HTTPException as e:
                return False, None, None, f"Channel fetch failed: {e}"
        
        if not channel:
            return False, None, None, f"Channel {target_channel_id} not found"
        
        # Check channel type
        if not isinstance(channel, discord.TextChannel):
            return False, None, None, f"Channel {target_channel_id} is not a text channel"
        
        # Send message - use embed for longer messages
        try:
            if len(announcement_message) < 1800:
                # Plain text for short messages
                message = await channel.send(announcement_message)
            else:
                # Use embed for longer messages (embeds support up to 4096 chars in description)
                embed = discord.Embed(
                    description=announcement_message[:4000],
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text="🌍 System Announcement")
                message = await channel.send(embed=embed)
            
            logger.info(
                f"[📢] Announcement sent to guild {guild_id}, channel {target_channel_id}, msg_id {message.id}"
            )
            return True, target_channel_id, message.id, None
            
        except discord.Forbidden:
            return False, target_channel_id, None, f"Bot lacks permission to send messages in {target_channel_id}"
        except discord.HTTPException as e:
            return False, target_channel_id, None, f"Failed to send message: {e}"
    
    except Exception as e:
        logger.error(
            f"[📢] Announcement delivery failed for guild {guild_id}: {e}",
            exc_info=True
        )
        return False, None, None, str(e)


async def send_notification_to_channel(
    channel: discord.TextChannel,
    title: str,
    description: str,
    color: discord.Color = discord.Color.blue()
) -> Tuple[bool, Optional[str]]:
    """Send a notification to a Discord channel as an embed.
    
    Args:
        channel: Target Discord text channel
        title: Embed title
        description: Embed description
        color: Embed color (default: blue)
    
    Returns:
        Tuple of (success, error_msg)
    
    Example:
        success, error = await send_notification_to_channel(
            channel,
            title="System Notice",
            description="Maintenance in 1 hour"
        )
    """
    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        await channel.send(embed=embed)
        return True, None
    except discord.Forbidden:
        return False, f"Bot lacks permission to send messages in {channel.id}"
    except discord.HTTPException as e:
        return False, f"Failed to send notification: {e}"
    except Exception as e:
        logger.error(f"[📢] Notification delivery failed: {e}", exc_info=True)
        return False, str(e)
