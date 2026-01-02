"""
Modern User Commands with Native UI

Replaces old prefix commands with modern slash commands:
- /suggest - Submit suggestions with Modal UI
- /help - Interactive help menu with categories
- /profile - View user profile and stats
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select
from abby_core.observability.logging import setup_logging, logging
from abby_core.database.mongodb import connect_to_mongodb
from datetime import datetime
from typing import Optional

setup_logging()
logger = logging.getLogger(__name__)


class SuggestionModal(Modal):
    """Modal for submitting suggestions."""
    
    def __init__(self):
        super().__init__(title="Submit a Suggestion", timeout=300)
        
        self.title_input = TextInput(
            label="Suggestion Title",
            placeholder="Brief title for your suggestion...",
            style=discord.TextStyle.short,
            max_length=100,
            required=True
        )
        
        self.description = TextInput(
            label="Description",
            placeholder="Detailed description of your suggestion...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        
        self.category = TextInput(
            label="Category",
            placeholder="e.g., Feature, Bot Improvement, Server, Other",
            style=discord.TextStyle.short,
            max_length=50,
            default="Other",
            required=False
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description)
        self.add_item(self.category)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(ephemeral=True)


class HelpMenuView(View):
    """Interactive help menu with category selection."""
    
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.bot = bot
        self.add_item(HelpCategorySelect(bot))


class HelpCategorySelect(Select):
    """Dropdown for help category selection."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        options = [
            discord.SelectOption(
                label="📋 Overview",
                description="General information about Abby",
                emoji="📋",
                value="overview"
            ),
            discord.SelectOption(
                label="⭐ Experience & Levels",
                description="XP system and leaderboards",
                emoji="⭐",
                value="exp"
            ),
            discord.SelectOption(
                label="🎮 Games & Fun",
                description="Entertainment commands",
                emoji="🎮",
                value="games"
            ),
            discord.SelectOption(
                label="🎁 Giveaways",
                description="Giveaway system",
                emoji="🎁",
                value="giveaways"
            ),
            discord.SelectOption(
                label="🎭 Personas",
                description="Switch between bot personalities",
                emoji="🎭",
                value="personas"
            ),
            discord.SelectOption(
                label="💬 Chat & AI",
                description="Chatbot and AI features",
                emoji="💬",
                value="chat"
            ),
            discord.SelectOption(
                label="🎨 Creative",
                description="Image generation and creative tools",
                emoji="🎨",
                value="creative"
            ),
            discord.SelectOption(
                label="⚙️ Admin Commands",
                description="Server management (Admin only)",
                emoji="⚙️",
                value="admin"
            )
        ]
        
        super().__init__(
            placeholder="Choose a help category...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection."""
        category = self.values[0]
        embed = self._get_category_embed(category)
        await interaction.response.edit_message(embed=embed)
    
    def _get_category_embed(self, category: str) -> discord.Embed:
        """Get embed for selected category."""
        embeds = {
            "overview": self._overview_embed(),
            "exp": self._exp_embed(),
            "games": self._games_embed(),
            "giveaways": self._giveaways_embed(),
            "personas": self._personas_embed(),
            "chat": self._chat_embed(),
            "creative": self._creative_embed(),
            "admin": self._admin_embed()
        }
        
        return embeds.get(category, self._overview_embed())
    
    def _overview_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🐰 Abby Bot - Overview",
            description=(
                "Hi there! I'm Abby, your friendly Discord assistant!\n\n"
                "I help with entertainment, moderation, XP tracking, "
                "AI conversations, and much more!\n\n"
                "**Use the dropdown menu below to explore different features!**"
            ),
            color=discord.Color.blue()
        )
        embed.add_field(
            name="💡 Getting Started",
            value=(
                "• Chat with me naturally - I'll respond!\n"
                "• Check `/help` for command categories\n"
                "• Use `/exp` to check your level\n"
                "• Try `/game emoji` for fun!"
            ),
            inline=False
        )
        return embed
    
    def _exp_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⭐ Experience & Levels",
            description="Track your server activity and climb the rankings!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="User Commands",
            value=(
                "`/exp [user]` - Check experience and level\n"
                "`/level [user]` - Quick level check\n"
                "`/leaderboard [top]` - View server rankings"
            ),
            inline=False
        )
        embed.add_field(
            name="📊 How XP Works",
            value=(
                "• Earn XP by chatting in the server\n"
                "• Win games for bonus XP\n"
                "• Level up to unlock perks\n"
                "• Cooldowns prevent spam"
            ),
            inline=False
        )
        return embed
    
    def _games_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎮 Games & Fun",
            description="Play games and have fun with the community!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Available Games",
            value=(
                "`/game emoji` - Emoji guessing game\n"
                "`/poll` - Create interactive polls\n"
                "`/meme` - Get random memes\n"
                "`/reddit` - Browse Reddit posts\n"
                "`/genrenator` - Random genre generator\n"
                "`/story` - Random story generator"
            ),
            inline=False
        )
        return embed
    
    def _giveaways_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎁 Giveaways",
            description="Host and participate in giveaways!",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="User Commands",
            value=(
                "`/giveaway list` - View active giveaways\n"
                "Click **🎉 Enter** button to join!"
            ),
            inline=False
        )
        embed.add_field(
            name="Admin Commands",
            value=(
                "`/giveaway create` - Create a giveaway\n"
                "`/giveaway end` - End a giveaway early"
            ),
            inline=False
        )
        return embed
    
    def _personas_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎭 Personas",
            description="Switch between different bot personalities!",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.add_field(
            name="Available Personas",
            value=(
                "🐰 **Abby** - Energetic bunny (default)\n"
                "🐱 **Kiki** - Playful kitten\n"
                "🦊 **Felix** - Clever fox\n"
                "*...and more!*"
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/persona list` - View all personas\n"
                "`/persona switch` - Change personality\n"
                "`/persona info` - Details about a persona"
            ),
            inline=False
        )
        return embed
    
    def _chat_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="💬 Chat & AI",
            description="Have conversations with Abby!",
            color=discord.Color.teal()
        )
        embed.add_field(
            name="How It Works",
            value=(
                "• Mention me or use my name to chat\n"
                "• I remember context from recent messages\n"
                "• Ask questions, get creative ideas!\n"
                "• Use `/analyze` for conversation insights"
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/analyze` - Analyze conversation patterns\n"
                "`/chat clear` - Clear conversation history"
            ),
            inline=False
        )
        return embed
    
    def _creative_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎨 Creative Tools",
            description="Generate images and creative content!",
            color=discord.Color.magenta()
        )
        embed.add_field(
            name="Image Generation",
            value=(
                "`/imagine <prompt>` - Generate AI images\n"
                "• Powered by Stability AI\n"
                "• High-quality results\n"
                "• Various styles available"
            ),
            inline=False
        )
        return embed
    
    def _admin_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚙️ Admin Commands",
            description="Server management commands (Administrator required)",
            color=discord.Color.red()
        )
        embed.add_field(
            name="XP Management",
            value=(
                "`/exp-admin add` - Add XP to users\n"
                "`/exp-admin remove` - Remove XP\n"
                "`/exp-admin reset` - Reset user XP\n"
                "`/exp-admin init-all` - Initialize all members"
            ),
            inline=False
        )
        embed.add_field(
            name="Bot Management",
            value=(
                "`!sync ~` - Sync slash commands (owner)\n"
                "`!reload` - Reload cogs (owner)\n"
                "`!shutdown` - Stop bot (owner)\n"
                "`/announce` - Create announcements"
            ),
            inline=False
        )
        return embed


class UserCommands(commands.Cog):
    """User-facing utility commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("[👤] Modern User Commands loaded")
    
    @app_commands.command(name="suggest", description="Submit a suggestion for the server or bot")
    async def suggest(self, interaction: discord.Interaction):
        """Submit a suggestion."""
        modal = SuggestionModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        # Store suggestion in database
        try:
            client = connect_to_mongodb()
            db = client["Abby_Database"]
            collection = db["suggestions"]
            
            suggestion_data = {
                "title": modal.title_input.value,
                "description": modal.description.value,
                "category": modal.category.value or "Other",
                "author_id": str(interaction.user.id),
                "author_name": interaction.user.display_name,
                "guild_id": str(interaction.guild_id),
                "status": "pending",
                "submitted_at": datetime.utcnow(),
                "upvotes": 0,
                "downvotes": 0
            }
            
            result = collection.insert_one(suggestion_data)
            
            # Confirmation embed
            embed = discord.Embed(
                title="✅ Suggestion Submitted!",
                description=f"**{modal.title_input.value}**",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Category", value=modal.category.value or "Other", inline=True)
            embed.add_field(name="ID", value=str(result.inserted_id)[:8], inline=True)
            embed.set_footer(text="Thank you for your feedback!")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"[👤] {interaction.user} submitted suggestion: {modal.title_input.value}")
            
        except Exception as e:
            logger.error(f"[👤] Error saving suggestion: {e}")
            await interaction.followup.send(
                "❌ An error occurred while saving your suggestion. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="help", description="View bot commands and features")
    async def help_command(self, interaction: discord.Interaction):
        """Display interactive help menu."""
        view = HelpMenuView(self.bot)
        
        # Initial embed
        embed = discord.Embed(
            title="🐰 Abby Bot - Help Menu",
            description=(
                "Welcome to Abby's help system!\n\n"
                "**Use the dropdown menu below** to explore different command categories.\n\n"
                "Select a category to see detailed command information."
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💡 Quick Tips",
            value=(
                "• All commands start with `/`\n"
                "• Some commands are admin-only\n"
                "• Chat with me naturally - just mention me!\n"
                "• Use `/suggest` to send feedback"
            ),
            inline=False
        )
        
        embed.set_footer(text="Select a category from the dropdown below!")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="profile", description="View your server profile and stats")
    @app_commands.describe(user="User to view profile for (leave empty for yourself)")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Display user profile."""
        target_user = user or interaction.user
        
        # Get XP data
        from abby_core.economy.xp import get_xp, get_level_from_xp
        
        user_data = get_xp(target_user.id)
        xp = user_data.get("points", 0) if user_data else 0
        level = get_level_from_xp(xp) if xp > 0 else 0
        
        # Create profile embed
        embed = discord.Embed(
            title=f"👤 {target_user.display_name}'s Profile",
            color=target_user.color if target_user.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if target_user.avatar:
            embed.set_thumbnail(url=target_user.avatar.url)
        
        # User info
        embed.add_field(
            name="📊 Server Stats",
            value=(
                f"**Level:** {level}\n"
                f"**XP:** {xp:,}\n"
                f"**Joined:** <t:{int(target_user.joined_at.timestamp())}:R>"
            ),
            inline=True
        )
        
        # Account info
        embed.add_field(
            name="👤 Account Info",
            value=(
                f"**ID:** {target_user.id}\n"
                f"**Created:** <t:{int(target_user.created_at.timestamp())}:R>\n"
                f"**Bot:** {'Yes' if target_user.bot else 'No'}"
            ),
            inline=True
        )
        
        # Roles (top 5)
        if target_user.roles[1:]:  # Exclude @everyone
            roles = [role.mention for role in reversed(target_user.roles[1:])][:5]
            embed.add_field(
                name=f"🎭 Roles ({len(target_user.roles) - 1})",
                value=" ".join(roles) if roles else "None",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add cog to bot."""
    await bot.add_cog(UserCommands(bot))
    logger.info("[👤] Modern User Commands loaded successfully")
