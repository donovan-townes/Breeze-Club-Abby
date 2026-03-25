"""
Discord Adapters for Platform-Agnostic Services

This package contains all Discord-specific implementations of core interfaces.

Modules:
    - tools.py: Tool implementations (server info, user XP, bot status)
    - output.py: Output formatting (OutputMessage → discord.Embed)
    - delivery.py: Announcement delivery to Discord channels
    - economy.py: Economy cog and background tasks (BankCog)
    - scheduler_bridge.py: Job handlers for SchedulerService

Architecture:
    Platform-Agnostic Core Services (abby_core/)
               ↓
    Discord Adapters (this package) - implements interfaces
               ↓
    Discord Cogs (abby_core/discord/cogs/) - user-facing commands

This separation ensures:
- Core services remain reusable across adapters (Web, CLI, Slack, etc.)
- Discord I/O is isolated to this package
- Adding new platforms requires only new adapters, not core refactoring
"""

import discord
from discord.ext import commands
from typing import Dict, Any, Optional, List
from datetime import datetime

from abby_core.services.scheduler import SchedulerService, JobHandler, get_scheduler_service
from abby_core.interfaces.tools import (
    IServerInfoTool, IUserInfoTool, IUserXPTool, IBotStatusTool,
    ServerInfo, UserInfo, UserXPInfo, BotStatus, ToolResult
)
from abby_core.interfaces.output import (
    IOutputFormatter, IAnnouncementDelivery, OutputMessage, OutputColor,
    ImageOutput, FieldOutput
)
from abby_core.database.collections.guild_configuration import get_guild_config
from abby_core.economy.xp import get_xp, get_level_from_xp, get_xp_required
from abby_core.observability.logging import logging

# Import Discord adapters
from abby_core.discord.adapters.scheduler_bridge import (
    register_scheduler_jobs,
    HeartbeatJobHandler,
    XPStreamingJobHandler,
    GiveawayCheckJobHandler,
    NudgeJobHandler,
)
from abby_core.discord.adapters.economy import BankCog

logger = logging.getLogger(__name__)


# ============================================================================
# DISCORD TOOL IMPLEMENTATIONS
# ============================================================================

class DiscordServerInfoTool(IServerInfoTool):
    """Discord implementation of server info tool."""
    
    async def get_server_info(self, server_id: str, context: Dict[str, Any]) -> ToolResult:
        """Get Discord guild information."""
        try:
            bot = context.get("bot")
            if not bot:
                return ToolResult(success=False, error="Bot client not available")
            
            guild = bot.get_guild(int(server_id))
            if not guild:
                return ToolResult(success=False, error=f"Guild {server_id} not found")
            
            # Build ServerInfo
            owner_name = "Unknown"
            if guild.owner:
                owner_name = guild.owner.display_name
            elif guild.owner_id:
                try:
                    owner = await guild.fetch_member(guild.owner_id)
                    owner_name = owner.display_name
                except:
                    owner_name = f"<@{guild.owner_id}>"
            
            server_info = ServerInfo(
                server_id=str(guild.id),
                name=guild.name,
                member_count=guild.member_count or 0,
                owner_id=str(guild.owner_id) if guild.owner_id else "Unknown",
                owner_name=owner_name,
                created_at=guild.created_at,
                icon_url=str(guild.icon.url) if guild.icon else None,
                description=guild.description,
            )
            
            return ToolResult(success=True, data=server_info.to_dict())
        
        except Exception as e:
            logger.error(f"[Discord Tool] Server info failed: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))


class DiscordUserXPTool(IUserXPTool):
    """Discord implementation of user XP tool."""
    
    async def get_user_xp(self, user_id: str, server_id: Optional[str], context: Dict[str, Any]) -> ToolResult:
        """Get Discord user's XP/level information."""
        try:
            # Get XP data from database
            user_data = get_xp(int(user_id))
            if not user_data:
                return ToolResult(success=False, error=f"No XP data for user {user_id}")
            
            xp = user_data.get("points", 0)
            level = get_level_from_xp(xp)
            xp_required = get_xp_required(level + 1)["xp_required"]
            
            try:
                prev_xp_required = get_xp_required(level)["xp_required"]
            except:
                prev_xp_required = 0
            
            current_level_xp = xp - prev_xp_required
            xp_for_level = xp_required - prev_xp_required
            
            # Get user info from bot
            bot = context.get("bot")
            username = f"User {user_id}"
            display_name = username
            
            if bot:
                try:
                    user = await bot.fetch_user(int(user_id))
                    username = user.name
                    display_name = user.display_name if hasattr(user, "display_name") else user.name
                except:
                    pass
            
            xp_info = UserXPInfo(
                user_id=str(user_id),
                username=username,
                display_name=display_name,
                xp=xp,
                level=level,
                xp_to_next_level=xp_required - xp,
                current_level_xp=current_level_xp,
                xp_for_level=xp_for_level,
            )
            
            return ToolResult(success=True, data=xp_info.to_dict())
        
        except Exception as e:
            logger.error(f"[Discord Tool] User XP failed: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))


class DiscordBotStatusTool(IBotStatusTool):
    """Discord implementation of bot status tool."""
    
    async def set_status(self, status: BotStatus, context: Dict[str, Any]) -> ToolResult:
        """Set Discord bot presence."""
        try:
            bot = context.get("bot")
            if not bot:
                return ToolResult(success=False, error="Bot client not available")
            
            # Map status type to Discord activity
            status_type = status.status_type.lower()
            
            if status_type == "playing":
                activity = discord.Game(name=status.message)
            elif status_type == "watching":
                activity = discord.Activity(type=discord.ActivityType.watching, name=status.message)
            elif status_type == "listening":
                activity = discord.Activity(type=discord.ActivityType.listening, name=status.message)
            elif status_type == "streaming":
                activity = discord.Streaming(name=status.message, url=status.url or "https://twitch.tv")
            else:
                activity = discord.Game(name=status.message)
            
            # Change presence
            await bot.change_presence(activity=activity)
            
            return ToolResult(
                success=True,
                message=f"Status updated to: {status_type} {status.message}"
            )
        
        except Exception as e:
            logger.error(f"[Discord Tool] Set status failed: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))
    
    async def get_status(self, context: Dict[str, Any]) -> ToolResult:
        """Get current Discord bot status."""
        try:
            bot = context.get("bot")
            if not bot:
                return ToolResult(success=False, error="Bot client not available")
            
            # Get current activity
            if bot.guilds and len(bot.guilds) > 0:
                # Get bot's member in first guild
                guild = bot.guilds[0]
                member = guild.get_member(bot.user.id)
                
                if member and member.activity:
                    activity = member.activity
                    status_type = "playing"
                    
                    if isinstance(activity, discord.Streaming):
                        status_type = "streaming"
                    elif isinstance(activity, discord.Activity):
                        if activity.type == discord.ActivityType.watching:
                            status_type = "watching"
                        elif activity.type == discord.ActivityType.listening:
                            status_type = "listening"
                    
                    bot_status = BotStatus(
                        status_type=status_type,
                        message=str(activity.name) if activity.name else "",
                        url=activity.url if hasattr(activity, "url") else None
                    )
                    
                    return ToolResult(success=True, data=bot_status.to_dict())
            
            return ToolResult(success=True, data=BotStatus(status_type="online", message="").to_dict())
        
        except Exception as e:
            logger.error(f"[Discord Tool] Get status failed: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))


# ============================================================================
# DISCORD OUTPUT FORMATTER
# ============================================================================

class DiscordOutputFormatter(IOutputFormatter):
    """Convert OutputMessage to Discord embeds."""
    
    # Color mapping
    COLOR_MAP = {
        "default": discord.Color.default(),
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.orange(),
        "info": discord.Color.blue(),
        "primary": discord.Color.blurple(),
        "secondary": discord.Color.greyple(),
    }
    
    def format_message(self, output: OutputMessage) -> discord.Embed:
        """Convert OutputMessage to Discord Embed."""
        # Get color
        color = self.COLOR_MAP.get(output.color.value, discord.Color.default())
        
        # Create base embed
        embed = discord.Embed(
            title=output.title,
            description=output.description,
            url=output.url,
            color=color,
            timestamp=output.timestamp
        )
        
        # Add author
        if output.author:
            embed.set_author(
                name=output.author.name,
                url=output.author.url,
                icon_url=output.author.icon_url
            )
        
        # Add fields
        for field in output.fields:
            embed.add_field(
                name=field.name,
                value=field.value,
                inline=field.inline
            )
        
        # Add footer
        if output.footer:
            embed.set_footer(
                text=output.footer.text,
                icon_url=output.footer.icon_url
            )
        
        # Add image
        if output.image and output.image.url:
            embed.set_image(url=output.image.url)
        
        # Add thumbnail
        if output.thumbnail and output.thumbnail.url:
            embed.set_thumbnail(url=output.thumbnail.url)
        
        return embed
    
    def format_text(self, output: OutputMessage) -> str:
        """Format as plain text (fallback)."""
        parts = []
        
        if output.title:
            parts.append(f"**{output.title}**")
        
        if output.description:
            parts.append(output.description)
        
        for field in output.fields:
            parts.append(f"**{field.name}:** {field.value}")
        
        if output.footer:
            parts.append(f"\n_{output.footer.text}_")
        
        return "\n".join(parts)


# ============================================================================
# DISCORD ANNOUNCEMENT DELIVERY
# ============================================================================

class DiscordAnnouncementDelivery(IAnnouncementDelivery):
    """Deliver announcements to Discord channels."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize with Discord bot instance."""
        self.bot = bot
    
    async def send_announcement(
        self,
        channel_id: str,
        output: OutputMessage,
        context: Dict[str, Any]
    ) -> bool:
        """Send announcement to Discord channel."""
        try:
            # Get channel
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                except:
                    logger.error(f"[Discord Delivery] Channel {channel_id} not found")
                    return False
            
            # Type narrowing: ensure it's a messageable channel
            if not hasattr(channel, "send"):
                logger.error(f"[Discord Delivery] Channel {channel_id} is not messageable")
                return False
            
            # Format message
            formatter = DiscordOutputFormatter()
            
            # Send as embed if we have rich content, otherwise plain text
            if output.title or output.fields or output.image:
                embed = formatter.format_message(output)
                await channel.send(content=output.content, embed=embed)  # type: ignore
            else:
                text = output.content or formatter.format_text(output)
                await channel.send(text)  # type: ignore
            
            logger.info(f"[Discord Delivery] Sent announcement to channel {channel_id}")
            return True
        
        except Exception as e:
            logger.error(f"[Discord Delivery] Failed to send to {channel_id}: {e}", exc_info=True)
            return False
    
    async def send_bulk_announcements(
        self,
        announcements: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Send multiple announcements."""
        results = {}
        
        for ann in announcements:
            channel_id = ann.get("channel_id")
            output = ann.get("output")
            
            if not channel_id or not output:
                continue
            
            success = await self.send_announcement(channel_id, output, context)
            results[channel_id] = success
        
        return results


# ============================================================================
# DISCORD JOB HANDLERS
# ============================================================================

class DiscordJobHandler(JobHandler):
    """Base class for Discord-specific job handlers."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize with bot instance."""
        self.bot = bot


# ============================================================================
# REGISTRATION HELPER
# ============================================================================

def register_discord_adapters(bot: commands.Bot):
    """Register all Discord adapters with factories and bot.
    
    Call this during bot startup to enable platform-agnostic services
    to work with Discord and to load Discord-specific cogs.
    
    This function:
    1. Registers tool implementations with ToolFactory
    2. Registers output formatters with FormatterFactory
    3. Registers scheduler job handlers with SchedulerService
    4. Initializes heartbeat service for this instance
    
    Args:
        bot: Discord bot instance
    """
    from abby_core.interfaces.tools import get_tool_factory
    from abby_core.interfaces.output import get_formatter_factory
    from abby_core.services.heartbeat_service import get_heartbeat_service
    
    # Register tool implementations with factory
    tool_factory = get_tool_factory()
    tool_factory.register("discord", "server_info", DiscordServerInfoTool())
    tool_factory.register("discord", "user_xp", DiscordUserXPTool())
    tool_factory.register("discord", "bot_status", DiscordBotStatusTool())
    # Register intent-facing tool aliases
    from abby_core.discord.adapters.intent_tools import (
        DiscordIntentGetGuildInfoTool,
        DiscordIntentGetUserExpTool,
        DiscordIntentSetBotStatusTool,
    )
    tool_factory.register("discord", "get_guild_info", DiscordIntentGetGuildInfoTool())
    tool_factory.register("discord", "get_user_exp", DiscordIntentGetUserExpTool())
    tool_factory.register("discord", "set_bot_status", DiscordIntentSetBotStatusTool())
    
    # Register output formatters with factory
    formatter_factory = get_formatter_factory()
    formatter_factory.register_formatter("discord", DiscordOutputFormatter())
    formatter_factory.register_delivery_handler("discord", DiscordAnnouncementDelivery(bot))
    
    # Initialize heartbeat service (creates singleton if needed)
    heartbeat_service = get_heartbeat_service()
    
    # Register scheduler job handlers
    register_scheduler_jobs(bot)
    
    logger.info("[🔌] Discord adapters initialized (tools, formatters, scheduler)")
