# Slash Commands: ping, pong
import discord
from discord import app_commands
from discord.ext import commands
BREEZE_CLUB = 547471286801268777

class MyCog(commands.Cog):
  def __init__(self, bot: commands.Bot) -> None:
    self.bot = bot
    
  @app_commands.command(name="ping")
  async def my_command(self, interaction: discord.Interaction) -> None:
    """ Ping the server! """
    await interaction.response.send_message("Hello from ping!", ephemeral=True)

  @app_commands.command(name="pong")
  @app_commands.guilds(discord.Object(id=BREEZE_CLUB))
  async def my_private_command(self, interaction: discord.Interaction) -> None:
    """ /command-2 """
    await interaction.response.send_message("Hello from pong!", ephemeral=True)

# async def setup(bot: commands.Bot) -> None:
#   await bot.add_cog(MyCog(bot))