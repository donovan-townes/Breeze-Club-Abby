import abby_core.database.mongodb as mongo_db
from abby_core.observability.logging import setup_logging, logging
from discord.ext import commands

setup_logging
logger = logging.getLogger(__name__)

@commands.command()
async def personality(message, *subargs):
    # Get the current personality from MongoDB
    # Function to be implemented in mongo_db module
    personality_doc = mongo_db.get_personality()
    PERSONALITY_NUMBER = personality_doc['personality_number'] if personality_doc else 0.6

    # Check if no arguments were passed
    if not subargs:
        # Send a message with the current personality
        await message.channel.send(f"Current personality: {PERSONALITY_NUMBER}")
        return

    try:
        # Try to convert the first argument to a float
        new_personality = float(subargs[0])
    except ValueError:
        # Send an error message if the conversion failed
        await message.channel.send("Invalid personality. Personality should be a float number between 0.0 and 2.0.")
        return

    # Check if the new personality is in the correct range
    if 0.0 <= new_personality <= 2.0:
        # Update the personality in MongoDB
        # Function to be implemented in mongo_db module
        mongo_db.update_personality(new_personality)

        # Send a success message
        await message.channel.send(f"Personality updated to: {new_personality}")
    else:
        # Send an error message if the new personality is not in the correct range
        await message.channel.send("Invalid personality. Personality should be a float number between 0.0 and 2.0.")

def setup(bot):
    bot.add_command(personality)
    