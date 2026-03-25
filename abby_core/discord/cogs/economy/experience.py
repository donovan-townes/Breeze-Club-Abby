"""
Modern Experience (XP) Command System

Consolidates exp_cog.py, commands/Admin/exp.py into a single, modern implementation
using Discord slash commands with proper UI elements.

Features:
- /exp - Check your experience and level
- /level - Quick level check
- /leaderboard - View server XP rankings
- /exp-admin - Admin commands for XP management (add/remove/reset)

All XP operations delegated to EconomyService (platform-agnostic).
This cog handles Discord UI only - no business logic.
"""

import discord
from discord import app_commands
from discord.ext import commands
from tdos_intelligence.observability import logging
from abby_core.economy.xp import (
    get_xp, get_level_from_xp, get_xp_required, fetch_all_users_exp
)
from abby_core.economy.user_levels import get_user_levels_collection
from abby_core.system.system_state import get_active_season
from abby_core.discord.cogs.economy.xp_rewards import current_xp_multiplier
from abby_core.services.economy_service import get_economy_service
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


class ExpCommands(commands.Cog):
    """Experience and leveling system for Discord server."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.debug("[⭐] EXP Commands loaded")
    
    def _create_progress_bar(self, progress_percent: float) -> str:
        """Create visual progress bar with emojis."""
        filled = int(progress_percent / 10)
        empty = 10 - filled
        return "🍃" * filled + "⬛" * empty
    
    def _create_exp_embed(self, user: discord.Member | discord.User, xp: int, level: int, 
                          xp_required: int, prev_xp_required: int) -> discord.Embed:
        """Create beautiful XP display embed."""
        # Calculate progress within current level (seasonal XP, not cumulative)
        # xp_for_level is the XP needed to go from current level to next level
        xp_for_level = xp_required - prev_xp_required
        # For seasonal XP (which resets to 0), progress is simply current XP toward next level
        # We don't subtract prev_xp_required because seasonal XP starts at 0 each season
        current_level_xp = xp
        xp_needed = xp_for_level  # Total XP needed to reach next level from 0
        progress_percent = (current_level_xp / xp_needed) * 100 if xp_needed > 0 else 0
        progress_bar = self._create_progress_bar(progress_percent)

        multiplier, holiday_name = current_xp_multiplier()
        multiplier_label = f"{multiplier}x"
        if holiday_name:
            multiplier_label += f" ({holiday_name})"
        
        # Get active season for context
        active_season = get_active_season()
        season_name = active_season.get("label", "Unknown Season") if active_season else "Unknown Season"
        
        # Create embed
        embed = discord.Embed(
            title=f"⭐ {user.display_name}'s Experience",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        # Add fields
        embed.add_field(
            name="📊 Current Level",
            value=f"**Level {level}** (Permanent)",
            inline=True
        )
        
        embed.add_field(
            name="💎 Seasonal XP",
            value=f"**{xp:,}** XP",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Next Level",
            value=f"**{xp_needed - current_level_xp:,}** XP needed",
            inline=True
        )

        embed.add_field(
            name="🌍 Current Season",
            value=f"{season_name}\nXP resets each season. Levels are permanent.",
            inline=False
        )

        embed.add_field(
            name="⚡ Current Multiplier",
            value=multiplier_label,
            inline=True
        )
        
        # Progress bar
        embed.add_field(
            name="📈 Progress to Next Level",
            value=f"{progress_bar} **{progress_percent:.1f}%**\n`{current_level_xp:,} / {xp_needed:,} XP`",
            inline=False
        )
        
        # Set thumbnail and footer
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        embed.set_footer(
            text="Keep chatting to earn more XP!",
            icon_url=user.avatar.url if user.avatar else None
        )
        
        return embed
    
    @app_commands.command(name="exp", description="Check your experience and level progress")
    @app_commands.describe(user="User to check (leave empty for yourself)")
    async def exp(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Display experience and level for a user."""
        target_user = user or interaction.user
        guild_id = interaction.guild.id if interaction.guild else None
        
        # Get XP data
        user_data = get_xp(target_user.id, guild_id)
        if not user_data:
            if target_user == interaction.user:
                await interaction.response.send_message(
                    "❌ You don't have any XP yet! Start chatting to earn experience.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {target_user.mention} doesn't have any XP yet.",
                    ephemeral=True
                )
            return
        
        # Read from new schema (xp field, backward compat with points)
        xp = user_data.get("xp", user_data.get("points", 0))
        
        # Get level from user_levels collection
        levels_coll = get_user_levels_collection()
        level_doc = levels_coll.find_one({"user_id": str(target_user.id), "guild_id": str(guild_id)})
        level = level_doc.get("level", 1) if level_doc else 1
        
        xp_required = get_xp_required(level + 1)["xp_required"]
        
        try:
            prev_xp_required = get_xp_required(level)["xp_required"]
        except:
            prev_xp_required = 0
        
        # Create and send embed
        embed = self._create_exp_embed(target_user, xp, level, xp_required, prev_xp_required)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="level", description="Quickly check your current level")
    @app_commands.describe(user="User to check (leave empty for yourself)")
    async def level(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Quick level check."""
        target_user = user or interaction.user
        guild_id = interaction.guild.id if interaction.guild else None
        
        user_data = get_xp(target_user.id, guild_id)
        if not user_data:
            await interaction.response.send_message(
                "❌ No XP data found.",
                ephemeral=True
            )
            return
        
        # Get level from user_levels collection
        levels_coll = get_user_levels_collection()
        level_doc = levels_coll.find_one({"user_id": str(target_user.id), "guild_id": str(guild_id)})
        level = level_doc.get("level", 1) if level_doc else 1
        
        embed = discord.Embed(
            description=f"🏆 {target_user.mention} is **Level {level}**!",
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard", description="View server XP leaderboard")
    @app_commands.describe(top="Number of users to show (default: 10)")
    async def leaderboard(self, interaction: discord.Interaction, top: int = 10):
        """Display server XP leaderboard."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command only works in servers.",
                ephemeral=True
            )
            return

        # Validate input
        if top < 1:
            top = 10
        elif top > 25:
            top = 25
        
        # Fetch all users' XP
        all_xp = fetch_all_users_exp(interaction.guild.id)
        if not all_xp:
            await interaction.response.send_message(
                "❌ No XP data found in this server.",
                ephemeral=True
            )
            return
        
        # Sort and get top users
        sorted_users = sorted(all_xp.items(), key=lambda x: x[1], reverse=True)[:top]
        
        # Create embed
        embed = discord.Embed(
            title="🏆 Experience Leaderboard 🏆",
            description="Top members by total experience",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        # Add server icon
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        # Build leaderboard text
        leaderboard_text = ""
        for position, (user_id, xp) in enumerate(sorted_users, start=1):
            user = interaction.guild.get_member(user_id) or self.bot.get_user(user_id)
            if not user:
                continue
            
            # Medal emojis for top 3
            if position == 1:
                emoji = "🥇"
            elif position == 2:
                emoji = "🥈"
            elif position == 3:
                emoji = "🥉"
            else:
                emoji = f"**{position}.**"
            
            level = get_level_from_xp(xp)
            leaderboard_text += f"{emoji} {user.mention} - Level **{level}** ({xp:,} XP)\n"
        
        embed.add_field(
            name=f"Top {len(sorted_users)} Members",
            value=leaderboard_text or "No data",
            inline=False
        )
        
        embed.set_footer(text="Keep chatting to climb the ranks!")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cooldown-debug", description="[ADMIN] Check daily bonus cooldown status for a user")
    @app_commands.describe(user="User to check cooldown status for")
    async def cooldown_debug(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Debug command to check cooldown status."""
        # Only allow bot owner/admins
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ This command is admin-only.",
                ephemeral=True
            )
            return
        
        target_user = user or interaction.user
        
        # Get XPRewardManager cog for debug info
        xp_cog = self.bot.get_cog("XPRewardManager")
        if not xp_cog:
            await interaction.response.send_message(
                "❌ XPRewardManager cog not loaded.",
                ephemeral=True
            )
            return
        
        debug_info = xp_cog._get_cooldown_debug_info(target_user.id)
        
        # Create embed with debug info
        embed = discord.Embed(
            title="🔍 Daily Bonus Cooldown Debug",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="User ID (as int)", value=f"`{target_user.id}`", inline=True)
        embed.add_field(name="User ID (as string)", value=f"`{str(target_user.id)}`", inline=True)
        embed.add_field(name="User Exists in DB", value=str(debug_info.get("user_exists", False)), inline=True)
        embed.add_field(name="Cooldown Active Today", value=str(debug_info.get("is_cooldown_active_today", False)), inline=True)
        embed.add_field(name="In-Memory Tracking", value=str(debug_info.get("in_memory_tracked", False)), inline=True)
        
        if debug_info.get("last_used_at"):
            embed.add_field(
                name="Last Used At (UTC)",
                value=f"`{debug_info['last_used_at']}`",
                inline=False
            )
            if debug_info.get("last_used_at_tzinfo"):
                embed.add_field(
                    name="Timezone Info",
                    value=f"`{debug_info['last_used_at_tzinfo']}`",
                    inline=True
                )
        
        if debug_info.get("current_utc_time"):
            embed.add_field(
                name="Current UTC Time",
                value=f"`{debug_info['current_utc_time']}`",
                inline=False
            )
        
        if debug_info.get("today_start_utc"):
            embed.add_field(
                name="Today Start (UTC Midnight)",
                value=f"`{debug_info['today_start_utc']}`",
                inline=False
            )
        
        if debug_info.get("timezone_info"):
            embed.add_field(
                name="ℹ️ Calculation Method",
                value=debug_info['timezone_info'],
                inline=False
            )
        
        if debug_info.get("error"):
            embed.color = discord.Color.red()
            embed.add_field(
                name="❌ Error",
                value=f"{debug_info['error']}",
                inline=False
            )
            if debug_info.get("error_type"):
                embed.add_field(
                    name="Error Type",
                    value=f"`{debug_info['error_type']}`",
                    inline=True
                )
        else:
            embed.color = discord.Color.green()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
async def setup(bot: commands.Bot):
    """Add cogs to bot."""
    await bot.add_cog(ExpCommands(bot))

