"""
Discord adapter for persona management
Imports core logic from abby_core.llm.persona
"""
from abby_core.llm.persona import (
    update_personas,
    add_persona,
    persona_db,
    get_persona,
    update_persona,
    get_persona_by_name,
    get_all_personas
)
from abby_core.utils.log_config import setup_logging, logging
from discord.ext import commands
import discord

setup_logging()
logger = logging.getLogger(__name__)


def get_all_personas():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]
    # Fetch all the personas from MongoDB
    return list(collection.find())

@commands.has_permissions(administrator=True)
@commands.command()
async def persona(message, *args):
    if len(args) == 0:
        # No persona_name argument given
        # Fetch all available personas and list them
        personas = get_all_personas()
        if personas:
            persona_names = ", ".join(
                [p['_id'].capitalize() for p in personas if p['_id'] != "active_persona"])
            await message.channel.send(f"Available personas: {persona_names}")
        else:
            await message.channel.send("No available personas found.")
        return
    elif len(args) != 1:
        await message.channel.send("Usage: !admin persona <persona_name>")
        return

    persona_name = args[0].lower()
    
    if get_persona_by_name(persona_name) is None:
        await message.channel.send(f"Invalid persona name '{persona_name}'.")
        return

    if persona_name == get_persona()['_id']:
        await message.channel.send(f"Persona is already set to '{persona_name}'.")
        return
    
    if persona_name == 'bunny':
        # Update the discord bot nickname and profile picture
        await message.guild.me.edit(nick="🐰 Abby")
        with open("/home/Discord/Images/avatar/abby_idle1.gif", "rb") as f:
            avatar = f.read()
            await message.bot.user.edit(avatar=avatar)
    elif persona_name == 'kitten':
        # Update the discord bot nickname and profile picture
        await message.guild.me.edit(nick="🐱 Kiki")
        with open("/home/Discord/Images/avatar/kiki_1.png", "rb") as f:
            avatar = f.read()
            await message.bot.user.edit(avatar=avatar)
    elif persona_name == 'fox':
        # Update the discord bot nickname and profile picture
        await message.guild.me.edit(nick="🦊 Felix")
        with open("/home/Discord/Images/avatar/felix_1.png", "rb") as f:
            avatar = f.read()
            await message.bot.user.edit(avatar=avatar)

    update_persona(persona_name)
    await message.channel.send(f"Persona has been updated to '{persona_name}'.")

def setup(bot):
    bot.add_command(persona)
 