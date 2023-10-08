import discord 
import random
from discord.ext import commands
from discord import app_commands
from utils.log_config import setup_logging, logging
from utils.mongo_db import connect_to_mongodb



setup_logging
logger = logging.getLogger(__name__)

BREEZE_LOUNGE = "802512963519905852"
BREEZE_MEMES = "1111136459072753664"
UP_ARROW = "⬆️"
DOWN_ARROW = "⬇️"


class Meme(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None: 
        self.bot = bot
        self.memes_collection = self.database_setup()

    def database_setup(self):
        client = connect_to_mongodb()
        db = client["Abby_Memes"]
        memes_collection = db["Memes"]
        return memes_collection
    

    def update_score(self, message_id, upvote=True):
        meme = self.memes_collection.find_one({"_id": message_id})

        if not meme:
            logger.info("Meme with id: {} not found in database".format(message_id))
            return
        
        if upvote:
            self.memes_collection.update_one({"_id": message_id}, {"$inc": {"score": 1}})
            logger.info("Updated score for meme with id: {}".format(message_id))
        else:
            self.memes_collection.update_one({"_id": message_id}, {"$inc": {"score": -1}})
            logger.info("Updated score for meme with id: {}".format(message_id))


    async def fetch_meme(self):
    # Decide whether to fetch based on popularity or randomness
        choice = random.choices(["popular", "random"], weights=[0.3, 0.7], k=1)[0]

        meme = None
        
        if choice == "popular":
            logger.info("Fetching popular meme")
            return self.get_popular_meme_from_db()
        
        if not meme:
            logger.info("Fetching random meme")
            meme = await self.get_random_new_meme_from_channel()
            self.add_meme_to_db(meme)  # Add this new meme to the database
            
            return meme
    
    def add_meme_to_db(self, meme):
        # Logic to add meme to database; 
        meme_url = self.extract_media_link(meme)
        # Set initial scores to zero
        if not self.memes_collection.find_one({"_id": meme_url}):
            self.memes_collection.insert_one({
                "_id": meme_url,
                "url": meme_url,
                "upvotes": 0,
                "downvotes": 0,
                "score": 0,
                "timestamp": meme.created_at
            })
            logger.info("Added meme with id: {} to database".format(meme_url))

    async def get_random_new_meme_from_channel(self):
        logger.info("Fetching random new meme from channel")
        # Ensure it's not in the database
        all_memes = await self.fetch_all_memes_from_channel()
        existing_meme_ids = [meme["_id"] for meme in self.memes_collection.find({}, {"_id": 1})]
        new_memes = [meme for meme in all_memes if meme.id not in existing_meme_ids]
        return random.choice(new_memes) if new_memes else None
    
    def get_popular_meme_from_db(self):
        # Fetching top 5 memes based on score
        top_memes = list(self.memes_collection.find().sort("score", -1).limit(5))
        return random.choice(top_memes)

    
    async def fetch_all_memes_from_channel(self):
        channel_id = BREEZE_MEMES
        channel = self.bot.get_channel(int(channel_id))
        # Retrieve the last 200 messages
        messages = []
        async for msg in channel.history(limit=400):
            messages.append(msg)
        return messages

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        # Check if the reaction is on a message sent by the bot
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != self.bot.user:
            return
        
        if payload.member == self.bot.user:  # Check if the reaction is added by the bot itself
            return
        
        message_id = message.content

        if str(payload.emoji) == UP_ARROW:
            logger.info("Upvoted meme with id: {}".format(message_id))
            self.update_score(message_id, upvote=True)
        if str(payload.emoji) == DOWN_ARROW:
            self.update_score(message_id, upvote=False) 
    

    def extract_media_link(self, message):
        if isinstance(message, int):  # if it's an ID, just return it
            return message

        if message.attachments:
            return message.attachments[0].url
        else:
            return None

        
    @app_commands.command(name="meme")
    async def meme_command(self, interaction: discord.Interaction) -> None:
        ''' Get a random meme from the #breeze-memes channel'''

        meme = await self.fetch_meme()

        # If we couldn't fetch a meme for some reason, we can send a default message
        if not meme:
            await interaction.response.send_message("Sorry, couldn't find a meme right now!")
            return

        # If the meme is fetched from the database, it might be in a different format (dict).
        # Ensure you're accessing the 'url' correctly based on the source (database or channel).
        meme_url = meme['_id'] if isinstance(meme, dict) else self.extract_media_link(meme)
        if meme_url is None:
            await interaction.response.send_message("Sorry, couldn't find a meme right now!")
            return
        
        logger.info(f"Sending meme with url: {meme_url}")
        await interaction.response.send_message(meme_url)
        sent_message = await interaction.original_response()
        await sent_message.add_reaction(UP_ARROW)
        await sent_message.add_reaction(DOWN_ARROW)

        

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Meme(bot))
