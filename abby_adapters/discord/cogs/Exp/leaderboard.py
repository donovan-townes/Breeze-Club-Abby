from pymongo import MongoClient
import discord
from discord.ext import commands, tasks
from abby_core.database.mongodb import connect_to_mongodb
from abby_core.observability.logging import setup_logging, logging
from abby_core.economy.xp import fetch_all_users_exp  # Assuming you've added the function to xp_handler.py
import datetime

setup_logging()
logger = logging.getLogger(__name__)

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = connect_to_mongodb()
        self.exp_leaderboard = {}  # Example exp leaderboard data

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"[💰] Leaderboard ready")

    @tasks.loop(minutes=15)
    async def update_leaderboard(self, ctx):
        # Update the exp_leaderboard dictionary
        self.exp_leaderboard = fetch_all_users_exp()
        
        leaderboard_embed = discord.Embed(title="Experience Leaderboard", color=discord.Color.blue())

        # Add data to the embed (assuming exp_leaderboard is a dictionary with user IDs and exp values)
        for position, (user_id, exp) in enumerate(sorted(self.exp_leaderboard.items(), key=lambda x: x[1], reverse=True), start=1):
            user = self.bot.get_user(user_id)
            leaderboard_embed.add_field(name=f"{position}. {user.display_name}", value=f"Exp: {exp}", inline=False)

        if hasattr(self.bot, 'leaderboard_message'):
            await self.bot.leaderboard_message.edit(embed=leaderboard_embed)
        else:
            self.bot.leaderboard_message = await ctx.send(embed=leaderboard_embed)

    @commands.command()
    async def leaderboard(self, ctx):
        # Update the exp_leaderboard dictionary when the command is invoked
        self.exp_leaderboard = fetch_all_users_exp()

        # Create the embed with a title, description, and a distinct color
        leaderboard_embed = discord.Embed(
            title="🏆 Breeze Club Experience Leaderboard 🏆" ,
            description="Here's how our members stack up in terms of experience!",
            color=discord.Color.green()  # Gold color for a leaderboard theme
        )
        
        # Add the server's logo as a thumbnail (replace 'URL' with the actual logo URL)
        leaderboard_embed.set_thumbnail(url=ctx.guild.icon)

        # Display only top 10 users for brevity and competitiveness
        top_users = list(sorted(self.exp_leaderboard.items(), key=lambda x: x[1], reverse=True))[:10]
        
        # Format the leaderboard entries
        leaderboard_text = ""
        for position, (user_id, exp) in enumerate(top_users, start=1):
            user = self.bot.get_user(user_id)
            emoji = "🏆" if position <= 3 else ""  # Trophy emoji for top 3 users
            leaderboard_text += f"{emoji} **{position}. {user.display_name}** - Exp: {exp}\n"
        
        leaderboard_embed.add_field(name="Top 10 Members", value=leaderboard_text, inline=False)
        
        # Add a footer with the timestamp
        leaderboard_embed.set_footer(text="Last Updated")
        leaderboard_embed.timestamp = datetime.datetime.now()

        # Send the beautified embed in the channel where the command was called
        await ctx.send(embed=leaderboard_embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
