from discord.ext import commands as discord_commands
from twitchio.ext import commands as twitch_commands
from utils.log_config import setup_logging, logging
from dotenv import load_dotenv
import os


setup_logging()
load_dotenv()
logger = logging.getLogger(__name__)

OAUTH = os.getenv("TWITCH_OAUTH")  # The Twitch OAuth token from https://twitchapps.com/tmi/ (starts with 'oauth:'
TWITCH_CHANNEL = "bladedgwario"  # The Twitch channel you want to listen to
DISCORD_CHANNEL_ID = 1148838747106983996  # Replace with the ID of your Discord channel where you want to relay the messages

class TwitchChatCog(discord_commands.Cog):

    class TwitchBotWrapper(twitch_commands.Bot):

        def __init__(self, parent_cog):
            super().__init__(token=OAUTH, prefix='?', initial_channels=[TWITCH_CHANNEL])
            self.parent_cog = parent_cog

        async def event_ready(self):
            print(f'Logged in to Twitch as | {self.nick}')

        async def event_message(self, message):
            if message.echo:
                return
                # Combine the Twitch user's name with their message
            formatted_message = f"[Twitch | **{message.author.name}**] {message.content}"
            
            await self.parent_cog.relay_to_discord(formatted_message)


        @twitch_commands.command()
        async def hello(self, ctx):
            await ctx.send(f'Hello {ctx.author.name}!')

    def __init__(self, bot):
        self.bot = bot
        self.twitch_bot = self.TwitchBotWrapper(self)

        # Start the Twitch bot in the background
        self.bot.loop.create_task(self.twitch_bot.start())

    async def relay_to_discord(self, message_content):
        discord_channel = self.bot.get_channel(DISCORD_CHANNEL_ID)
        if discord_channel:
            await discord_channel.send(message_content)

# async def setup(bot):
#     await bot.add_cog(TwitchChatCog(bot))
