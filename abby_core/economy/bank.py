import discord
from discord.ext import commands, tasks
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import datetime

# Import unified MongoDB client
sys.path.insert(0, str(Path(__file__).parent.parent / 'abby-core'))
from abby_core.database.mongodb import get_economy, update_balance, list_economies
from abby_core.observability.logging import setup_logging, logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)



class Bank(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        # No separate connection needed - unified client handles pooling
        self.bank_update.start()
        logger.info(f"[💲] Bank cog initialized with unified database")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f'[💲] Economy Initialized')

    @commands.group(name="bank", aliases=["economy"], invoke_without_command=True)
    async def bank_group(self, ctx):
        """Bank commands"""
        await ctx.send_help(ctx.command)
    
    @tasks.loop(minutes=10)
    async def bank_update(self):
        """Iterate tenant-scoped economies for periodic tasks (interest/rewards hooks)."""
        try:
            processed = 0
            for econ in list_economies():
                guild_id = econ.get("guild_id")
                user_id = econ.get("user_id")
                # Placeholder for future interest/reward logic; no mutation yet
                processed += 1
            logger.debug(f"[💲] bank_update scanned {processed} economy docs")
        except Exception as e:
            logger.error(f"[💲] bank_update failed: {e}")
            
    async def cooldown_check(self, user_id):
        user_data = get_economy(user_id)
        if user_data:
            last_daily = user_data.get("last_daily")
            if last_daily:
                if datetime.datetime.utcnow() - last_daily < datetime.timedelta(hours=24):
                    return False
            return True
        return False


    def amt_check(self, amount):    
        if amount == "":
            return "Please enter an amount to withdraw."
        if not amount.isdigit():
            return "Please enter a valid amount to withdraw."
        if int(amount) <= 0:
            return "Please enter a valid amount to withdraw."
            
    @bank_group.command()
    async def balance(self,ctx):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        if user_data:
            wallet_balance = user_data.get("wallet_balance", user_data.get("wallet", 0))
            bank_balance = user_data.get("bank_balance", user_data.get("bank", 0))
            await ctx.send(f"Wallet Balance: {wallet_balance}, Bank Balance: {bank_balance}")
        else:
            await ctx.send("User profile not found.")

    @bank_group.command()
    async def deposit(self,ctx, amount):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        if user_data:
            amount_int = int(amount)
            wallet_balance = user_data.get("wallet_balance", user_data.get("wallet", 0))
            if wallet_balance < amount_int:
                await ctx.send("Insufficient funds in your wallet.")
                return
            # Use unified client helper to update balances atomically
            update_balance(user_id, wallet_delta=-amount_int, bank_delta=amount_int, guild_id=guild_id)
            await ctx.send(f"Deposited {amount} into your bank account.")
        else:
            await ctx.send("User profile not found.")

    @bank_group.command()
    async def withdraw(self,ctx, amount):
        if self.amt_check(amount):
            await ctx.send(self.amt_check(amount))
            return
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        if user_data:
            amount_int = int(amount)
            bank_balance = user_data.get("bank_balance", user_data.get("bank", 0))
            if bank_balance >= amount_int:
                # Use unified client helper to update balances atomically
                update_balance(user_id, wallet_delta=amount_int, bank_delta=-amount_int, guild_id=guild_id)
                await ctx.send(f"Withdrew {amount} from your bank account.")
            else:
                await ctx.send("Insufficient funds in your bank account.")

    @bank_group.command()
    async def list_service(self,ctx, title, description, price):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else None
        user_data = get_economy(user_id, guild_id)
        price_int = int(price)
        if user_data and user_data.get("wallet_balance", 0) >= price_int:
            # Deduct from wallet balance when listing a service
            update_balance(user_id, wallet_delta=-price_int, guild_id=guild_id)

            # Store the service listing logic here

            await ctx.send("Service listed successfully!")
        else:
            await ctx.send("You don't have enough funds in your wallet.")

    # Other commands for purchasing, transactions, interest calculation, etc.


# async def setup(bot):
#     await bot.add_cog(Bank(bot))
