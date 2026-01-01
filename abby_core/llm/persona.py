"""
Persona management for Abby's LLM behavior
Pure domain logic - no Discord dependencies
"""
import abby_core.database.mongodb as mongo_db
from abby_core.observability.logging import setup_logging, logging
# Update personas
def update_personas():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]

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
    db = client["Abby_Database"]
    collection = db["bot_settings"]

    update_doc = {"$set": {"persona_message": message}}
    collection.update_one({"_id": persona}, update_doc, upsert=True)
    logger.info(f"Persona added: {persona}")

def persona_db():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Fetch the persona document from MongoDB
    return collection


def get_persona():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Fetch the persona document from MongoDB
    return collection.find_one({"_id": "active_persona"})


def update_persona(new_persona):
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Update the active persona in the persona document
    collection.update_one({"_id": "active_persona"}, {
                          "$set": {"active_persona": new_persona}}, upsert=True)


def get_persona_by_name(persona_name):
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Fetch the persona document from MongoDB
    return collection.find_one({"_id": persona_name})


def get_all_personas():
    client = mongo_db.connect_to_mongodb()
    db = client["Abby_Database"]
    collection = db["bot_settings"]
    # Fetch all the personas from MongoDB
    personas = collection.find()
    return [persona for persona in personas]

