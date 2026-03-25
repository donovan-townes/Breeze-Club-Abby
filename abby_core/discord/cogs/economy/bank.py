"""
/bank - Single entry point with button-driven navigation for balance, deposit, withdraw, history.
/tip - Separate atomic command for quick tipping.

Follows the same philosophy as /stats: slash commands are entry points, not control surfaces.

All economy operations delegated to EconomyService (platform-agnostic).
This cog handles Discord UI only - no business logic.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from abby_core.services.economy_service import get_economy_service
from abby_core.database.mongodb import get_transaction_history
from tdos_intelligence.observability import logging
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


def _format_currency(amount: int) -> str:
    """Format coins with dollar conversion (100 Breeze Coins = 1 Leaf Dollar)."""
    dollars = amount / 100
    return f"{amount:,} BC (${dollars:.2f})"


class DepositModal(discord.ui.Modal, title="Deposit to Bank"):
    """Modal for depositing coins into bank."""
    amount_input = discord.ui.TextInput(
        label="Amount to Deposit",
        placeholder="Enter amount (e.g., 100)",
        min_length=1,
        max_length=10,
        required=True
    )

    def __init__(self, cog: "BankCommands"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("Invalid amount. Enter a number.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        guild_id = interaction.guild_id if interaction.guild_id else None
        user_id = interaction.user.id
        economy_service = get_economy_service()
        
        success, error = economy_service.deposit(user_id, amount, guild_id)
        
        if not success:
            await interaction.response.send_message(f"❌ Deposit failed: {error}", ephemeral=True)
            return

        embed = await self.cog.build_overview_embed(interaction)
        view = BankView(self.cog, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)


class WithdrawModal(discord.ui.Modal, title="Withdraw from Bank"):
    """Modal for withdrawing coins from bank."""
    amount_input = discord.ui.TextInput(
        label="Amount to Withdraw",
        placeholder="Enter amount (e.g., 100)",
        min_length=1,
        max_length=10,
        required=True
    )

    def __init__(self, cog: "BankCommands"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("Invalid amount. Enter a number.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        guild_id = interaction.guild_id if interaction.guild_id else None
        user_id = interaction.user.id
        economy_service = get_economy_service()
        
        success, error = economy_service.withdraw(user_id, amount, guild_id)
        
        if not success:
            await interaction.response.send_message(f"❌ Withdraw failed: {error}", ephemeral=True)
            return

        embed = await self.cog.build_overview_embed(interaction)
        view = BankView(self.cog, interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=view)


class BankView(discord.ui.View):
    """Button-driven navigation for /bank screens."""

    def __init__(self, cog: "BankCommands", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id

    async def _update_view(self, interaction: discord.Interaction, tab: str):
        if tab == "overview":
            embed = await self.cog.build_overview_embed(interaction)
        elif tab == "history":
            embed = await self.cog.build_history_embed(interaction)
        else:
            embed = await self.cog.build_overview_embed(interaction)
        
        new_view = BankView(self.cog, self.owner_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="💰", row=0)
    async def button_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_view(interaction, "overview")

    @discord.ui.button(label="Deposit", style=discord.ButtonStyle.success, emoji="⬇️", row=0)
    async def button_deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DepositModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Withdraw", style=discord.ButtonStyle.danger, emoji="⬆️", row=0)
    async def button_withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WithdrawModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="History", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def button_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_view(interaction, "history")


class BankCommands(commands.Cog):
    """Bank overview with button-driven actions: deposit, withdraw, history."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.debug("[💰] Bank commands loaded")

    @app_commands.command(name="bank", description="View your bank overview (wallet + bank + actions)")
    async def bank(self, interaction: discord.Interaction):
        """Single entry point with button navigation."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command only works in servers.", ephemeral=True)
            return

        embed = await self.build_overview_embed(interaction)
        view = BankView(self, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def build_overview_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Build the bank overview embed."""
        guild_id = interaction.guild_id if interaction.guild_id else None
        user_id = interaction.user.id
        economy_service = get_economy_service()
        
        stats = economy_service.get_user_stats(user_id, guild_id)
        balance = stats["balance"]
        wallet = balance["wallet"]
        bank = balance["bank"]
        total = balance["total"]
        tip_remaining = stats["tip_budget_remaining"]

        embed = discord.Embed(title="💰 Your Bank", color=discord.Color.blue())
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        embed.add_field(name="Wallet", value=_format_currency(wallet), inline=True)
        embed.add_field(name="Bank", value=_format_currency(bank), inline=True)
        embed.add_field(name="Total", value=_format_currency(total), inline=True)
        embed.add_field(name="Composition", value=_progress_bar(bank, total), inline=False)
        embed.add_field(
            name="Daily Tip Budget",
            value=f"{_format_currency(tip_remaining)} remaining",
            inline=False
        )
        
        embed.set_footer(text="Use buttons below to manage your finances")
        return embed

    async def build_history_embed(self, interaction: discord.Interaction, limit: int = 10) -> discord.Embed:
        """Build the transaction history embed."""
        if limit < 1 or limit > 25:
            limit = 10
        
        guild_id = interaction.guild_id if interaction.guild_id else None
        user_id = interaction.user.id
        
        transactions = get_transaction_history(user_id, guild_id, limit)
        
        embed = discord.Embed(title="📜 Transaction History", color=discord.Color.gold())
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=getattr(interaction.user.display_avatar, "url", None)
        )
        
        if not transactions:
            embed.description = "No transaction history found."
            return embed
        
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
        return embed

    @app_commands.command(name="tip", description="Tip another user with Breeze Coins (daily budget applies)")
    @app_commands.describe(
        recipient="The user to tip",
        amount="Amount of Breeze Coins to tip",
        reason="Optional reason for the tip (shown publicly)",
        public="Whether to show a public thank-you message (default: True)"
    )
    async def tip(
        self, 
        interaction: discord.Interaction, 
        recipient: discord.Member, 
        amount: int,
        reason: Optional[str] = None,
        public: bool = True
    ):
        """Tip another user with Breeze Coins from your wallet (daily budget applies)."""
        # Validation: positive amount
        if amount <= 0:
            await interaction.response.send_message("Tip amount must be positive.", ephemeral=True)
            return
        
        # Validation: recipient cannot be a bot
        if recipient.bot:
            await interaction.response.send_message("You cannot tip bots.", ephemeral=True)
            return
        
        # Validation: cannot tip yourself
        if recipient.id == interaction.user.id:
            await interaction.response.send_message("You cannot tip yourself.", ephemeral=True)
            return
        
        guild_id = interaction.guild_id if interaction.guild_id else None
        sender_id = interaction.user.id
        recipient_id = recipient.id
        
        economy_service = get_economy_service()
        success, error = economy_service.tip(sender_id, recipient_id, amount, guild_id)
        
        if not success:
            await interaction.response.send_message(
                f"⚠️ {error}",
                ephemeral=True
            )
            return
        
        # Get updated stats for confirmation
        sender_stats = economy_service.get_user_stats(sender_id, guild_id)
        
        # Send confirmation
        embed = discord.Embed(title="💸 Tip Sent!", color=discord.Color.gold())
        embed.add_field(name="From", value=interaction.user.mention, inline=True)
        embed.add_field(name="To", value=recipient.mention, inline=True)
        embed.add_field(name="Amount", value=_format_currency(amount), inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Your New Wallet", value=_format_currency(sender_stats["balance"]["wallet"]), inline=True)
        embed.add_field(name="Tip Budget Remaining", value=_format_currency(sender_stats["tip_budget_remaining"]), inline=True)
        embed.set_footer(text="Thank you for spreading kindness! ✨")
        
        await interaction.response.send_message(embed=embed, ephemeral=not public)


async def setup(bot: commands.Bot):
    await bot.add_cog(BankCommands(bot))
