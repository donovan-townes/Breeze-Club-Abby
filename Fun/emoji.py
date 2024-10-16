import discord
import random
import asyncio
from discord.ext import commands, tasks
from utils.log_config import setup_logging, logging
from Exp.xp_handler import increment_xp
import datetime

setup_logging()
logger = logging.getLogger(__name__)

class EmojiGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_game = False
        self.grid_size = 4
        self.emoji_conifgs()
        self.winner_emoji = None
        self.used_reactions = set()
        self.correct_users = []
        self.incorrect_users = []
        self.game_message = None
        self.results_message = None
        self.react_message = None
        self.test_channel = 1103490012500201632
        self.breeze_lounge = 802512963519905852
        self.guild_id = 547471286801268777
        self.active_exp = False
        self.start_tasks()

    def cog_unload(self):
        self.auto_game.cancel()
    
    def start_tasks(self):
        if not self.auto_game.is_running():
            logger.info("[🎮] Starting auto game loop")
            self.auto_game.start()

    def emoji_conifgs(self):
        self.custom_emojis = {
            "emoji1": "❤️",
            "emoji2": "🌟",
            "emoji3": "💥",
            "emoji4": "🍀",
            # Add more custom emojis as needed
        }

    def create_row(self):
        emojis = random.sample(list(self.custom_emojis.values()), self.grid_size)
        self.winner_emoji = random.choice(emojis)
        logger.info(f"Emojis: {emojis} - Winner: {self.winner_emoji}")
        return emojis

    @commands.command(name="emoji_game", aliases=["emoji","imogame","imoji","imogi","imo"])
    async def start_game(self, ctx):
        
        if ctx.author.bot:
            logger.info("[🎮] Game started by bot!")
        else:   
            logger.info(f"Game started by {ctx.author.display_name}")
        
        if not self.active_game:
            self.active_game = True
            
            logger.info(f"Game active: {self.active_game}")
            
            channel = ctx.channel
            # Your game logic goes here
            await channel.send("**BreezIMO BREEZIMO!**\nGame started! Welcome to the game!",delete_after=10)

            # Delete the user's command message
            try:
                await ctx.message.delete()
            except AttributeError:
                pass
            # Create a row with black squares
            emojis = self.create_row()
            # Send the row message
            self.game_message = await channel.send("".join(":black_large_square:" for _ in range(self.grid_size)))
            
            for emoji in emojis:
                await self.game_message.add_reaction(emoji)
            self.react_message = await channel.send("React to the correct emoji in the next 30 seconds to be awesome!!!")

            # Set a timeout of 30 seconds for the game
            await asyncio.sleep(25)
            # When 5 seconds are left, send a warning message
            if self.active_game:
                logger.info(f"{self.active_game} - {self.game_message}")
                await channel.send("5 seconds left!", delete_after=5)
                await asyncio.sleep(5)
            logger.info(f" [Start Game] Game is still active = {self.active_game}")  
            await self.end_game(ctx)

    async def start_game_auto(self):
        logger.info("[🎮] Starting game auto")
        # Function to start the game automatically
        channel = self.bot.get_channel(self.breeze_lounge)
        self.active_exp = True # Activate EXP gain

        # Start the game automatically in the specified channel
        self.active_game = True
        await channel.send("**BREEZIMO BreezIMO!!**\nGame started! Welcome to the game!", delete_after=10)
        # Create a row with black squares
        emojis = self.create_row()
        # Send the row message
        self.game_message = await channel.send("".join(":black_large_square:" for _ in range(self.grid_size)))
        for emoji in emojis:
            await self.game_message.add_reaction(emoji)
        self.react_message = await channel.send("React to the correct emoji in the next 1 minute for bonus EXP!!")

        # Set a timeout of 30 seconds for the game
        await asyncio.sleep(30)
        # When 5 seconds are left, send a warning message
        if self.active_game:
            await channel.send("30 seconds left!", delete_after=5)
            await asyncio.sleep(25)
            await channel.send("5 seconds left!", delete_after=5)
            await asyncio.sleep(5)
        await self.end_game(channel)

    async def end_game(self, ctx):
        self.active_game = False

        if self.game_message:
            await self.game_message.delete()
            self.game_message = None

        if self.react_message:
            await self.react_message.delete()
            self.react_message = None

        await asyncio.sleep(5)
        # Report correct and incorrect users
        embed = discord.Embed(title="Game Over! Results", color=0x00ff00)
        embed.add_field(name="Correct Emoji", value=self.winner_emoji)

        if self.correct_users:
            embed.add_field(name="Participants who won", value=", ".join(user.display_name for user in self.correct_users))
        else:
            embed.add_field(name="Participants who won", value="None.")

        if self.incorrect_users:
            embed.add_field(name="Runner-ups", value=", ".join(user.display_name for user in self.incorrect_users))
        else:
            embed.add_field(name="Runner-ups", value="None.")

        # Send the embed
        self.results_message = await ctx.send(embed=embed)
        self.results_message = None
            #Update User's EXP that reacted to the correct emoji
        if self.active_exp:
            for user in self.correct_users:
                user_id = user.id
                channel = self.bot.get_channel(self.breeze_lounge)
                logger.info(f"User: {user_id} - Channel: {channel}")
                await channel.send(f"{user.display_name} wins 10 EXP")
                increment_xp(user_id, 10) # Increment EXP by 10
                self.active_exp = False
        else:
            pass
        # Reset the game
        self.used_reactions = set()
        self.correct_users = []
        self.incorrect_users = []
        logger.info("[🎮] Game ended!")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("[🎮] Emoji game cog loaded")
    
    @tasks.loop(hours=24)
    async def auto_game(self):
        logger.info("[🎮] Starting auto game")
        await asyncio.sleep(10) # Wait 10 seconds before starting the game
        await self.start_game_auto()

    @auto_game.before_loop
    async def before_auto_game(self):
        await self.bot.wait_until_ready()
        logger.info("[🎮] Auto game loop ready")

        now = datetime.datetime.now()
        
        #Calculate the time for the next 8 AM
        tomorrow = now + datetime.timedelta(days=1)
        tomorrow = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)

        # If it's already past 8 AM, set the next 8 AM to be tomorrow
        if now.hour >= 8:
            tomorrow = now + datetime.timedelta(days=1)
            tomorrow = tomorrow.replace(hour=8, minute=0, second=0)
        
        time_until_8_am = (tomorrow - now).total_seconds()

        logger.info(f"Sleeping until {tomorrow}")
        await asyncio.sleep(time_until_8_am)


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not self.active_game or user.bot or reaction.message.author != self.bot.user:
            return

        try:
            # Check if the reaction was on the bot's message
            message = reaction.message
            logger.info (f"[🎮] Reaction: {reaction.emoji} - User: {user.display_name}")
            await reaction.remove(user)
            # logger.info("Removed reaction!")
            if message.author == self.bot.user and reaction.emoji in self.custom_emojis.values():
                # Get the row reactions
                # logger.info("Getting row reactions...")
                row_message = await message.channel.fetch_message(message.id)
                row_emojis = [react.emoji for react in row_message.reactions]

                if user.id not in self.used_reactions:
                    logger.info("[🎮] User's first react!")
                    self.used_reactions.add(user.id)
                    if reaction.emoji == self.winner_emoji:
                        logger.info("[🎮 ] User react was Correct!")
                        self.correct_users.append(user) # Change this to user and debug
                        # await message.channel.send(f"Correct! {reaction.emoji} is the winner!", delete_after=5)
                    else:
                        logger.info(" [🎮] User react was Incorrect!")
                        # await message.channel.send(f"Incorrect! {reaction.emoji} is not the correct emoji.", delete_after=5)
                        self.incorrect_users.append(user)
                else:
                    logger.info(" [🎮] User has already reacted!")
                    # await message.channel.send("You have already reacted to this row!", delete_after=5)
        except Exception as e:
            logger.info("Error:", e)
  
async def setup(bot):
    await bot.add_cog(EmojiGame(bot))
