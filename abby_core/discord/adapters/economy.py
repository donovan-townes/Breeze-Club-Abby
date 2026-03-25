"""Discord Adapter for Economy Features

This module implements Discord-specific bot commands and scheduling for the economy subsystem.

Architecture:
    Platform-agnostic EconomyService (abby_core.services.economy_service)
                           ↓
    Discord Adapter (this module) - Cogs, background tasks, Discord UI

Responsibilities:
    - Bank cog: /bank, /balance, /deposit, /withdraw commands
    - Background interest calculation: Platform scheduler runs economy service logic
    - Economy display: Format balance info for Discord embeds
    - User interaction: Parse Discord commands and convert to service calls

This module bridges Discord bot to the platform-agnostic EconomyService.
All business logic lives in the service; this module handles Discord I/O only.
"""

import discord
from discord.ext import commands
import datetime
from typing import Optional

from abby_core.database.mongodb import get_economy
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

class BankCog(commands.Cog):
    """Discord bank commands and background economy tasks.
    
    This cog is Discord-specific: it handles commands, events, and background tasks
    using discord.py. Business logic is delegated to EconomyService.
    """

    def __init__(self, bot: commands.Bot):
        """Initialize the bank cog.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        logger.info(f"[💲] Bank cog initialized")

    async def cog_unload(self):
        """Clean up background tasks when cog is unloaded."""
        logger.info("[💲] Bank cog unloaded")

    @commands.Cog.listener()
    async def on_ready(self):
        """Log when economy is ready."""
        logger.info(f'[💲] Economy System Ready')

    @commands.group(name="bank", aliases=["economy"], invoke_without_command=True)
    async def bank_group(self, ctx: commands.Context):
        """Bank commands (balance, deposit, withdraw, etc.)."""
        await ctx.send_help(ctx.command)

    # NOTE:
    # Interest accrual now runs via platform SchedulerService (BankInterestJobHandler).

    # ════════════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════════════════════════

    async def cooldown_check(self, user_id: str) -> bool:
        """Check if user has completed a daily action.
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if cooldown has passed (action allowed), False if still on cooldown
        """
        user_data = get_economy(user_id)
        if user_data:
            last_daily = user_data.get("last_daily")
            if last_daily:
                if datetime.datetime.utcnow() - last_daily < datetime.timedelta(hours=24):
                    return False
            return True
        return False

    def _validate_amount(self, amount: str) -> Optional[str]:
        """Validate amount string is a valid positive integer.
        
        Args:
            amount: Amount string to validate
            
        Returns:
            None if valid, error message string if invalid
        """
        if amount == "":
            return "Please enter an amount."
        if not amount.isdigit():
            return "Please enter a valid number."
        if int(amount) <= 0:
            return "Amount must be greater than zero."
        return None

    # ════════════════════════════════════════════════════════════════════════════════
    # DISCORD COMMANDS
    # ════════════════════════════════════════════════════════════════════════════════

    @bank_group.command(name="balance")
    async def balance_command(self, ctx: commands.Context):
        """Show your current wallet and bank balance.
        
        Usage:
            /bank balance
        """
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        
        if user_data:
            wallet_balance = user_data.get("wallet_balance") or user_data.get("wallet", 0)
            bank_balance = user_data.get("bank_balance") or user_data.get("bank", 0)
            
            embed = discord.Embed(
                title="💰 Account Balance",
                color=discord.Color.gold()
            )
            embed.add_field(name="Wallet", value=f"{wallet_balance} BC", inline=True)
            embed.add_field(name="Bank", value=f"{bank_balance} BC", inline=True)
            embed.add_field(name="Total", value=f"{wallet_balance + bank_balance} BC", inline=False)
            embed.set_footer(text="BC = Baddies Credits")
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ User profile not found. Please initialize your account first.")

    @bank_group.command(name="deposit")
    async def deposit_command(self, ctx: commands.Context, amount: str):
        """Deposit BC from your wallet to your bank.
        
        Usage:
            /bank deposit 100
        """
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        
        if not user_data:
            await ctx.send("❌ User profile not found.")
            return
        
        # Validate amount
        validation_error = self._validate_amount(amount)
        if validation_error:
            await ctx.send(f"❌ {validation_error}")
            return
        
        amount_int = int(amount)
        wallet_balance = user_data.get("wallet_balance") or user_data.get("wallet", 0)
        
        if wallet_balance < amount_int:
            await ctx.send(f"❌ Insufficient funds. You have {wallet_balance} BC in your wallet.")
            return
        
        # Update balances atomically
        update_balance(user_id, wallet_delta=-amount_int, bank_delta=amount_int, guild_id=guild_id)
        new_balance = get_economy(user_id, guild_id)
        
        embed = discord.Embed(
            title="✅ Deposit Successful",
            description=f"Deposited {amount_int} BC to your bank",
            color=discord.Color.green()
        )
        embed.add_field(name="New Wallet", value=f"{new_balance.get('wallet_balance') or 0} BC")
        embed.add_field(name="New Bank", value=f"{new_balance.get('bank_balance') or 0} BC")
        await ctx.send(embed=embed)

    @bank_group.command(name="withdraw")
    async def withdraw_command(self, ctx: commands.Context, amount: str):
        """Withdraw BC from your bank to your wallet.
        
        Usage:
            /bank withdraw 50
        """
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        
        if not user_data:
            await ctx.send("❌ User profile not found.")
            return
        
        # Validate amount
        validation_error = self._validate_amount(amount)
        if validation_error:
            await ctx.send(f"❌ {validation_error}")
            return
        
        amount_int = int(amount)
        bank_balance = user_data.get("bank_balance") or user_data.get("bank", 0)
        
        if bank_balance < amount_int:
            await ctx.send(f"❌ Insufficient funds. You have {bank_balance} BC in your bank.")
            return
        
        # Update balances atomically
        update_balance(user_id, wallet_delta=amount_int, bank_delta=-amount_int, guild_id=guild_id)
        new_balance = get_economy(user_id, guild_id)
        
        embed = discord.Embed(
            title="✅ Withdrawal Successful",
            description=f"Withdrew {amount_int} BC from your bank",
            color=discord.Color.green()
        )
        embed.add_field(name="New Wallet", value=f"{new_balance.get('wallet_balance') or 0} BC")
        embed.add_field(name="New Bank", value=f"{new_balance.get('bank_balance') or 0} BC")
        await ctx.send(embed=embed)

    @bank_group.command(name="list_service")
    async def list_service_command(self, ctx: commands.Context, title: str, description: str, price: str):
        """List a service for other users to purchase.
        
        Usage:
            /bank list_service "Custom Art" "Commission a drawing" 500
        """
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        
        if not user_data:
            await ctx.send("❌ User profile not found.")
            return
        
        # Validate price
        validation_error = self._validate_amount(price)
        if validation_error:
            await ctx.send(f"❌ {validation_error}")
            return
        
        price_int = int(price)
        wallet_balance = user_data.get("wallet_balance", 0)
        
        if wallet_balance < price_int:
            await ctx.send(f"❌ Insufficient funds. Service listing costs {price_int} BC.")
            return
        
        # Deduct from wallet balance when listing a service
        update_balance(user_id, wallet_delta=-price_int, guild_id=guild_id)
        
        # TODO: Store the service listing in database
        
        embed = discord.Embed(
            title="✅ Service Listed",
            description=title,
            color=discord.Color.green()
        )
        embed.add_field(name="Description", value=description)
        embed.add_field(name="Price", value=f"{price_int} BC")
        embed.set_footer(text=f"Listed by {ctx.author}")
        await ctx.send(embed=embed)


# ════════════════════════════════════════════════════════════════════════════════
# COG SETUP
# ════════════════════════════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    """Load the bank cog into the bot.
    
    This function is called by discord.py bot.load_extension().
    """
    await bot.add_cog(BankCog(bot))
    logger.info("[💲] Bank cog loaded")
