import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from utils.mongo_db import *
import datetime

load_dotenv()



class Bank(commands.Cog):    
    def __init__(self, bot):
        self.bot = bot
        self.bank_collection, self.central_bank_collection = self.econ_init()
        self.bank_update.start()

        
    # Initialize MongoDB connection
    def econ_init(self):
        client = connect_to_mongodb()
        db = client["Abby_Economy"]
        bank_collection = db["Abby_Bank"]
        central_bank_collection = db["Central_Bank"]
        return bank_collection, central_bank_collection

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'[💲] Economy Initalized')

    @commands.group(name="bank", aliases=["economy"], invoke_without_command=True)
    async def bank_group(self, ctx):
        """Bank commands"""
        await ctx.send_help(ctx.command)
    
    @tasks.loop(minutes=10)
    async def bank_update(self):
        for user_data in self.bank_collection.find():
            user_id = user_data["_id"]
            user_data["wallet_balance"] += 100
            self.bank_collection.update_one({"_id": user_id}, {"$set": user_data})
            await self.bot.get_user(user_id).send("You have received 100 coins for being active in the server.")
            
    async def cooldown_check(self, user_id):
        user_data = self.bank_collection.find_one({"_id": user_id})
        if user_data:
            last_daily = user_data["last_daily"]
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
        user_id = ctx.author.id
        user_data = self.bank_collection.find_one({"_id": user_id})
        if user_data:
            wallet_balance = user_data["wallet_balance"]
            bank_balance = user_data["bank_balance"]
            await ctx.send(f"Wallet Balance: {wallet_balance}, Bank Balance: {bank_balance}")
        else:
            await ctx.send("User profile not found.")

    @bank_group.command()
    async def deposit(self,ctx, amount):
        user_id = ctx.author.id
        user_data = self.bank_collection.find_one({"_id": user_id})
        if user_data:
            user_data["wallet_balance"] -= int(amount)
            user_data["bank_balance"] += int(amount)
            self.bank_collection.update_one({"_id": user_id}, {"$set": user_data})
            await ctx.send(f"Deposited {amount} into your bank account.")
        else:
            await ctx.send("User profile not found.")

    @bank_group.command()
    async def withdraw(self,ctx, amount):
        if self.amt_check(amount):
            await ctx.send(self.amt_check(amount))
            return
        user_id = ctx.author.id
        user_data = self.bank_collection.find_one({"_id": user_id})
        if user_data:
            if user_data["bank_balance"] >= int(amount):
                user_data["bank_balance"] -= int(amount)
                user_data["wallet_balance"] += int(amount)
                self.bank_collection.update_one({"_id": user_id}, {"$set": user_data})
                await ctx.send(f"Withdrew {amount} from your bank account.")
            else:
                await ctx.send("Insufficient funds in your bank account.")

    @bank_group.command()
    async def list_service(self,ctx, title, description, price):
        user_id = ctx.author.id
        user_data = self.bank_collection.find_one({"_id": user_id})
        if user_data and user_data["wallet_balance"] >= int(price):
            # Deduct from wallet balance when listing a service
            user_data["wallet_balance"] -= int(price)
            self.bank_collection.update_one({"_id": user_id}, {"$set": user_data})

            # Store the service listing logic here

            await ctx.send("Service listed successfully!")
        else:
            await ctx.send("You don't have enough funds in your wallet.")

    # Other commands for purchasing, transactions, interest calculation, etc.


# async def setup(bot):
#     await bot.add_cog(Bank(bot))
