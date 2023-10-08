import asyncio
import utils.mongo_db as mongo_db
from utils.log_config import setup_logging, logging
from discord.ext import commands
client = mongo_db.connect_to_mongodb()
import discord
from discord import app_commands
setup_logging
logger = logging.getLogger(__name__)


def clear_conversation(user_id):
    try:
        client.admin.command('ping')
        print("[✅] Successfully connected to MongoDB!")
    except Exception as e:
        print(e)

    try:
        # Specify the users database
        db = client[f"User_{user_id}"]

        # Specify the collection based on the user_id
        users_collection = db["Chat Sessions"]

        # Delete all documents from the collection
        users_collection.delete_many({})

        print("[✅] Successfully cleared conversation for user", user_id)
    except Exception as e:
        print(e)

@commands.command()
async def clear(ctx, user: discord.Member = None):
    # Check if a user was mentioned
    if user is None:
        user_id = ctx.author.id
    else:
        user_id = user.id

    # Send a confirmation message
    confirm_message = await ctx.channel.send(f"Are you sure you want to clear the conversation history for <@{user_id}>? Type `yes` to confirm or `no` to cancel.")

    def check(m):
        # Only accept a message from the user who sent the command, and in the same channel
        return m.author == ctx.author and m.channel == ctx.channel and \
            m.content.lower() in ["yes", "no"]

    try:
        # wait for 60 seconds
        msg = await ctx.bot.wait_for('message', check=check, timeout=60.0)
    except asyncio.TimeoutError:
        # If no response is provided within the timeout period
        await confirm_message.edit(content='Clear conversation operation cancelled due to no response.')
    else:
        if msg.content.lower() == "yes":
            # Clear the conversation
            clear_conversation(user_id)
            await ctx.channel.send(f"Conversation history for <@{user_id}> cleared.")
        else:
            await ctx.channel.send("Clear conversation operation cancelled.")

    # Delete the confirmation message
    await confirm_message.delete(delay=5.0)

clear.description = '''
**Usage:** `!clear @<user>`

Brings up the prompt to clear the users conversation history from Mongo Database. 
If no user is tagged it will clear the user who called the command.

'''


def setup(bot):
    bot.add_command(clear)




# @commands.command()
# async def clear(ctx, user: discord.Member = None):
#     # Check if a user was mentioned
#     if user is None:
#         user_id = ctx.author.id
#     else:
#         user_id = user.id

#     # Send a confirmation message
#     confirm_message = await ctx.channel.send(f"Are you sure you want to clear the conversation history for <@{user_id}>? Type `yes` to confirm or `no` to cancel.")

#     def check(m):
#         # Only accept a message from the user who sent the command, and in the same channel
#         return m.author == ctx.author and m.channel == ctx.channel and \
#             m.content.lower() in ["yes", "no"]

#     try:
#         # wait for 60 seconds
#         msg = await ctx.bot.wait_for('message', check=check, timeout=60.0)
#     except asyncio.TimeoutError:
#         # If no response is provided within the timeout period
#         await confirm_message.edit(content='Clear conversation operation cancelled due to no response.')
#     else:
#         if msg.content.lower() == "yes":
#             # Clear the conversation
#             clear_conversation(user_id)
#             await ctx.channel.send(f"Conversation history for <@{user_id}> cleared.")
#         else:
#             await ctx.channel.send("Clear conversation operation cancelled.")

#     # Delete the confirmation message
#     await confirm_message.delete(delay=5.0)

# clear.description = '''
# **Usage:** `!clear @<user>`

# Brings up the prompt to clear the users conversation history from Mongo Database. 
# If no user is tagged it will clear the user who called the command.

# '''


# def setup(bot):
#     bot.add_command(clear)
