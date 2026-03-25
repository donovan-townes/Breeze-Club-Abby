"""
/stats command - Single entry point with in-message navigation (buttons),
mirroring the guild_config UX. Keeps slash command surface clean while
offering multiple views via buttons: Overview, Game Stats, XP/Level, Leaderboard.
"""

import discord
from discord import app_commands
from discord.ext import commands

from abby_core.economy.leveling import (
    get_game_leaderboard,
    get_game_stats,
    get_xp_progress_to_next_level,
    get_current_season,
    get_xp_for_level,
)
from abby_core.economy.xp import get_xp
from abby_core.economy.user_levels import get_user_levels_collection
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


def format_number(num: int) -> str:
    """Format large numbers with commas."""
    return f"{num:,}"


class StatsView(discord.ui.View):
    """Button-driven navigation for /stats embeds."""

    def __init__(self, cog: "StatsCommands", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id

    async def _update(self, interaction: discord.Interaction, tab: str):
        embed = await self.cog.build_embed(interaction, tab)
        new_view = StatsView(self.cog, self.owner_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="📊", row=0)
    async def button_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction, "overview")

    @discord.ui.button(label="Game", style=discord.ButtonStyle.secondary, emoji="🎲", row=0)
    async def button_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction, "game")

    @discord.ui.button(label="XP / Level", style=discord.ButtonStyle.secondary, emoji="📈", row=0)
    async def button_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction, "xp")

    @discord.ui.button(label="Leaderboard", style=discord.ButtonStyle.secondary, emoji="🏆", row=1)
    async def button_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction, "leaderboard")


class StatsCommands(commands.Cog):
    """Player statistics, leveling, and leaderboards via a single /stats entry."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.debug("[📊] Stats Commands loaded")

    @app_commands.command(name="stats", description="View your guild stats (Overview/Game/XP/Leaderboards)")
    async def stats(self, interaction: discord.Interaction):
        """Single entry point with button navigation."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command only works in servers.", ephemeral=True)
            return

        embed = await self.build_embed(interaction, tab="overview")
        view = StatsView(self, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    async def build_embed(self, interaction: discord.Interaction, tab: str) -> discord.Embed:
        """Build embed for the requested tab."""
        tab = tab.lower()
        if tab == "game":
            return await self._build_game_embed(interaction)
        if tab == "xp":
            return await self._build_xp_embed(interaction)
        if tab == "leaderboard":
            return await self._build_leaderboard_embed(interaction)
        return await self._build_overview_embed(interaction)

    async def _build_overview_embed(self, interaction: discord.Interaction) -> discord.Embed:
        user = interaction.user
        guild = interaction.guild

        user_xp = get_xp(user.id, guild.id) if guild else None
        current_xp = user_xp.get("xp", user_xp.get("points", 0)) if user_xp else 0
        
        # Get level from user_levels collection
        levels_coll = get_user_levels_collection()
        level_doc = levels_coll.find_one({"user_id": str(user.id), "guild_id": str(guild.id) if guild else None}) if guild else None
        current_level = level_doc.get("level", 1) if level_doc else 1
        
        progress = get_xp_progress_to_next_level(current_xp)

        game_stats = get_game_stats(user.id, guild.id, "emoji") if guild else None

        embed = discord.Embed(
            title=f"📊 {user.display_name}'s Guild Stats",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🎖️ Level",
            value=f"**{current_level}** • {format_number(current_xp)} XP",
            inline=True,
        )

        progress_bar = self._build_progress_bar(progress["percent_to_next"])
        embed.add_field(
            name="📈 Progress to Level " + str(current_level + 1),
            value=(
                f"{progress_bar}\n"
                f"{format_number(progress['xp_progress'])} / {format_number(progress['xp_needed'])} XP"
            ),
            inline=False,
        )

        if game_stats:
            embed.add_field(
                name="🎲 Emoji Game",
                value=(
                    f"**Played:** {game_stats['games_played']}\n"
                    f"**Wins:** {game_stats['games_won']}\n"
                    f"**Losses:** {game_stats['games_lost']}\n"
                    f"**Win Rate:** {game_stats['win_rate']}%"
                ),
                inline=True,
            )
        else:
            embed.add_field(
                name="🎲 Emoji Game",
                value="No games played yet!",
                inline=True,
            )

        embed.set_footer(text=f"Season: {get_current_season()}")
        return embed

    async def _build_game_embed(self, interaction: discord.Interaction) -> discord.Embed:
        user = interaction.user
        guild = interaction.guild

        game_stats = get_game_stats(user.id, guild.id, "emoji") if guild else None

        embed = discord.Embed(
            title=f"🎲 {user.display_name}'s Emoji Game Stats",
            color=discord.Color.gold(),
        )

        if not game_stats:
            embed.description = "You haven't played any emoji games yet! Use `/games` to start."
            embed.set_footer(text=f"Season: {get_current_season()}")
            return embed

        embed.add_field(
            name="📊 Overall Statistics",
            value=(
                f"**Games Played:** {format_number(game_stats['games_played'])}\n"
                f"**Games Won:** {game_stats['games_won']}\n"
                f"**Games Lost:** {game_stats['games_lost']}\n"
                f"**Win Rate:** {game_stats['win_rate']}%"
            ),
            inline=False,
        )

        embed.add_field(
            name="🏆 Achievements",
            value=(
                f"🥇 First Win: " + ("✅ Unlocked" if game_stats['games_won'] > 0 else "🔒 Locked") + "\n"
                f"💯 Perfect Game: " + (
                    "✅ Unlocked" if game_stats['win_rate'] == 100.0 and game_stats['games_played'] >= 5 else "🔒 Locked"
                )
            ),
            inline=False,
        )

        embed.set_footer(text=f"Season: {get_current_season()}")
        return embed

    async def _build_xp_embed(self, interaction: discord.Interaction) -> discord.Embed:
        user = interaction.user
        guild = interaction.guild

        user_xp = get_xp(user.id, guild.id) if guild else None
        current_xp = user_xp.get("xp", user_xp.get("points", 0)) if user_xp else 0
        
        # Get level from user_levels collection
        levels_coll = get_user_levels_collection()
        level_doc = levels_coll.find_one({"user_id": str(user.id), "guild_id": str(guild.id) if guild else None if guild else None}) if guild else None
        current_level = level_doc.get("level", 1) if level_doc else 1
        
        progress = get_xp_progress_to_next_level(current_xp)

        embed = discord.Embed(
            title=f"📈 {user.display_name}'s Level & XP",
            color=discord.Color.green(),
        )

        embed.add_field(name="🎖️ Current Level", value=f"**{current_level}**", inline=True)
        embed.add_field(name="💫 Total XP", value=f"**{format_number(current_xp)}**", inline=True)
        embed.add_field(name="", value="", inline=False)

        progress_bar = self._build_progress_bar(progress["percent_to_next"])
        embed.add_field(
            name=f"🎯 Progress to Level {current_level + 1}",
            value=(
                f"{progress_bar}\n"
                f"{format_number(progress['xp_progress'])} / {format_number(progress['xp_needed'])} XP\n"
                f"({progress['percent_to_next']}%)"
            ),
            inline=False,
        )

        next_levels = []
        for lvl in [current_level + 1, current_level + 2, current_level + 5]:
            xp_needed = get_xp_for_level(lvl) - current_xp
            if xp_needed > 0:
                next_levels.append(f"Level {lvl}: {format_number(xp_needed)} XP away")

        if next_levels:
            embed.add_field(name="🗺️ Upcoming Milestones", value="\n".join(next_levels), inline=False)

        embed.set_footer(text=f"Season: {get_current_season()}")
        return embed

    async def _build_leaderboard_embed(self, interaction: discord.Interaction) -> discord.Embed:
        guild = interaction.guild

        embed = discord.Embed(
            title=f"🏆 {guild.name} Leaderboards" if guild else "🏆 Leaderboards",
            color=discord.Color.gold(),
        )

        try:
            game_leaders = get_game_leaderboard(guild.id, "emoji", limit=3) if guild else []
            if game_leaders:
                game_text = ""
                for i, leader in enumerate(game_leaders, 1):
                    user_id = int(leader["user_id"])
                    try:
                        user = await self.bot.fetch_user(user_id)
                        name = user.display_name
                    except Exception:
                        name = f"User {user_id}"
                    game_text += f"{i}. **{name}** - {leader['games_won']} wins ({leader['win_rate']}%)\n"

                embed.add_field(name="🎲 Top Emoji Game Winners", value=game_text, inline=False)
            else:
                embed.add_field(name="🎲 Top Emoji Game Winners", value="No games played yet!", inline=False)
        except Exception as e:
            logger.error(f"Error fetching game leaderboard: {e}")
            embed.add_field(name="🎲 Top Emoji Game Winners", value="Error loading leaderboard", inline=False)

        embed.set_footer(text=f"Season: {get_current_season()}")
        return embed

    def _build_progress_bar(self, percent: float, length: int = 20) -> str:
        """Build a simple text-based progress bar."""
        filled = int(length * percent / 100)
        empty = length - filled
        return f"`[{'█' * filled}{'░' * empty}]`"


async def setup(bot: commands.Bot):
    """Load the stats cog."""
    await bot.add_cog(StatsCommands(bot))
