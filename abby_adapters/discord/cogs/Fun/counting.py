from discord.ext import commands
import asyncio
from abby_core.observability.logging import setup_logging, logging
import re
from discord import app_commands
import discord
import random

setup_logging
logger = logging.getLogger(__name__)


class CounterGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="counting")
    async def counting(self, interaction: discord.Interaction):
        """Play a game of counting"""
        view = Counter()
        await interaction.response.send_message(f"Click a number past 10 to win!", view=view)
        await view.wait()
        if view.winner:
            await interaction.edit_original_response(content=f"Game over! Winner is {view.winner.mention}", view=None)
        else:
            await interaction.edit_original_response(content=f"Game over! No winner.", view=None)


class Counter(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.amount = None
        self.winner = None
        self.timeout = 60

    @discord.ui.button(label='0', style=discord.ButtonStyle.red)
    async def count(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Pick a number between 0 and 99 and round it to the nearest 10
        number = random.randint(0, 9) if button.label else 0
        if number + 1 >= 10:
            button.style = discord.ButtonStyle.green
            button.disabled = True
            self.value = True
            button.label = str(number + 1)
            self.winner = interaction.user             
            self.stop()
            return
        button.label = str(number)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='0', style=discord.ButtonStyle.blurple)
    async def count2(self, interaction: discord.Interaction, button: discord.ui.Button):
        # number = int(button.label) if button.label else 0
        number = random.randint(0, 9) if button.label else 0
        if number + 1 >= 10:
            button.style = discord.ButtonStyle.green
            button.disabled = True
            self.value = True
            button.label = str(number + 1)
            self.winner = interaction.user             
            self.stop()
            return
        button.label = str(number + 1)
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label='0', style=discord.ButtonStyle.green)
    async def count3(self, interaction: discord.Interaction, button: discord.ui.Button):
        # number = int(button.label) if button.label else 0
        number = random.randint(0, 9) if button.label else 0
        if number + 1 >= 10:
            button.style = discord.ButtonStyle.green
            button.disabled = True
            self.value = True
            button.label = str(number + 1)
            self.winner = interaction.user             
            self.stop()
            return
        button.label = str(number + 1)
        await interaction.response.edit_message(view=self)

    async def on_timeout(self, interaction: discord.Interaction):
        self.winner = None
        self.stop()

async def setup(bot):
    await bot.add_cog(CounterGame(bot))
