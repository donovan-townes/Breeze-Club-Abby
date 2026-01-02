"""
Modern Experience (XP) Command System

Consolidates exp_cog.py, commands/Admin/exp.py into a single, modern implementation
using Discord slash commands with proper UI elements.

Features:
- /exp - Check your experience and level
- /level - Quick level check
- /leaderboard - View server XP rankings
- /exp-admin - Admin commands for XP management (add/remove/reset)
"""

import discord
from discord import app_commands
from discord.ext import commands
from abby_core.observability.logging import setup_logging, logging
from abby_core.economy.xp import (
    increment_xp, decrement_xp, get_xp, initialize_xp, 
    reset_exp, get_level_from_xp, get_xp_required, fetch_all_users_exp
)
from datetime import datetime
from typing import Optional

setup_logging()
logger = logging.getLogger(__name__)


class ExpCommands(commands.Cog):
    """Experience and leveling system for Discord server."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("[⭐] Modern EXP Commands loaded")
    
    def _create_progress_bar(self, progress_percent: float) -> str:
        """Create visual progress bar with emojis."""
        filled = int(progress_percent / 10)
        empty = 10 - filled
        return "🍃" * filled + "⬛" * empty
    
    def _create_exp_embed(self, user: discord.Member, xp: int, level: int, 
                          xp_required: int, prev_xp_required: int) -> discord.Embed:
        """Create beautiful XP display embed."""
        # Calculate progress
        current_level_xp = xp - prev_xp_required
        xp_for_level = xp_required - prev_xp_required
        progress_percent = (current_level_xp / xp_for_level) * 100 if xp_for_level > 0 else 0
        progress_bar = self._create_progress_bar(progress_percent)
        
        # Create embed
        embed = discord.Embed(
            title=f"⭐ {user.display_name}'s Experience",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        # Add fields
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
    
    @app_commands.command(name="exp", description="Check your experience and level progress")
    @app_commands.describe(user="User to check (leave empty for yourself)")
    async def exp(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Display experience and level for a user."""
        target_user = user or interaction.user
        
        # Get XP data
        user_data = get_xp(target_user.id)
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
        
        xp = user_data.get("points", 0)
        level = get_level_from_xp(xp)
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
        
        user_data = get_xp(target_user.id)
        if not user_data:
            await interaction.response.send_message(
                "❌ No XP data found.",
                ephemeral=True
            )
            return
        
        xp = user_data.get("points", 0)
        level = get_level_from_xp(xp)
        
        embed = discord.Embed(
            description=f"🏆 {target_user.mention} is **Level {level}**!",
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard", description="View server XP leaderboard")
    @app_commands.describe(top="Number of users to show (default: 10)")
    async def leaderboard(self, interaction: discord.Interaction, top: int = 10):
        """Display server XP leaderboard."""
        # Validate input
        if top < 1:
            top = 10
        elif top > 25:
            top = 25
        
        # Fetch all users' XP
        all_xp = fetch_all_users_exp()
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
            user = self.bot.get_user(user_id) or interaction.guild.get_member(user_id)
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


# Admin commands group
class ExpAdminCommands(commands.GroupCog, name="exp-admin"):
    """Administrative commands for managing XP (Admin only)."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()
        logger.info("[⭐] EXP Admin Commands loaded")
    
    @app_commands.command(name="add", description="[Admin] Add XP to a user")
    @app_commands.describe(
        user="User to give XP to",
        amount="Amount of XP to add"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_xp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Add XP to a user."""
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild_id
        
        try:
            increment_xp(user.id, amount, guild_id)
            
            # Get updated info
            user_data = get_xp(user.id)
            new_xp = user_data.get("points", 0)
            new_level = get_level_from_xp(new_xp)
            
            embed = discord.Embed(
                title="✅ XP Added",
                description=f"Added **{amount:,} XP** to {user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="New Total", value=f"{new_xp:,} XP", inline=True)
            embed.add_field(name="Level", value=f"{new_level}", inline=True)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"[⭐] {interaction.user} added {amount} XP to {user}")
            
        except Exception as e:
            logger.error(f"[⭐] Error adding XP: {e}")
            await interaction.response.send_message(
                f"❌ Error adding XP: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="remove", description="[Admin] Remove XP from a user")
    @app_commands.describe(
        user="User to remove XP from",
        amount="Amount of XP to remove"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_xp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Remove XP from a user."""
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild_id
        
        try:
            decrement_xp(user.id, amount, guild_id)
            
            # Get updated info
            user_data = get_xp(user.id)
            new_xp = user_data.get("points", 0)
            new_level = get_level_from_xp(new_xp)
            
            embed = discord.Embed(
                title="✅ XP Removed",
                description=f"Removed **{amount:,} XP** from {user.mention}",
                color=discord.Color.orange()
            )
            embed.add_field(name="New Total", value=f"{new_xp:,} XP", inline=True)
            embed.add_field(name="Level", value=f"{new_level}", inline=True)
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"[⭐] {interaction.user} removed {amount} XP from {user}")
            
        except Exception as e:
            logger.error(f"[⭐] Error removing XP: {e}")
            await interaction.response.send_message(
                f"❌ Error removing XP: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="reset", description="[Admin] Reset a user's XP to 0")
    @app_commands.describe(user="User to reset XP for")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_xp(self, interaction: discord.Interaction, user: discord.Member):
        """Reset a user's XP to 0."""
        # Confirmation view
        view = ConfirmView(interaction.user)
        
        embed = discord.Embed(
            title="⚠️ Confirm XP Reset",
            description=f"Are you sure you want to reset **all XP** for {user.mention}?\n\nThis action cannot be undone!",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        
        if view.value is None:
            await interaction.edit_original_response(content="❌ Timed out.", embed=None, view=None)
            return
        elif not view.value:
            await interaction.edit_original_response(content="❌ Cancelled.", embed=None, view=None)
            return
        
        try:
            reset_exp(user.id)
            
            embed = discord.Embed(
                title="✅ XP Reset",
                description=f"Reset XP for {user.mention} to **0**",
                color=discord.Color.green()
            )
            
            await interaction.edit_original_response(embed=embed, view=None)
            logger.info(f"[⭐] {interaction.user} reset XP for {user}")
            
        except Exception as e:
            logger.error(f"[⭐] Error resetting XP: {e}")
            await interaction.edit_original_response(
                content=f"❌ Error resetting XP: {str(e)}",
                embed=None,
                view=None
            )
    
    @app_commands.command(name="init-all", description="[Admin] Initialize XP for all server members")
    @app_commands.checks.has_permissions(administrator=True)
    async def init_all(self, interaction: discord.Interaction):
        """Initialize XP for all members in the server."""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        initialized = 0
        
        for member in guild.members:
            if not member.bot:  # Skip bots
                try:
                    initialize_xp(member.id)
                    initialized += 1
                except:
                    pass
        
        embed = discord.Embed(
            title="✅ XP Initialization Complete",
            description=f"Initialized XP for **{initialized}** members",
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"[⭐] {interaction.user} initialized XP for {initialized} members")


class ConfirmView(discord.ui.View):
    """Confirmation dialog with Yes/No buttons."""
    
    def __init__(self, user: discord.User):
        super().__init__(timeout=30)
        self.user = user
        self.value = None
    
    @discord.ui.button(label="Yes, Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your confirmation dialog!", ephemeral=True)
            return
        self.value = True
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your confirmation dialog!", ephemeral=True)
            return
        self.value = False
        self.stop()


async def setup(bot: commands.Bot):
    """Add cogs to bot."""
    await bot.add_cog(ExpCommands(bot))
    await bot.add_cog(ExpAdminCommands(bot))
    logger.info("[⭐] Modern EXP system loaded successfully")
