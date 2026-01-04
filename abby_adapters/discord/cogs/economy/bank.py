"""
Modern slash-command bank interface.
Provides /bank group with balance, deposit, withdraw, and history stubs using guild-scoped economy data.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from abby_core.database.mongodb import get_economy, update_balance, log_transaction, get_transaction_history
from abby_core.observability.logging import logging
from datetime import datetime

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
    embed.add_field(name="Wallet", value=_format_currency(wallet), inline=True)
    embed.add_field(name="Bank", value=_format_currency(bank), inline=True)
    embed.add_field(name="Total", value=_format_currency(total), inline=True)
    embed.add_field(name="Composition", value=_progress_bar(bank, total), inline=False)
    return embed


def _validate_amount(amount: int | None) -> str | None:
    if amount is None:
        return "Enter an amount."
    if amount <= 0:
        return "Enter a positive amount."
    return None


def _validate_non_negative(value: int | None) -> str | None:
    if value is None:
        return "Enter a value."
    if value < 0:
        return "Enter a non-negative value."
    return None


def _format_currency(amount: int) -> str:
    """Format coins with dollar conversion (100 Breeze Coins = 1 Leaf Dollar)."""
    dollars = amount / 100
    return f"{amount:,} BC (${dollars:.2f})"


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
        new_bank = econ.get("bank_balance", econ.get("bank", 0)) + amount
        log_transaction(user_id, guild_id, "deposit", amount, new_bank, f"Deposited {amount} BC")
        embed = _balance_embed(interaction.user, wallet - amount, new_bank)
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
        new_wallet = econ.get("wallet_balance", econ.get("wallet", 0)) + amount
        log_transaction(user_id, guild_id, "withdraw", amount, bank_balance - amount, f"Withdrew {amount} BC")
        embed = _balance_embed(interaction.user, new_wallet, bank_balance - amount)
        await interaction.response.send_message("Withdrawal successful.", embed=embed, ephemeral=True)

    @app_commands.command(name="history", description="View recent bank transactions")
    @app_commands.describe(limit="Number of recent transactions to show (max 25)")
    async def history(self, interaction: discord.Interaction, limit: int = 10):
        if limit < 1 or limit > 25:
            limit = 10
        
        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        user_id = str(interaction.user.id)
        
        transactions = get_transaction_history(user_id, guild_id, limit)
        if not transactions:
            await interaction.response.send_message("No transaction history found.", ephemeral=True)
            return
        
        embed = discord.Embed(title="Transaction History", color=discord.Color.gold())
        embed.set_author(name=interaction.user.display_name, icon_url=getattr(interaction.user.display_avatar, "url", None))
        
        history_text = ""
        for txn in transactions:
            txn_type = txn.get("type", "unknown")
            amount = txn.get("amount", 0)
            desc = txn.get("description", "")
            timestamp = txn.get("timestamp")
            time_str = timestamp.strftime("%Y-%m-%d %H:%M") if timestamp else "unknown"
            
            emoji = "💰" if txn_type == "deposit" else "💸" if txn_type == "withdraw" else "🔄"
            history_text += f"{emoji} **{txn_type.title()}** - {_format_currency(amount)}\n"
            history_text += f"   _{desc}_ • {time_str}\n\n"
        
        embed.description = history_text or "No transactions."
        embed.set_footer(text=f"Showing last {len(transactions)} transaction(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="init", description="Admin: create or reset a bank profile")
    @app_commands.describe(
        user="User to initialize/reset (defaults to yourself)",
        wallet="Starting wallet amount (>=0)",
        bank="Starting bank amount (>=0)",
        reset="Reset even if a profile already exists",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def init_profile(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        wallet: int = 0,
        bank: int = 0,
        reset: bool = False,
    ):
        err_wallet = _validate_non_negative(wallet)
        err_bank = _validate_non_negative(bank)
        if err_wallet or err_bank:
            await interaction.response.send_message(err_wallet or err_bank, ephemeral=True)
            return

        target = user or interaction.user
        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        user_id = str(target.id)

        existing = get_economy(user_id, guild_id)
        if existing and not reset:
            await interaction.response.send_message(
                "Profile already exists. Use reset=true to overwrite balances.",
                ephemeral=True,
            )
            return

        current_wallet = existing.get("wallet_balance", existing.get("wallet", 0)) if existing else 0
        current_bank = existing.get("bank_balance", existing.get("bank", 0)) if existing else 0

        wallet_delta = wallet - current_wallet
        bank_delta = bank - current_bank

        update_balance(user_id, wallet_delta=wallet_delta, bank_delta=bank_delta, guild_id=guild_id)
        log_transaction(user_id, guild_id, "init", wallet + bank, bank, f"Profile initialized (wallet={wallet}, bank={bank})")

        embed = _balance_embed(target, wallet, bank)
        await interaction.response.send_message(
            f"Profile initialized for {target.mention} (reset={reset}).",
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(name="pay", description="Send Breeze Coins to another user")
    @app_commands.describe(
        recipient="User to send coins to",
        amount="Amount to send (from wallet)"
    )
    async def pay(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        err = _validate_amount(amount)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        
        if recipient.bot:
            await interaction.response.send_message("You cannot send coins to bots.", ephemeral=True)
            return
        
        if recipient.id == interaction.user.id:
            await interaction.response.send_message("You cannot send coins to yourself.", ephemeral=True)
            return
        
        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        sender_id = str(interaction.user.id)
        recipient_id = str(recipient.id)
        
        # Get sender profile
        sender_econ = get_economy(sender_id, guild_id)
        if not sender_econ:
            await interaction.response.send_message("Your profile not found. Initialize with `/bank init` first.", ephemeral=True)
            return
        
        sender_wallet = sender_econ.get("wallet_balance", sender_econ.get("wallet", 0))
        if sender_wallet < amount:
            await interaction.response.send_message(
                f"Insufficient funds. You have {_format_currency(sender_wallet)}.",
                ephemeral=True
            )
            return
        
        # Get or create recipient profile (upsert with 0 balance)
        recipient_econ = get_economy(recipient_id, guild_id)
        if not recipient_econ:
            # Create profile with 0 balance via upsert
            update_balance(recipient_id, wallet_delta=0, bank_delta=0, guild_id=guild_id)
            recipient_econ = get_economy(recipient_id, guild_id)
        
        recipient_wallet = recipient_econ.get("wallet_balance", recipient_econ.get("wallet", 0))
        
        # Execute transfer atomically
        update_balance(sender_id, wallet_delta=-amount, guild_id=guild_id)
        update_balance(recipient_id, wallet_delta=amount, guild_id=guild_id)
        
        # Log transactions for both parties
        new_sender_wallet = sender_wallet - amount
        new_recipient_wallet = recipient_wallet + amount
        log_transaction(sender_id, guild_id, "transfer", amount, new_sender_wallet, f"Sent {amount} BC to {recipient.display_name}")
        log_transaction(recipient_id, guild_id, "transfer", amount, new_recipient_wallet, f"Received {amount} BC from {interaction.user.display_name}")
        
        # Send confirmation
        embed = discord.Embed(title="Transfer Complete", color=discord.Color.green())
        embed.add_field(name="From", value=interaction.user.mention, inline=True)
        embed.add_field(name="To", value=recipient.mention, inline=True)
        embed.add_field(name="Amount", value=_format_currency(amount), inline=False)
        embed.add_field(name="Your New Balance", value=_format_currency(new_sender_wallet), inline=False)
        embed.set_footer(text="Transfer logged in your transaction history")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(BankCommands(bot))
