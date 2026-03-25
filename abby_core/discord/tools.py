"""DEPRECATED: Discord-specific tools module.

⚠️ This module is deprecated. Use abby_core.discord.adapters instead.

Migration Guide:
    Tool implementations have moved to: abby_core.discord.adapters
    Tool registration moved to: abby_core.discord.adapters.__init__.py
    Factory patterns moved to: abby_core.interfaces.tools

Example:
    from abby_core.discord.adapters import DiscordServerInfoTool  # ✅ NEW
    # NOT: from abby_core.discord.tools import ...              # ❌ OLD

Deprecation Timeline:
    - Phase 1 (v1.0): Added deprecation notice ← you are here
    - Phase 2 (v1.1): Imports will raise warnings
    - Phase 3 (v1.2): Module will be removed

This module is maintained for backward compatibility only.
"""

import warnings

# Issue deprecation warning on import
warnings.warn(
    "abby_core.discord.tools is deprecated and will be removed in v1.2. "
    "Use abby_core.discord.adapters instead.",
    DeprecationWarning,
    stacklevel=2
)

from typing import Optional, Dict, Any
import discord
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class GuildInfoTool:
    """Guild information tool - reuses ServerInfo cog logic."""
    
    @staticmethod
    async def format_guild_info_embed(guild: discord.Guild) -> discord.Embed:
        """Format guild info as Discord embed (matches ServerInfo cog format).
        
        This replicates the ServerInfo cog's embed format for consistency.
        
        Args:
            guild: Discord guild object
            
        Returns:
            Formatted Discord embed
        """
        if not guild:
            embed = discord.Embed(
                title="Error",
                description="Guild not found",
                color=0xFF0000
            )
            return embed
        
        guild_icon_url = str(guild.icon.url) if guild.icon else None
        creation_date = guild.created_at.strftime("%B %d, %Y") if guild.created_at else "Unknown"
        
        # Try to get owner member for display name (matches cog)
        try:
            if guild.owner_id:
                guild_owner = await guild.fetch_member(guild.owner_id)
                owner_name = guild_owner.display_name
            else:
                owner_name = "Unknown"
        except:
            owner_name = f"<@{guild.owner_id}>" if guild.owner_id else "Unknown"
        
        # Create embed matching ServerInfo cog format
        embed = discord.Embed(
            title=guild.name,
            description="Server Information",
            color=0x00ff00
        )
        
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Member Count", value=guild.member_count)
        embed.add_field(name="Server Owner", value=owner_name)
        embed.add_field(name="Creation Date", value=creation_date)
        
        if guild_icon_url:
            embed.set_thumbnail(url=guild_icon_url)
        
        return embed
    
    @staticmethod
    def format_guild_info_text(guild: discord.Guild) -> str:
        """Format guild info as plain text response (for non-embed contexts).
        
        Args:
            guild: Discord guild object
            
        Returns:
            Formatted text response
        """
        if not guild:
            return "Error: Guild not found"
        
        creation_date = guild.created_at.strftime("%B %d, %Y") if guild.created_at else "Unknown"
        
        return (
            f"**Guild Information**\n"
            f"**Name:** {guild.name}\n"
            f"**ID:** {guild.id}\n"
            f"**Members:** {guild.member_count}\n"
            f"**Owner ID:** {guild.owner_id}\n"
            f"**Created:** {creation_date}"
        )


class BotStatusTool:
    """Tool for managing bot status (config intent)."""
    
    @staticmethod
    def set_bot_status(
        bot: discord.Client,
        activity_type: str,
        message: str,
    ) -> Dict[str, Any]:
        """Set bot presence/status.
        
        Args:
            bot: Discord bot client
            activity_type: Type of activity ('playing', 'watching', 'listening', 'streaming', or None)
            message: Status message text
            
        Returns:
            Result dictionary with success flag and message
        """
        try:
            activity_type_lower: Optional[str] = activity_type.lower() if activity_type else None
            
            if activity_type_lower is None or activity_type_lower == "none":
                # Just set game activity
                activity = discord.Game(name=message)
            elif activity_type_lower == "playing":
                activity = discord.Game(name=message)
            elif activity_type_lower == "watching":
                activity = discord.Activity(type=discord.ActivityType.watching, name=message)
            elif activity_type_lower == "listening":
                activity = discord.Activity(type=discord.ActivityType.listening, name=message)
            elif activity_type_lower == "streaming":
                activity = discord.Streaming(name=message, url="https://twitch.tv")
            else:
                return {
                    "success": False,
                    "message": f"Unknown activity type: {activity_type}",
                }
            
            # This is a coroutine, so we'd need to await it in async context
            # For now, return the activity object for the caller to handle
            return {
                "success": True,
                "activity": activity,
                "activity_type": activity_type,
                "message": f"Status updated to: {activity_type} {message}",
            }
        except Exception as e:
            logger.error(f"[tool_status] Error setting bot status: {e}")
            return {
                "success": False,
                "message": f"Error setting status: {str(e)}",
            }
    
    @staticmethod
    def format_status_response(result: Dict[str, Any]) -> str:
        """Format status change result as text.
        
        Args:
            result: Result dictionary from set_bot_status()
            
        Returns:
            Formatted text response
        """
        if result.get("success"):
            return f"✓ {result['message']}"
        else:
            return f"Error: {result['message']}"


class ExpTool:
    """Tool for displaying user experience and level (task intent)."""
    
    @staticmethod
    async def format_exp_embed(user: discord.Member) -> discord.Embed:
        """Format user's exp as Discord embed (matches ExpCommands cog format).
        
        Reuses the experience.py cog's display logic for consistency.
        
        Args:
            user: Discord member object
            
        Returns:
            Formatted Discord embed
        """
        from abby_core.economy.xp import get_xp, get_level_from_xp, get_xp_required
        
        # Get XP data
        user_data = get_xp(user.id)
        if not user_data:
            embed = discord.Embed(
                title="❌ No XP Data",
                description=f"{user.mention} doesn't have any XP yet! Start chatting to earn experience.",
                color=discord.Color.red()
            )
            return embed
        
        xp = user_data.get("points", 0)
        level = get_level_from_xp(xp)
        xp_required = get_xp_required(level + 1)["xp_required"]
        
        try:
            prev_xp_required = get_xp_required(level)["xp_required"]
        except:
            prev_xp_required = 0
        
        # Calculate progress
        current_level_xp = xp - prev_xp_required
        xp_for_level = xp_required - prev_xp_required
        progress_percent = (current_level_xp / xp_for_level) * 100 if xp_for_level > 0 else 0
        
        # Create progress bar
        filled = int(progress_percent / 10)
        empty = 10 - filled
        progress_bar = "🍃" * filled + "⬛" * empty
        
        # Create embed (matches ExpCommands cog format)
        embed = discord.Embed(
            title=f"⭐ {user.display_name}'s Experience",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📊 Current Level",
            value=f"**Level {level}**",
            inline=True
        )
        
        embed.add_field(
            name="💎 Total XP",
            value=f"**{xp:,}** XP",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Next Level",
            value=f"**{xp_required - xp:,}** XP needed",
            inline=True
        )
        
        # Progress bar
        embed.add_field(
            name="📈 Progress to Next Level",
            value=f"{progress_bar} **{progress_percent:.1f}%**\n`{current_level_xp:,} / {xp_for_level:,} XP`",
            inline=False
        )
        
        # Set thumbnail and footer
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        embed.set_footer(
            text=f"Keep chatting to earn more XP!",
            icon_url=user.avatar.url if user.avatar else None
        )
        
        return embed
    
    @staticmethod
    def format_exp_text(user: discord.Member) -> str:
        """Format user's exp as plain text (fallback).
        
        Args:
            user: Discord member object
            
        Returns:
            Formatted text response
        """
        from abby_core.economy.xp import get_xp, get_level_from_xp
        
        user_data = get_xp(user.id)
        if not user_data:
            return f"{user.mention} doesn't have any XP yet!"
        
        xp = user_data.get("points", 0)
        level = get_level_from_xp(xp)
        
        return (
            f"⭐ **{user.display_name}'s Experience**\n"
            f"**Level:** {level}\n"
            f"**Total XP:** {xp:,}"
        )
