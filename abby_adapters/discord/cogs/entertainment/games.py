"""
Modern Emoji Game with Button UI

Replaces reaction-based emoji game with modern button interactions.
Players click buttons instead of reacting to emojis.

Features:
- /game emoji - Start an emoji guessing game
- Button-based UI (no more reactions!)
- Auto-game scheduling
- XP rewards for winners
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
from abby_core.observability.logging import logging
from abby_adapters.discord.config import BotConfig
from abby_core.economy.xp import increment_xp
from datetime import datetime, time
import random
import asyncio

logger = logging.getLogger(__name__)

config = BotConfig()

class EmojiGameView(View):
    """View with emoji buttons for the game."""
    
    def __init__(self, winning_emoji: str, all_emojis: list, timeout_seconds: int = 30):
        super().__init__(timeout=timeout_seconds)
        self.winning_emoji = winning_emoji
        self.correct_users = []
        self.incorrect_users = []
        self.game_over = False
        
        # Create buttons for each emoji
        for emoji in all_emojis:
            button = Button(
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"emoji_{emoji}"
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
            
            # Check if correct
            if emoji == self.winning_emoji:
                self.correct_users.append(user)
                await interaction.response.send_message(
                    "✅ Correct! You chose the winning emoji!",
                    ephemeral=True
                )
            else:
                self.incorrect_users.append(user)
                await interaction.response.send_message(
                    "❌ Wrong choice! Better luck next time!",
                    ephemeral=True
                )
        
        return callback
    
    async def on_timeout(self):
        """Called when the view times out."""
        self.game_over = True
        # Disable all buttons
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True


class GameCommands(commands.GroupCog, name="game"):
    """Interactive game commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_game = False
        
        # Emoji choices
        self.custom_emojis = [
            "❤️", "🌟", "💥", "🍀", "🎯", "🎨", 
            "🎭", "🎪", "🎸", "🎺", "🎲", "🎯"
        ]
        
        # Use centralized config for channel and guild
        self.game_channel_id = config.channels.breeze_lounge
        self.guild_id = config.server_info.guild_id
        
        logger.info("[🎮] Modern Game Commands loaded")
        
        # Start auto-game task
        self.auto_game_task.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.auto_game_task.cancel()
    
    @app_commands.command(name="emoji", description="Start an emoji guessing game")
    async def emoji_game(self, interaction: discord.Interaction):
        """Start an emoji guessing game."""
        if self.active_game:
            await interaction.response.send_message(
                "⚠️ A game is already active! Wait for it to finish.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        await self._start_game(interaction.channel, interaction.user, manual=True)
    
    async def _start_game(self, channel: discord.TextChannel, starter: discord.User = None, manual: bool = False):
        """Internal method to start a game."""
        if self.active_game:
            return
        
        self.active_game = True
        
        # Select random emojis
        grid_size = 4
        selected_emojis = random.sample(self.custom_emojis, grid_size)
        winning_emoji = random.choice(selected_emojis)
        
        logger.info(f"[🎮] Game started | Emojis: {selected_emojis} | Winner: {winning_emoji}")
        
        # Create game embed
        embed = discord.Embed(
            title="🎮 EMOJI GUESSING GAME! 🎮",
            description=(
                "**Can you guess the correct emoji?**\n\n"
                "Click the button with the winning emoji to win!\n"
                f"{'🎁 Winners get **+10 XP**!' if not manual else ''}\n\n"
                "⏱️ You have **60 seconds** to choose!"
            ),
            color=discord.Color.blue()
        )
        
        # Create black squares to hide the emojis initially
        squares = "⬛" * grid_size
        embed.add_field(
            name="Hidden Emojis",
            value=squares,
            inline=False
        )
        
        if starter:
            embed.set_footer(text=f"Started by {starter.display_name}")
        else:
            embed.set_footer(text="Auto-started daily game")
        
        # Send game message
        if manual:
            await channel.send("🎮 **GAME TIME!** 🎮")
        else:
            await channel.send("🎮 **DAILY GAME!** 🎮\nQuick! Click the correct emoji!")
        
        # Create view with buttons
        view = EmojiGameView(winning_emoji, selected_emojis, timeout_seconds=60)
        game_message = await channel.send(embed=embed, view=view)
        
        # Countdown warnings
        await asyncio.sleep(30)
        if self.active_game:
            await channel.send("⏰ **30 seconds left!**", delete_after=5)
            await asyncio.sleep(25)
        
        if self.active_game:
            await channel.send("⏰ **5 seconds left!**", delete_after=5)
            await asyncio.sleep(5)
        
        # End game
        await self._end_game(channel, game_message, view, winning_emoji, give_xp=not manual)
    
    async def _end_game(self, channel: discord.TextChannel, game_message: discord.Message, 
                       view: EmojiGameView, winning_emoji: str, give_xp: bool = False):
        """End the game and announce results."""
        self.active_game = False
        view.game_over = True
        
        # Disable all buttons
        for child in view.children:
            if isinstance(child, Button):
                child.disabled = True
        
        await game_message.edit(view=view)
        
        # Create results embed
        embed = discord.Embed(
            title="🎮 GAME OVER! 🎮",
            description=f"The winning emoji was: **{winning_emoji}**",
            color=discord.Color.green()
        )
        
        # Winners
        if view.correct_users:
            winner_list = ", ".join([user.mention for user in view.correct_users])
            embed.add_field(
                name="🏆 Winners",
                value=winner_list,
                inline=False
            )
        else:
            embed.add_field(
                name="🏆 Winners",
                value="*Nobody guessed correctly!*",
                inline=False
            )
        
        # Participants
        if view.incorrect_users:
            participant_list = ", ".join([user.mention for user in view.incorrect_users[:10]])
            if len(view.incorrect_users) > 10:
                participant_list += f" *and {len(view.incorrect_users) - 10} more...*"
            embed.add_field(
                name="🎯 Participants",
                value=participant_list,
                inline=False
            )
        
        # Stats
        total_players = len(view.correct_users) + len(view.incorrect_users)
        embed.add_field(
            name="📊 Stats",
            value=f"**Total Players:** {total_players}\n**Winners:** {len(view.correct_users)}",
            inline=False
        )
        
        await channel.send(embed=embed)
        
        # Award XP to winners
        if give_xp and view.correct_users:
            xp_awarded = []
            for user in view.correct_users:
                try:
                    increment_xp(user.id, 10, channel.guild.id)
                    xp_awarded.append(user.mention)
                except Exception as e:
                    logger.error(f"[🎮] Error awarding XP to {user}: {e}")
            
            if xp_awarded:
                await channel.send(
                    f"🎁 Bonus XP awarded! {', '.join(xp_awarded)} received **+10 XP**!"
                )
        
        logger.info(f"[🎮] Game ended | Winners: {len(view.correct_users)} | Participants: {total_players}")
    
    @tasks.loop(time=time(hour=8, minute=0))  # Run daily at 8 AM
    async def auto_game_task(self):
        """Automatically start a game once per day."""
        logger.info("[🎮] Auto-game triggered")
        
        await asyncio.sleep(10)  # Wait 10 seconds after trigger
        
        channel = self.bot.get_channel(self.game_channel_id)
        if channel:
            await self._start_game(channel, starter=None, manual=False)
        else:
            logger.warning(f"[🎮] Could not find game channel: {self.game_channel_id}")
    
    @auto_game_task.before_loop
    async def before_auto_game(self):
        """Wait for bot to be ready before starting auto-game."""
        await self.bot.wait_until_ready()
        logger.info("[🎮] Auto-game task ready")


async def setup(bot: commands.Bot):
    """Add cog to bot."""
    await bot.add_cog(GameCommands(bot))
