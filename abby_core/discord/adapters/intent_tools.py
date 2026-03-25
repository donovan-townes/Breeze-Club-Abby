"""Discord intent tool wrappers.

Provides intent-friendly tool names and output formatting that map to
platform-agnostic tool interfaces. These wrappers expose a single
`execute(context)` coroutine used by the intent tool registry.
"""

from typing import Any, Dict, Optional

import discord

from abby_core.interfaces.tools import (
    BotStatus,
    ToolResult,
)
from abby_core.discord.adapters import (
    DiscordServerInfoTool,
    DiscordUserXPTool,
    DiscordBotStatusTool,
)


class DiscordIntentGetGuildInfoTool:
    """Intent wrapper for guild/server info."""

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        guild = context.get("guild")
        bot = context.get("bot")

        if guild is None:
            return {
                "text": "Guild not available for server info.",
                "error": "guild_missing",
            }

        # Build info using the platform tool for consistency.
        tool = DiscordServerInfoTool()
        result = await tool.get_server_info(str(guild.id), {"bot": bot})
        if not result.success:
            return {
                "text": result.error or "Server info lookup failed.",
                "error": result.error or "server_info_failed",
            }

        data = result.data or {}
        text = (
            "Server Info: {name} (ID: {server_id}) | Members: {member_count} "
            "| Owner: {owner_name} | Created: {created_at}"
        ).format(
            name=data.get("name", "Unknown"),
            server_id=data.get("server_id", "Unknown"),
            member_count=data.get("member_count", "Unknown"),
            owner_name=data.get("owner_name", "Unknown"),
            created_at=data.get("created_at", "Unknown"),
        )

        embed = discord.Embed(
            title=data.get("name", "Server Info"),
            description="Server Information",
            color=0x00FF00,
        )
        embed.add_field(name="Server ID", value=data.get("server_id", "Unknown"), inline=True)
        embed.add_field(name="Member Count", value=data.get("member_count", "Unknown"), inline=True)
        embed.add_field(name="Owner", value=data.get("owner_name", "Unknown"), inline=True)
        embed.add_field(name="Created", value=data.get("created_at", "Unknown"), inline=True)

        icon_url = data.get("icon_url")
        if icon_url:
            embed.set_thumbnail(url=icon_url)

        return {
            "text": text,
            "embed": embed,
            "data": data,
            "success": True,
        }


class DiscordIntentGetUserExpTool:
    """Intent wrapper for user XP/level info."""

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        user = context.get("user")
        bot = context.get("bot")
        guild = context.get("guild")

        if user is None:
            return {
                "text": "User not available for XP lookup.",
                "error": "user_missing",
            }

        tool = DiscordUserXPTool()
        result = await tool.get_user_xp(
            str(user.id),
            str(guild.id) if guild else None,
            {"bot": bot},
        )
        if not result.success:
            return {
                "text": result.error or "XP lookup failed.",
                "error": result.error or "user_xp_failed",
            }

        data = result.data or {}
        text = (
            "XP for {display_name}: Level {level} | XP {xp} | "
            "Next level in {xp_to_next_level}"
        ).format(
            display_name=data.get("display_name", data.get("username", "Unknown")),
            level=data.get("level", "Unknown"),
            xp=data.get("xp", "Unknown"),
            xp_to_next_level=data.get("xp_to_next_level", "Unknown"),
        )

        return {
            "text": text,
            "data": data,
            "success": True,
        }


class DiscordIntentSetBotStatusTool:
    """Intent wrapper for bot status updates."""

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        bot = context.get("bot")
        activity_type = context.get("activity_type") or "playing"
        message = context.get("message") or "available"

        status = BotStatus(status_type=activity_type, message=message)
        tool = DiscordBotStatusTool()
        result: ToolResult = await tool.set_status(status, {"bot": bot})

        if not result.success:
            return {
                "text": result.error or "Failed to update status.",
                "error": result.error or "bot_status_failed",
            }

        return {
            "text": result.message or "Status updated.",
            "success": True,
        }
