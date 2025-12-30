import asyncio
import os
import random
import re

import dateutil.parser as parser
import discord
from discord.ext import commands,tasks
from dotenv import load_dotenv
from abby_core.utils.log_config import logging, setup_logging
from abby_core.utils.mongo_db import *
from datetime import timedelta, datetime
from abby_adapters.discord.cogs.Twitter.Client import TwitterClient
from tabulate import tabulate
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Obtain Giveaway URL
GIVEAWAY_URL = os.getenv("GIVEAWAY_URL")

# Discord Channels
GUST_CHANNEL = 802461884091465748
ABBY_CHAT = 1103490012500201632
GIVEAWAY_CHANNEL = 802461884091465748
BREEZE_FAM = 807664341158592543

def convert_seconds_to_readable(seconds):
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    
    if days > 0:
        duration_str = f"{days} days"
    elif hours > 0:
        duration_str = f"{hours} hours"
    else:
        duration_str = f"{minutes} minutes"
    
    return duration_str

# Insert the Giveaway Document into the database
def update_giveaway_metadata(prize,emoji,channel,duration,start_time):
    client = connect_to_mongodb()
    db = client["Abby_Giveaway"]
    collection = db["Giveaway"]


    # Fill in the Giveaway Document
    
    giveaway_data = {
        'giveaway_prize': prize,
        'giveaway_emoji': emoji,
        'giveaway_channel': channel,
        'giveaway_duration': duration,
        'giveaway_start_time': start_time
    }
    
    try:
        inserted_id = collection.insert_one(giveaway_data).inserted_id
        logger.info(f"[📗] Successfully Inserted Giveaway Metadata with ID: {inserted_id}")
    except Exception as e:
        logger.warning("[❌] update_giveaway_metadata error")
        logger.warning(str(e))

#Define the questions for the Giveaway
giveaway_questions = {
    'question_1': "What is the Giveaway Prize?",
    'question_2': "What is the Giveaway Emoji?",
    'question_3': "What is the Giveaway Channel?",
    'question_4': "What is the Giveaway Duration?",
    'question_5': 'What is the Giveaway Start Time?'
}

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.giveaway_task = None

    def cog_unload(self):
        self.hourly_giveaway_check.cancel()
        

    # Giveaway Embed
    async def giveaway_embed(self,channel,emoji,prize,duration):
        
        channel = self.bot.get_channel(int(channel))
        embed = discord.Embed(
            title="🎉 Breeze Club Giveaway 🎉",
            description=f"React with {emoji} to enter!\nHosted by the Breeze Club",
            color=discord.Color.green(),
        )
        duration = convert_seconds_to_readable(duration)
        embed.add_field(name="Prize:", value=prize)
        embed.set_footer(text=f"Ends in {duration}")
        logger.info(f"[🎉] (GIVEAWAY_EMBED) Channel Should be: {channel}")
        await channel.send("🎉 **GIVEAWAY** 🎉")
        await channel.send(f"Enter Now <@&{BREEZE_FAM}>!")
        message = await channel.send(embed=embed)
        message_id = message.id
        await message.add_reaction(emoji)
        
        return message, message_id

    # Start Giveaway
    async def start_giveaway(self, giveaway):
        logger.info(f"[🎉] Starting Giveaway")
        client = connect_to_mongodb()
        db = client["Abby_Giveaway"]    
        collection = db["Giveaway"]
        # Fetch the correct giveaway and message_id
        collection.find_one({"_id": giveaway['_id']})
        # Fetch the giveaway message
        channel = self.bot.get_channel(giveaway['giveaway_channel'])
        # logger.info(f"[🎉] Channeld ID is (should be an integer): {channel}")
        message, message_id = await self.giveaway_embed(giveaway['giveaway_channel'],giveaway['giveaway_emoji'],giveaway['giveaway_prize'],giveaway['giveaway_duration'])
        # Update the giveaway message ID in the database
        collection.update_one({"_id": giveaway['_id']}, {
                                "$set": {"giveaway_message_id": message_id}}, upsert=True)
        #Log the start of the Giveaway and provide giveaway ID and details
        logger.info(f"[🎉] Giveaway Started")
        logger.info(f"[🎉] Giveaway ID: {giveaway['_id']}")

    # End Giveaway
    async def end_giveaway(self, giveaway):
        # Fetch the Giveaway
        client = connect_to_mongodb()
        db = client["Abby_Giveaway"]
        collection = db["Giveaway"]
        
        # Check if giveaway has a message_id (old giveaways might not)
        if 'giveaway_message_id' not in giveaway:
            logger.warning(f"[🎉] Giveaway {giveaway['_id']} missing message_id, marking as ended without winner selection")
            # Mark the giveaway as ended in database
            collection.update_one(
                {"_id": giveaway['_id']},
                {"$set": {"giveaway_ended": True}}
            )
            return
        
        # Fetch the correct giveaway and message_id
        collection.find_one({"_id": giveaway['_id']})
        # Fetch the giveaway message
        channel = self.bot.get_channel(giveaway['giveaway_channel'])
        if not channel:
            logger.error(f"[🎉] Could not find channel {giveaway['giveaway_channel']} for giveaway {giveaway['_id']}")
            return
            
        message = await channel.fetch_message(giveaway['giveaway_message_id'])
        # Fetch the giveaway reactions
        reactions = message.reactions
        users = []
        async for user in reactions[0].users():
            users.append(user)
        # Remove the bot from the list of users
        users.remove(self.bot.user)
        # Select a random winner
        winner = random.choice(users)
        # Announce the winner
        await channel.send(f"Congratulations {winner.mention}, you won the {giveaway['giveaway_prize']}!")
        # Remove the giveaway from the database
        collection.delete_one({"_id": giveaway['_id']})
        logger.info(f"[🎉] Giveaway has been deleted from the database")

    # List Giveaways
    @commands.command()
    async def list_giveaways(self,ctx):
        client = connect_to_mongodb()
        db = client["Abby_Giveaway"]
        collection = db["Giveaway"]
        # Fetch the giveaway from the database
        giveaways = collection.find({})
        # Iterate through the giveaways and print them


        for giveaway in giveaways:
            duration = giveaway['giveaway_duration']
            duration_read = convert_seconds_to_readable(duration)    
            embed = discord.Embed(title="Giveaway Information", color=0x00ff00)
            embed.add_field(name="Giveaway ID", value=giveaway['_id'], inline=False)
            embed.add_field(name="Giveaway Prize", value=giveaway['giveaway_prize'], inline=False)
            embed.add_field(name="Giveaway Emoji", value=giveaway['giveaway_emoji'], inline=False)
            embed.add_field(name="Giveaway Channel", value=f"<#{giveaway['giveaway_channel']}>", inline=False)
            embed.add_field(name="Giveaway Duration", value=duration_read, inline=False)
            embed.add_field(name="Giveaway Start Time", value=giveaway['giveaway_start_time'], inline=False)
            
            if 'giveaway_message_id' in giveaway:
                embed.add_field(name="Giveaway Message ID", value=giveaway['giveaway_message_id'], inline=False)
            
            embed.set_footer(text="Powered by Abby!", icon_url=self.bot.user.avatar.url)
            
            await ctx.send(embed=embed)

    # Only the Server Owner can call this command
    @commands.has_permissions(administrator=True)
    @commands.command()
    async def add_giveaway(self,ctx):
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        # Ask What is the Prize
        await ctx.send(giveaway_questions['question_1'])
        giveaway_prize = await self.bot.wait_for('message', check=check)
        giveaway_prize = giveaway_prize.content # Obtain the Prize from the message
        
        # Ask what Emoji will be used
        await ctx.send(giveaway_questions['question_2'])
        giveaway_emoji = await self.bot.wait_for('message', check=check)
        giveaway_emoji = giveaway_emoji.content.lower() # Obtain the Emoji ID from the message
        # Use regular expression to extract the emoji ID
        emoji_id_match = re.search(r'<(?:a)?:[a-zA-Z0-9_]+:(\d+)>', giveaway_emoji)
        if emoji_id_match:
            giveaway_emoji_id = emoji_id_match.group(1)
            logger.info(f"Extracted emoji ID: {giveaway_emoji_id}")
        else:
            logger.error("Failed to extract emoji ID")
            await ctx.send("Failed to extract emoji ID. Please provide a valid emoji.")
            return

              
        # Ask what Channel will be used
        await ctx.send(giveaway_questions['question_3'])
        giveaway_channel = await self.bot.wait_for('message', check=check)
        giveaway_channel = giveaway_channel.content.lower() # Obtain the Channel ID from the message
        
        # Use regular expression to extract the channel ID from the mention
        channel_id_match = re.search(r'<#(\d+)>', giveaway_channel)
        if channel_id_match:
            giveaway_channel_id = int(channel_id_match.group(1))
            logger.info(f"Extracted channel ID: {giveaway_channel_id}")
        else:
            logger.error("Failed to extract channel ID")
            await ctx.send("Failed to extract channel ID. Please try again.")
            return


        # Ask what the Duration will be
        await ctx.send(giveaway_questions['question_4'])
        giveaway_duration = await self.bot.wait_for('message', check=check)
        giveaway_duration = giveaway_duration.content.lower() # Convert the message to time Duration (Days, Hours)
        
        # Use regular expressions to extract days and hours from the input
        days_match = re.search(r'(\d+)\s*days?', giveaway_duration)
        hours_match = re.search(r'(\d+)\s*hours?', giveaway_duration)

        days = int(days_match.group(1)) if days_match else 0
        hours = int(hours_match.group(1)) if hours_match else 0

        giveaway_duration = days * 24 * 60 * 60 + hours * 60 * 60

        # Ask what the Start Time will be
        await ctx.send(giveaway_questions['question_5'])
        giveaway_start_time_input = await self.bot.wait_for('message', check=check)
        giveaway_start_time_input = giveaway_start_time_input.content  # Remove .lower() to maintain the case

        # Use dateutil to parse the human-readable start time input
        try:
            giveaway_start_time = parser.parse(giveaway_start_time_input, fuzzy=True)
            logger.info(f"Parsed start time: {giveaway_start_time}")
        except Exception as e:
            logger.error(f"Failed to parse start time: {e}")
            await ctx.send("Failed to parse start time. Please try again.")
            logger.info(f"Failed to parse start time: {giveaway_start_time_input}")
            return        

        # Convert the duration into human readable format (days,hours,minutes)
        giveaway_duration_read = convert_seconds_to_readable(giveaway_duration)
        # Confirm the information with the user
        await ctx.send(f"Giveaway Prize: {giveaway_prize}\nGiveaway Emoji: {giveaway_emoji}\nGiveaway Channel: {giveaway_channel}\nGiveaway Duration: {giveaway_duration_read}\nGiveaway Start Time: {giveaway_start_time}")
        await ctx.send("Is this information correct? (y/n)")
        confirmation = await self.bot.wait_for('message', check=check)
        confirmation = confirmation.content.lower()
        if confirmation == 'y':
            await ctx.send("Giveaway Added!")
        else:
            await ctx.send("Giveaway Cancelled")
            return
        
        update_giveaway_metadata(giveaway_prize,giveaway_emoji,giveaway_channel_id,giveaway_duration,giveaway_start_time)
        
        logger.info(" [🎉] Giveaway Successfully Added")
      

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.hourly_giveaway_check.is_running():
            self.hourly_giveaway_check.start()

    # Schedule the Giveaway Check (Every Hour)
    @tasks.loop(hours=1)
    async def hourly_giveaway_check(self):
        await self.check_giveaways()
    
    @hourly_giveaway_check.before_loop
    async def before_hourly_giveaway_check(self):
        await self.bot.wait_until_ready()
        logger.info("[🎉] Giveaway Check initialized. Check is every [1] Hour")

    # Giveaway Check
    async def check_giveaways(self):
        client = connect_to_mongodb()
        db = client["Abby_Giveaway"]
        collection = db["Giveaway"]
        current_time = datetime.now()
        
        # Iterate through all giveaways and check their statuses
        for giveaway in collection.find():
            logger.info(f"[🎉] Checking Giveaway: {giveaway['_id']}")
            giveaway_start_time = giveaway['giveaway_start_time']
            giveaway_duration = timedelta(seconds=giveaway['giveaway_duration'])  # Convert duration to timedelta
            end_time = giveaway_start_time + giveaway_duration

            if current_time >= giveaway_start_time and current_time <= end_time:
                table_data = []

                # The giveaway is currently running
                table_data.append(("Status", "Running"))

                # Announce remaining time for running giveaway
                current_time = datetime.now()
                time_left = end_time - current_time
                time_left_readable = convert_seconds_to_readable(time_left.total_seconds())
                table_data.append(("Time Left", time_left_readable))

                # Report the giveaway prize
                table_data.append(("Prize", giveaway['giveaway_prize']))

                # Create headers and format the table
                headers = ["Attribute", "Value"]
                table = tabulate(table_data, headers=headers, tablefmt="grid")

                logger.info(f"\n{table}")
                pass
            elif current_time > end_time:
                # The giveaway has ended
                logger.info(f"[🎉] Giveaway has ended")
                # Run the End Giveaway function
                await self.end_giveaway(giveaway)
            elif current_time.date() == giveaway_start_time.date() and current_time.hour >= giveaway_start_time.hour - 1:
                # The giveaway is about to start within the next hour
                logger.info(f"[🎉] Giveaway is about to start")
                logger.info(f"[🎉] Giveaway ID: {giveaway['_id']}")
                #calculate the time left until the giveaway starts
                time_left = giveaway_start_time - current_time
                readable_time_left = convert_seconds_to_readable(time_left.total_seconds())
                #Sleep until the giveaway starts
                logger.info(f"[🎉] Sleeping for {readable_time_left} seconds and starting Giveaway!")
                await asyncio.sleep(time_left.total_seconds())
                await self.start_giveaway(giveaway)
            else:
                # Calculate the time left until the giveaway starts
                time_left = giveaway_start_time - current_time
                time_left = convert_seconds_to_readable(time_left.total_seconds())
                # Report the upcoming giveaway
                logger.info(f"[🎉]The giveaway for {giveaway['giveaway_prize']} will start in {time_left}")
        # logger.info(f"[🎉] Finished Checking Giveaways!")


async def setup(bot):
    await bot.add_cog(Giveaway(bot))



