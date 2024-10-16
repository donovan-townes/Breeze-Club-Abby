import utils.mongo_db as mongo_db
from utils.log_config import setup_logging, logging
from discord.ext import commands
import discord

setup_logging
logger = logging.getLogger(__name__)

# Update personas
def update_personas():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]

    PERSONAS = {
        'bunny': "I'm Abby, A bunny assistant for the Breeze Club Discord!, i will randomly insert words like: '*hops around*', '*munches on carrot*' or '*exploring the outdoors*' and other similar words and emojis in my response to match my bunny persona!",
        'kitten': "I'm Kiki, a playful kitten for the Breeze Club Discord! who loves to play and discover new things. I might say things like '*pounces on a ball of yarn*', '*curls up in the sun*', or '*chases after a laser pointer*' to match my kitten persona!",
        'owl': "I'm Oliver, a wise owl for the Breeze Club Discord! who offers insightful advice and guidance. I might say things like '*preens my feathers*', '*soars above the trees*', or '*hoots thoughtfully*' to match my owl persona!",
        'squirrel': "I'm Sammy, a cheeky squirrel who is full of energy for the Breeze Club Discord!. I might say things like '*darts up a tree*', '*munches on an acorn*', or '*chitters excitedly*' to match my squirrel persona!",
        'fox': "I'm Felix, a charming fox who has a way with words for the Breeze Club Discord!. I might say things like '*trotts through the underbrush*', '*howls at the moon*', or '*grins slyly*' to match my fox persona!",
        'panda': "I'm Paddy, a gentle panda who radiates tranquility for the Breeze Club Discord!. I might say things like '*nibbles on bamboo*', '*rolls around lazily*', or '*snoozes peacefully*' to match my panda persona!",
    }

    for persona, message in PERSONAS.items():
        # Define the update document
        update_doc = {"$set": {"persona_message": message}}
        # Update the document in the collection
        collection.update_one({"_id": persona}, update_doc, upsert=True)
    client.close()

    logger.info(" 🟢 Persona's Updated!")


def add_persona(persona, message):
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]

    update_doc = {"$set": {"persona_message": message}}
    collection.update_one({"_id": persona}, update_doc, upsert=True)
    logger.info(f"Persona added: {persona}")

def persona_db():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]
    # Fetch the persona document from MongoDB
    return collection


def get_persona():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]
    # Fetch the persona document from MongoDB
    return collection.find_one({"_id": "active_persona"})


def update_persona(new_persona):
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]
    # Update the active persona in the persona document
    collection.update_one({"_id": "active_persona"}, {
                          "$set": {"active_persona": new_persona}}, upsert=True)


def get_persona_by_name(persona_name):
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Profile"]
    collection = db["personas"]
    # Fetch the persona document from MongoDB
    return collection.find_one({"_id": persona_name})


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

# We have to update chat_openai's import call if we move this file location 