import discord
from discord import app_commands
from discord.ext import commands


class BankingCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    group = app_commands.Group(name="bank", description="Access the bank commands")

    @group.command(name="balance")
    async def check_balance(self, interaction: discord.Interaction) -> None:
        """ Check your balance"""
        await interaction.response.send_message("Your balance is 0 Breeze Coins!", ephemeral=True)

    # we use the declared group to make a command.
    @group.command(name="withdraw")
    async def withdraw(self, interaction: discord.Interaction) -> None:
        """ Withdraw money from the bank! """
        await interaction.response.send_message("You withdraw $100 Leaf Dollars!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BankingCommand(bot))
