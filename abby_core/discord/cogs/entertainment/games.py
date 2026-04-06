"""
Modern Games Nexus with Button UI

Consolidates all game operations under a single `/games` nexus command.
Currently features:
- Emoji Guessing Game

Designed for extensibility: add more games as buttons on the landing panel.

Features:
- /games - Main landing panel (show available games, status)
- Emoji Game - Start via button (modal for settings)
- Button-based UI (no more reactions!)
- Auto-game scheduling (via centralized scheduler in system/job_handlers.py)
- XP rewards for winners
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
from tdos_intelligence.observability import logging
from abby_core.discord.config import BotConfig
from abby_core.economy.xp import increment_xp
from abby_core.discord.cogs.economy.xp_rewards import current_xp_multiplier
from abby_core.economy.leveling import record_game_result
from abby_core.database.collections.guild_configuration import (
    get_guild_config,
    get_memory_settings,
    set_memory_settings,
)
from datetime import datetime, time, timezone
import random
import asyncio

logger = logging.getLogger(__name__)

config = BotConfig()


class GamesLandingPanel(discord.ui.View):
    """Landing panel for all games - shows available games and management options."""

    def __init__(self, guild_id: Optional[int], bot: commands.Bot):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.bot = bot

    async def build_embed(self) -> discord.Embed:
        """Build landing panel embed."""
        embed = discord.Embed(
            title="🎮 Abby's Games",
            description="Choose a game to play or configure auto-game settings.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🎯 Available Games",
            value="🎪 **Emoji Game** - Guess the correct emoji!\n\n"
                  "*More games coming soon...*",
            inline=False
        )

        embed.add_field(
            name="🎮 Actions",
            value="Use the buttons below to start a game or configure settings.",
            inline=False
        )

        embed.set_footer(text="Win games to earn XP!")
        return embed

    @discord.ui.button(label="Play Emoji Game", style=discord.ButtonStyle.primary, emoji="🎪", row=0)
    async def button_emoji_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start an emoji guessing game."""
        await interaction.response.defer()

        bot = interaction.client
        if isinstance(bot, commands.Bot):
            cog: Optional["GamesManager"] = bot.get_cog("GamesManager")  # type: ignore[assignment]
            if cog and isinstance(interaction.channel, discord.TextChannel):
                starter = interaction.user if isinstance(interaction.user, discord.User) else None  # type: ignore[assignment]
                await cog._start_emoji_game(interaction.channel, starter)
            else:
                await interaction.followup.send("❌ Games system unavailable.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Games system unavailable.", ephemeral=True)

    @discord.ui.button(label="Auto-Game Settings", style=discord.ButtonStyle.secondary, emoji="⚙️", row=0)
    async def button_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show auto-game configuration (admin only)."""
        user = interaction.user
        if not isinstance(user, discord.Member) or not user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need manage guild permissions to configure games.",
                ephemeral=True
            )
            return

        # Just acknowledge for now - detailed settings can be added to /config
        await interaction.response.send_message(
            "⚙️ Auto-game settings are managed in `/config` → Scheduling → Auto-Game.",
            ephemeral=True
        )


class EmojiGameView(View):
    """View with emoji buttons for the game."""
    
    def __init__(self, winning_emoji: str, all_emojis: list, timeout_seconds: Optional[int] = None):
        # Use None for no timeout (we'll manage duration manually)
        # Discord max is 900 seconds (15 min), but we can set None for longer games
        super().__init__(timeout=timeout_seconds)
        self.winning_emoji = winning_emoji
        self.correct_users = []
        self.incorrect_users = []
        self.game_over = False
        
        # Create buttons for each emoji.
        # Use an index prefix so custom_ids are always unique even if the caller
        # somehow passes a list with duplicate emoji values.
        for i, emoji in enumerate(all_emojis):
            button = Button(
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"emoji_{i}_{emoji}"
            )
            button.callback = self._create_callback(emoji)
            self.add_item(button)
    
    def _create_callback(self, emoji: str):
        """Create callback function for emoji button."""
        async def callback(interaction: discord.Interaction):
            if self.game_over:
                await interaction.response.send_message(
                    "⏰ Game already ended!",
                    ephemeral=True
                )
                return
            
            user = interaction.user
            
            # Check if user already clicked
            if user in self.correct_users or user in self.incorrect_users:
                await interaction.response.send_message(
                    "🚫 You already made your choice!",
                    ephemeral=True
                )
                return
            
            # Record the choice (don't reveal correct/wrong yet)
            if emoji == self.winning_emoji:
                self.correct_users.append(user)
            else:
                self.incorrect_users.append(user)
            
            # Neutral confirmation - no spoilers
            await interaction.response.send_message(
                "✓ Your selection recorded! Wait for results...",
                ephemeral=True
            )
        
        return callback
    
    def get_participant_count(self) -> int:
        """Get total number of participants who have made a selection."""
        return len(self.correct_users) + len(self.incorrect_users)
    
    async def on_timeout(self):
        """Called when the view times out."""
        self.game_over = True
        # Disable all buttons
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True


class GamesManager(commands.Cog):
    """Games management system - consolidated under /games nexus."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_game = False
        
        # Emoji choices — must contain no duplicates; duplicate entries produce
        # identical custom_ids on the button row which Discord rejects (400 50035).
        self.custom_emojis = [
            "❤️", "🌟", "💥", "🍀", "🎯", "🎨",
            "🎭", "🎪", "🎸", "🎺", "🎲", "🏆"
        ]
        
        # Use centralized config for channel and guild
        self.game_channel_id = config.channels.breeze_lounge
        self.guild_id = config.server_info.guild_id
        
        logger.debug("[🎮] Games manager loaded")
    
    # Cog unload removed - no tasks to cancel (centralized scheduler handles auto-game)

    @app_commands.command(name="games", description="View available games and play")
    async def games_landing(self, interaction: discord.Interaction):
        """Show games landing panel with available games."""
        view = GamesLandingPanel(interaction.guild_id, self.bot)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    async def _start_emoji_game(self, channel: discord.TextChannel, starter: Optional[discord.User] = None):
        """Internal method to start an emoji game via button/auto-game."""
        if self.active_game:
            if starter:
                logger.warning("[🎮] Game already active, rejecting start request")
            return
        
        # Type check the channel
        if not isinstance(channel, discord.TextChannel):
            logger.warning("[🎮] Invalid channel type for emoji game")
            return
        
        # Create and send the initial game embed using the interaction
        self.active_game = True
        grid_size = 4
        selected_emojis = random.sample(self.custom_emojis, grid_size)
        winning_emoji = random.choice(selected_emojis)
        
        # Get duration from guild config, default to 5 minutes
        try:
            guild = channel.guild
            if guild:
                guild_config = get_guild_config(guild.id)
                scheduling = guild_config.get("scheduling", {})
                duration_minutes = scheduling.get("auto_game", {}).get("duration_minutes", 5)
            else:
                duration_minutes = 5
        except Exception:
            duration_minutes = 5
        
        # Create game embed
        embed = discord.Embed(
            title="🎮 EMOJI GUESSING GAME! 🎮",
            description=(
                "**Can you guess the correct emoji?**\n\n"
                "Click the button with the winning emoji to win!\n"
                "🎁 Winners get **+10 XP** (multiplier applies)!\n\n"
                f"⏱️ You have **{duration_minutes} minute{'s' if duration_minutes != 1 else ''}** to make your selection."
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="How to Play",
            value=f"Choose from {grid_size} emojis below. Your selection is private until results!",
            inline=False
        )
        
        if starter:
            embed.set_footer(text=f"Started by {starter.display_name} | Participating: 0")
        else:
            embed.set_footer(text="Auto-started daily game | Participating: 0")
        
        # Create view with buttons
        view = EmojiGameView(winning_emoji, selected_emojis, timeout_seconds=None)

        # Send the embed directly to channel
        try:
            game_message = await channel.send(embed=embed, view=view)
        except discord.HTTPException as e:
            self.active_game = False
            logger.error(f"[🎮] Failed to send game message, rolling back active state: {e}")
            raise

        # Start the game logic with pre-created message
        await self._run_game(
            channel,
            starter,
            game_message=game_message,
            winning_emoji=winning_emoji,
            view=view,
            duration_minutes=duration_minutes
        )
    
    async def _run_game(self, channel: discord.TextChannel, starter: Optional[discord.User | discord.Member] = None, 
                         game_message: Optional[discord.Message] = None, winning_emoji: Optional[str] = None, 
                         view: Optional[EmojiGameView] = None, duration_minutes: int = 5):
        """Internal method to run a game.
        
        Args:
            channel: Channel to post game in
            starter: User who started the game (None for auto-games)
            game_message: Pre-created game message (for manual games via interaction)
            winning_emoji: Pre-selected winning emoji (for manual games)
            view: Pre-created view with buttons (for manual games)
            duration_minutes: How long the game lasts (1-60 minutes)
        """
        if not self.active_game:
            self.active_game = True

        if not game_message:
            # Auto-game flow: create embed and send normally
            grid_size = 4
            selected_emojis = random.sample(self.custom_emojis, grid_size)
            winning_emoji = random.choice(selected_emojis)
            
            # Clamp duration between 1-60 minutes
            duration_minutes = max(1, min(60, duration_minutes))
            duration_seconds = duration_minutes * 60
            
            logger.info(f"[🎮] Game started | Emojis: {selected_emojis} | Winner: {winning_emoji} | Duration: {duration_minutes}m")
            
            # Create game embed
            embed = discord.Embed(
                title="🎮 EMOJI GUESSING GAME! 🎮",
                description=(
                    "**Can you guess the correct emoji?**\n\n"
                    "Click the button with the winning emoji to win!\n"
                    f"⏱️ You have **{duration_minutes} minute{'s' if duration_minutes != 1 else ''}** to make your selection."
                ),
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="How to Play",
                value=f"Choose from {grid_size} emojis below. Your selection is private until results!",
                inline=False
            )
            
            if starter:
                embed.set_footer(text=f"Started by {starter.display_name} | Participating: 0")
            else:
                embed.set_footer(text="Auto-started daily game | Participating: 0")
            
            # Create view with buttons (no timeout - we manage duration manually)
            view = EmojiGameView(winning_emoji, selected_emojis, timeout_seconds=None)
            try:
                game_message = await channel.send(embed=embed, view=view)
            except discord.HTTPException as e:
                # Roll back active state so the next scheduled tick can start a fresh game.
                self.active_game = False
                logger.error(f"[🎮] Failed to send game message, rolling back active state: {e}")
                raise
        else:
            # Manual game flow: game_message, winning_emoji, and view already created
            duration_minutes = max(1, min(60, duration_minutes))
            duration_seconds = duration_minutes * 60
            
            logger.info(f"[🎮] Game started | Winner: {winning_emoji} | Duration: {duration_minutes}m")
        
        # Game duration countdown with participant counter and time updates
        async def update_game_embed(remaining_seconds: int):
            """Update embed with remaining time and participant count."""
            if not game_message or not view:
                return
            try:
                embeds = game_message.embeds
                if embeds and len(embeds) > 0:
                    embed = embeds[0]
                    if embed and embed.footer and embed.footer.text:
                        footer_text = embed.footer.text.split(' | ')[0] if ' | ' in embed.footer.text else embed.footer.text
                        participant_count = view.get_participant_count()
                        
                        # Format remaining time
                        remaining_mins = remaining_seconds // 60
                        remaining_secs = remaining_seconds % 60
                        if remaining_mins > 0:
                            time_str = f"{remaining_mins}m {remaining_secs}s remaining!"
                        else:
                            time_str = f"{remaining_secs}s remaining!"
                        
                        embed.set_footer(text=f"{footer_text} | {time_str} | Participating: {participant_count}")
                        await game_message.edit(embed=embed)
            except Exception:
                pass
        
        if duration_minutes > 2:
            # Long game: warn at halfway and 30 seconds before end
            halfway = duration_seconds // 2
            
            # Sleep in 5-second chunks to update participant counter and remaining time
            elapsed = 0
            while elapsed < halfway and self.active_game:
                sleep_time = min(5, halfway - elapsed)
                await asyncio.sleep(sleep_time)
                elapsed += sleep_time
                remaining = duration_seconds - elapsed
                # Update embed every 10 seconds
                if elapsed % 10 == 0:
                    await update_game_embed(remaining)
            
            if self.active_game and game_message:
                remaining_minutes = (duration_seconds - halfway) // 60
                msg = await channel.send(f"⏰ **{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''} left!**")
                await update_game_embed(duration_seconds - halfway)
                await asyncio.sleep(8)
                try:
                    await msg.delete()
                except Exception:
                    pass
            
            await asyncio.sleep(duration_seconds - halfway - 30)
            if self.active_game and game_message:
                msg = await channel.send("⏰ **30 seconds left!**")
                await update_game_embed(30)
                await asyncio.sleep(8)
                try:
                    await msg.delete()
                except Exception:
                    pass
            
            await asyncio.sleep(22)  # 30 - 8 = 22 more seconds
        else:
            # Short game: standard countdown
            if duration_seconds > 30:
                await asyncio.sleep(duration_seconds - 30)
                if self.active_game and game_message:
                    msg = await channel.send("⏰ **30 seconds left!**")
                    await update_game_embed(30)
                    await asyncio.sleep(8)
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                await asyncio.sleep(22)  # 30 - 8 = 22 more seconds
            else:
                await asyncio.sleep(duration_seconds - 5)
            
            if self.active_game and game_message:
                msg = await channel.send("⏰ **5 seconds left!**")
                await update_game_embed(5)
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except Exception:
                    pass
            await asyncio.sleep(2)
        
        # End game
        if view and winning_emoji:
            await self._end_game(channel, game_message, view, winning_emoji)
    
    async def _end_game(self, channel: discord.TextChannel, game_message: discord.Message, 
                       view: EmojiGameView, winning_emoji: str):
        """End the game and update the original embed with results."""
        self.active_game = False
        view.game_over = True
        
        # Disable all buttons
        for child in view.children:
            if isinstance(child, Button):
                child.disabled = True
        
        # Create results embed - REPLACES the original
        embed = discord.Embed(
            title="🎮 GAME OVER! 🎮",
            description=f"The winning emoji was: **{winning_emoji}**",
            color=discord.Color.green()
        )
        
        # Winning message
        total_players = len(view.correct_users) + len(view.incorrect_users)
        win_rate = (len(view.correct_users) / total_players * 100) if total_players > 0 else 0
        
        embed.add_field(
            name="📊 Final Results",
            value=(
                f"🏆 **Winners:** {len(view.correct_users)} / {total_players}\n"
                f"🎯 **Accuracy:** {win_rate:.1f}%\n"
                f"👥 **Total Guesses:** {total_players}"
            ),
            inline=False
        )
        
        # Winners list
        if view.correct_users:
            winner_list = ", ".join([user.mention for user in view.correct_users[:15]])
            if len(view.correct_users) > 15:
                winner_list += f" *and {len(view.correct_users) - 15} more...*"
            embed.add_field(
                name="🏅 Winners",
                value=winner_list,
                inline=False
            )
        else:
            embed.add_field(
                name="🏅 Winners",
                value="*Nobody guessed correctly! Better luck next time!*",
                inline=False
            )
        
        # Flavor text and meta
        embed.set_footer(text="Use /stats game to track your guessing record! | Thanks for playing!")
        
        # Edit the original game message with results
        await game_message.edit(embed=embed, view=view)
        
        # Award XP to winners and record game stats
        if view.correct_users:
            multiplier, holiday_name = current_xp_multiplier()
            xp_amount = 10 * multiplier
            xp_awarded = []
            for user in view.correct_users:
                try:
                    increment_xp(user.id, xp_amount, channel.guild.id)
                    record_game_result(user.id, channel.guild.id, won=True, game_type="emoji")
                    xp_awarded.append(user.mention)
                except Exception as e:
                    logger.error(f"[🎮] Error awarding XP to {user}: {e}")
            
            if xp_awarded:
                bonus_label = f" ({holiday_name})" if holiday_name else ""
                await channel.send(
                    f"🎁 Bonus XP awarded! {', '.join(xp_awarded)} received **+{xp_amount} XP**!{bonus_label}",
                    delete_after=10
                )
        
        # Record losses for participants who didn't win
        if view.incorrect_users:
            for user in view.incorrect_users:
                try:
                    record_game_result(user.id, channel.guild.id, won=False, game_type="emoji")
                except Exception as e:
                    logger.error(f"[🎮] Error recording game loss for {user}: {e}")
        
        logger.info(f"[🎮] Game ended | Winners: {len(view.correct_users)} | Participants: {total_players}")


async def setup(bot: commands.Bot):
    """Add cog to bot."""
    await bot.add_cog(GamesManager(bot))
