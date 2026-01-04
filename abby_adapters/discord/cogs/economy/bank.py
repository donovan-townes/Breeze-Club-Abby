"""
Modern slash-command bank interface.
Provides /bank group with balance, deposit, withdraw, and history stubs using guild-scoped economy data.
"""

import discord
from discord import app_commands
from discord.ext import commands

from abby_core.database.mongodb import get_economy, update_balance
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


def _progress_bar(current: int, total: int, length: int = 20) -> str:
    """ASCII progress bar for wallet+bank composition."""
    if total <= 0:
        return "[....................]"
    ratio = max(0.0, min(1.0, current / total))
    filled = int(ratio * length)
    empty = length - filled
    return f"[{'#' * filled}{'.' * empty}] {int(ratio * 100)}%"


def _balance_embed(user: discord.abc.User, wallet: int, bank: int) -> discord.Embed:
    total = wallet + bank
    embed = discord.Embed(title="Bank Balance", color=discord.Color.blue())
    embed.set_author(name=user.display_name, icon_url=getattr(user.display_avatar, "url", None))
    embed.add_field(name="Wallet", value=f"{wallet:,}", inline=True)
    embed.add_field(name="Bank", value=f"{bank:,}", inline=True)
    embed.add_field(name="Total", value=f"{total:,}", inline=True)
    embed.add_field(name="Composition", value=_progress_bar(bank, total), inline=False)
    return embed


def _validate_amount(amount: int | None) -> str | None:
    if amount is None:
        return "Enter an amount."
    if amount <= 0:
        return "Enter a positive amount."
    return None


class BankCommands(commands.GroupCog, name="bank"):
    """Slash commands for balance, deposit, withdraw, and history."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("[bank] Slash commands loaded")

    @app_commands.command(name="balance", description="View your wallet and bank balances")
    async def balance(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        user_id = str(interaction.user.id)
        econ = get_economy(user_id, guild_id)
        if not econ:
            await interaction.response.send_message("No economy profile found for you yet.", ephemeral=True)
            return

        wallet = econ.get("wallet_balance", econ.get("wallet", 0))
        bank = econ.get("bank_balance", econ.get("bank", 0))
        embed = _balance_embed(interaction.user, wallet, bank)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="deposit", description="Move coins from wallet into bank")
    @app_commands.describe(amount="Amount to deposit")
    async def deposit(self, interaction: discord.Interaction, amount: int):
        err = _validate_amount(amount)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        user_id = str(interaction.user.id)
        econ = get_economy(user_id, guild_id)
        if not econ:
            await interaction.response.send_message("No economy profile found for you yet.", ephemeral=True)
            return

        wallet = econ.get("wallet_balance", econ.get("wallet", 0))
        if wallet < amount:
            await interaction.response.send_message("Insufficient funds in your wallet.", ephemeral=True)
            return

        update_balance(user_id, wallet_delta=-amount, bank_delta=amount, guild_id=guild_id)
        embed = _balance_embed(interaction.user, wallet - amount, econ.get("bank_balance", econ.get("bank", 0)) + amount)
        await interaction.response.send_message("Deposit successful.", embed=embed, ephemeral=True)

    @app_commands.command(name="withdraw", description="Move coins from bank into wallet")
    @app_commands.describe(amount="Amount to withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        err = _validate_amount(amount)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        user_id = str(interaction.user.id)
        econ = get_economy(user_id, guild_id)
        if not econ:
            await interaction.response.send_message("No economy profile found for you yet.", ephemeral=True)
            return

        bank_balance = econ.get("bank_balance", econ.get("bank", 0))
        if bank_balance < amount:
            await interaction.response.send_message("Insufficient funds in your bank account.", ephemeral=True)
            return

        update_balance(user_id, wallet_delta=amount, bank_delta=-amount, guild_id=guild_id)
        embed = _balance_embed(interaction.user, econ.get("wallet_balance", econ.get("wallet", 0)) + amount, bank_balance - amount)
        await interaction.response.send_message("Withdrawal successful.", embed=embed, ephemeral=True)

    @app_commands.command(name="history", description="View recent bank transactions (coming soon)")
    async def history(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Transaction history will be available in the next update.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BankCommands(bot))
