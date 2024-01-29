import json
import utils.chat_openai as chat_openai
import utils.mongo_db as mongo_db
import asyncio
import random
import uuid
import time
import discord


from discord.ext import commands, tasks
from utils.log_config import setup_logging,logging

setup_logging()
logger = logging.getLogger(__name__)
ABBY_RUN = "<a:Abby_run:1135375927589748899>"
ABBY_IDLE = "<a:Abby_idle:1135376647495884820>"
ABBY_JUMP = "<a:Abby_jump:1135372059350933534>"
WAVE = "<a:leafwave:806058099051200534>"
processing_messages = [
    f"{ABBY_RUN} Abby is hopping into action...",
    f"{ABBY_JUMP} Munching on a carrot and getting to you soon...",
    f"{ABBY_IDLE} Abby is hopping down the bunny trail to find you...",
    f"{ABBY_RUN} Hang tight, Abby is burrowing to you...",
    f"{ABBY_JUMP} One hop, two hop... Abby is on it!",
    f"{ABBY_IDLE} Abby is hopping at high speed to get to you...",
    f"{ABBY_RUN} Fast as a darting rabbit! Abby is on the job...",
    f"{ABBY_RUN} Abby is bounding through the field to help you...",
    f"{ABBY_JUMP} Just like a bunny in spring, Abby is swiftly on the task...",
    f"{ABBY_IDLE} Bouncing over to get to you...",
    f"{ABBY_RUN} Abby is twitching her bunny ears and listening carefully...",
    f"{ABBY_JUMP} Crunching on some data carrots, I'll be there in a breeze...",
    f"{ABBY_IDLE} Fluffy tail bobbing, Abby is on the move to assist you...",
    f"{ABBY_RUN} Like a rabbit in a magic hat, Abby will make your answer appear..."
]

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.TIMEOUT_SECONDS = 60.0
        self.client = mongo_db.connect_to_mongodb()
        self.summon_words = self.load_words("abby/summon.json", "summon_words")
        self.dismiss_words = self.load_words("abby/dismiss.json", "dismiss_words")
        self.chat_mode = {}         # Track the state of each user's chat.The key is the user_id and the value is either 'normal' or 'code'
        self.user_channel = {}      # Track the channel of each user's chat The key is the user_id and the value is the channel object
        self.active_instances = []  # Track the active instances of the chatbot


    # Helper Functions
    def load_words(self, file_path, key):
        with open(file_path, "r") as file:
            data = json.load(file)
        return data[key]

    def get_greeting(self, user):
        name = user.mention

        bunny_words = ["*hops around*", "*munches on carrot*",
                    "*exploring the outdoors*", "🐇", "*binkies around happily*"]
        greetings = [
            f"{ABBY_RUN} Hey {name}! {random.choice(bunny_words)} Hope your day is going amazing!",
            f"{ABBY_RUN} Hello {name}! {random.choice(bunny_words)} Wishing you a fantastic day!",
            f"{ABBY_IDLE} Greetings {name}! {random.choice(bunny_words)} Sending you positive vibes!",
            f"{ABBY_JUMP} Hey there {name}! {random.choice(bunny_words)}",
            f"{ABBY_IDLE} {name}! {random.choice(bunny_words)} Feel the breeze - let it fill you with tranquility!",
            f"{ABBY_JUMP} Hey {name}! {random.choice(bunny_words)}",
            f"{ABBY_JUMP} Hello {name}! {random.choice(bunny_words)} I'm here to help you with anything you need!",
        ]

        return random.choice(greetings)
    
    async def send_message(self, channel, message):
        if len(message) <= 2000:
            await channel.send(message)
        else:
            chunks = [message[i: i + 1999] for i in range(0, len(message), 1999)]
            for chunk in chunks:
                await channel.send(chunk)
            
    def remove_user(self, user_id):
        if user_id in self.active_instances:
            self.active_instances.remove(user_id)   # Remove the user from active instances
        self.chat_mode.pop(user_id, None)           # Reset chat mode after conversation ends
        self.user_channel.pop(user_id, None)        # Reset user channel after conversation ends

    def end_cleanup(self,user,start_time):
        logger.info(f"[💭] Ending Conversation with {user.name}")
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"[⏱️] (Conversation) Elapsed Time: {elapsed_time:0.4f} seconds")
    
    def end_summary(self,user_id,session_id,chat_history):
        # Generate a summary of last conversation
        logger.info(f"[💭] Generating summary for user {user_id}, session {session_id}")
        recent_chat_history = chat_history[-5:] if len(chat_history) >= 5 else chat_history
        summary = chat_openai.summarize(recent_chat_history)
        mongo_db.update_summary(user_id, session_id, summary)
    
    def user_chat_mode(self,user_id,chat_mode,chat_history,user_input):
        logger.info(f"[💭] Chat Mode for {user_id} is {chat_mode.get(user_id)}")
        if chat_mode.get(user_id) == "code":
            response = chat_openai.chat_gpt4(user_input.content, user_id, chat_history=chat_history)
        else:
            response = chat_openai.chat(user_input.content, user_id, chat_history=chat_history)
        return response

    def user_update_chat_history(self,user_id,session_id, chat_history,user_input,response):
        mongo_db.insert_interaction(user_id, session_id, user_input.content, response)
        chat_history.append(
            {
                "input": user_input.content,
                "response": response,
            }
        )
        logger.info(f"[💭] Updated chat history for user {user_id}, session {session_id}")

    def initalize_user(self,user_id,session_id,message):
        # Fetch the last summary and insert it into the chat history only when a new conversation is initiated
        logger.info(f"[💭] Initializing user {user_id}, session {session_id} - Checking for last summary!") 
        mongo_db.update_user_metadata(user_id, message.author.name)
        last_summary = mongo_db.get_last_summary(user_id) 
        session = mongo_db.get_session(user_id, session_id)
        chat_history = session['session'] if session else []
        if last_summary:
            logger.info(f"[💭] Initializing user - Last summary found!")
            chat_history.insert(0,                    {
                        "input": "Previous Conversation Summary:",
                        "response": last_summary,
                    }
                )
        return chat_history

    # Event Listeners
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore the message if the author is a bot
        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            return

        # If message starts with '!', ignore it
        if message.content.startswith('!'):
            return
        await self.handle_chatbot(self.bot, message)

    async def handle_conversation(self,client, message, user_id, session_id, chat_history, chat_mode):
        user = message.author
        logger.info(f"[💭] Handling Conversation with {user.name}") 
        start_time = time.perf_counter()

        # Start the conversation loop
        while True:
            try:
                # Wait for user input
                user_input = await client.wait_for(
                    "message", 
                    timeout=self.TIMEOUT_SECONDS, 
                    check=lambda m: m.author == user and not m.content.startswith('!') and m.channel == self.user_channel[user_id]
                )

                # If the user says the dismiss word, send a message and reset the chatbot
                if user_input.content.lower().strip() in self.dismiss_words:
                    await user_input.channel.send(f"So happy to help {user.mention}! *happily hops off*! {ABBY_RUN}")
                    self.remove_user(user_id)
                    # Generate a summary of last conversation
                    self.end_summary(user_id,session_id,chat_history)
                    # End the conversation
                    self.end_cleanup(user,start_time)
                    break

                async with message.channel.typing():
                    # Check user's chat mode and respond accordingly
                    response = self.user_chat_mode(user_id,chat_mode,chat_history,user_input)
                await self.send_message(user_input.channel, response)
                
                # Update the chat history after each response
                self.user_update_chat_history(user_id,session_id, chat_history,user_input,response)
  
            # If the user does not respond within the timeout, send a message and reset the chatbot
            except asyncio.TimeoutError:
                await message.channel.send(f"Hey {user.mention}, I've gotta hop! {ABBY_JUMP}")
                self.remove_user(user_id)
                # Generate a summary of last conversation
                self.end_summary(user_id,session_id,chat_history)       
                # End the conversation
                self.end_cleanup(user,start_time)
                break

            # If there is an error, send a message and reset the chatbot
            except Exception as e:
                logger.warning(f"[❌] There was an error (handle_conversation) {str(e)}")
                await message.channel.send(f"Oops, there was an error. Please try again.")
                # Remove User from Chatbot
                self.remove_user(user_id)
                # End the conversation
                self.end_cleanup(user,start_time)
                break

    async def handle_chatbot(self, client, message):
        # logger.info("[💭] Handling Chatbot")
        start_time = time.perf_counter()
        user_id = str(message.author.id)

        # If the bot is already active for the user, return
        if user_id in self.active_instances:
            logger.info(f"[💭] Chatbot is already active for {user_id}")
            return
        
        if message.content.lower().startswith(tuple(self.summon_words)) or message.content.lower().startswith('code abby'):
            logger.info(f"[💭] Summoning Chatbot for {user_id}")        
            # Set the user's channel if not already set
            if user_id not in self.user_channel:
                logger.info(f"[💭] Setting user channel for {user_id}")
                self.user_channel[user_id] = message.channel

            # Send a "processing" message in bunny talk
            processing_message = await message.channel.send(random.choice(processing_messages))
            
            # Create new session ID for the user
            session_id = str(uuid.uuid4())  
            
            # Ignore the message if the user is in a different channel
            if message.channel != self.user_channel[user_id]:
                logger.info(f"[💭] User {user_id} is in a different channel")
                return 
            
            # Initialize the user's chat history
            chat_history = self.initalize_user(user_id,session_id,message)

            # Set the chat mode based on the user input
            if message.content.lower().startswith('code abby'):
                self.chat_mode[user_id] = 'code'
                user_input = message.content[10:]
            else:
                self.chat_mode[user_id] = 'normal'
                user_input = message.content[len(max(self.summon_words, key=len)):]
            
            # Add the user to active instances    
            self.active_instances.append(user_id)

            if user_input:
                # If there is an input after the summon word, process it as usual
                response = self.user_chat_mode(user_id,self.chat_mode,chat_history,message)

                # Delete the "processing" message and send the actual response
                await processing_message.delete()
                await self.send_message(message.channel, response)

                # Update the chat history after each response
                self.user_update_chat_history(user_id,session_id, chat_history,message,response)
            else:
                # If there is no input after the summon word, update the "processing" message with a greeting
                greeting = self.get_greeting(message.author)
                await processing_message.edit(content=f"{greeting} How can I assist you today? {WAVE}")
            
            # Log Chatbot Startup Time
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            logger.info(f"[⏱️] (Startup) Elapsed Time: {elapsed_time:0.4f} seconds")
            
            # Continue the listener loop, pass chat_mode as well
            await self.handle_conversation(client, message, user_id, session_id, chat_history, self.chat_mode)

async def setup(bot):
    await bot.add_cog(Chatbot(bot))
    
