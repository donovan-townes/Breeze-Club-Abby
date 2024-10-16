from discord.ext import commands as discord_commands
from twitchio.ext import commands as twitch_commands
from utils.log_config import setup_logging, logging
from dotenv import load_dotenv
import os
from asyncio import run_coroutine_threadsafe

# Set up logging
setup_logging()
load_dotenv()
logger = logging.getLogger(__name__)

# Set up the environment variables
OAUTH = os.getenv("TWITCH_OAUTH")  # The Twitch OAuth token from https://twitchapps.com/tmi/ (starts with 'oauth:'
TWITCH_CHANNEL = "z8phyr"  # The Twitch channel you want to listen to
DISCORD_CHANNEL_ID = 1148838747106983996  # Replace with the ID of your Discord channel where you want to relay the messages

class TwitchChatCog(discord_commands.Cog):

    class TwitchBotWrapper(twitch_commands.Bot):

        def __init__(self, parent_cog):
            super().__init__(token=OAUTH, prefix='!', initial_channels=[TWITCH_CHANNEL])
            self.parent_cog = parent_cog

        # Unload the cog as well
        async def teardown(self):
            logger.info("Tearing Down - Twitch Bot Wrapper")
            self.unload_module()
            self.remove_cog()
            await self._ws.close()
            await self.close()

        async def event_ready(self):
            logger.info(f'Logged in to Twitch as | {self.nick}')

        async def event_command_error(self, error: Exception):
            logger.error(error)

        async def event_message(self, message):
            logger.info(f"Received message from Twitch: {message.content}")
            if message.echo:
                return
            
            if message.content.startswith(self._prefix):
                await self.handle_commands(message)
                return
            
            # logger.info("Received message from Twitch")
            #     # Combine the Twitch user's name with their message
            # formatted_message = f"[Twitch | **{message.author.name}**] {message.content} | {self.nick}"
            
            # await self.parent_cog.relay_to_discord(formatted_message)

        @twitch_commands.command()
        async def hello(self, ctx):
            await ctx.send(f'Hello {ctx.author.name}!')

        @twitch_commands.command()
        async def discord(self, ctx):
            await ctx.send(f'Join the discord at: https://discord.gg/yGsBGQAC49')

        @twitch_commands.command()
        async def twitter(self, ctx):
            await ctx.send(f'Follow me on Twitter at: https://twitter.com/z8phyr')
        
        @twitch_commands.command()
        async def github(self, ctx):
            await ctx.send(f'Check out my GitHub at: https://github.com/z8phyr')
        
        @twitch_commands.command()
        async def youtube(self, ctx):
            await ctx.send(f'Subscribe to my YouTube at: https://www.youtube.com/z8phyrmusic')
        
        @twitch_commands.command()
        async def instagram(self, ctx):
            await ctx.send(f'Follow me on Instagram at: https://www.instagram.com/z8phyr')
        
        @twitch_commands.command()
        async def website(self, ctx):
            await ctx.send(f'Check out my website at: https://z8phyr.com')
        
        @twitch_commands.command()
        async def donate(self, ctx):
            await ctx.send(f'Support me by donating at: https://streamlabs.com/z8phyr/tip')

        @twitch_commands.command()
        async def soundcloud(self, ctx):
            await ctx.send(f'Listen to my music on SoundCloud at: https://soundcloud.com/z8phyr')
        
        @twitch_commands.command()
        async def spotify(self, ctx):
            await ctx.send(f'Listen to my music on Spotify at: https://open.spotify.com/artist/0wJ6V9Vv3y9e8Tq7RQm6p8')
        
        @twitch_commands.command()
        async def bandcamp(self, ctx):
            await ctx.send(f'Listen to my music on Bandcamp at: https://z8phyr.bandcamp.com')

        @twitch_commands.command()
        async def twitch(self, ctx):
            await ctx.send(f'Follow me on Twitch at: https://www.twitch.tv/z8phyr')

        @twitch_commands.command()
        async def tiktok(self, ctx):
            await ctx.send(f'Follow me on TikTok at: https://www.tiktok.com/@z8phyr')

        @twitch_commands.command()
        async def snapchat(self, ctx):
            await ctx.send(f'Add me on Snapchat at: https://www.snapchat.com/add/z8phyr')

        @twitch_commands.command()
        async def facebook(self, ctx):
            await ctx.send(f'Like me on Facebook at: https://www.facebook.com/z8phyr')

        @twitch_commands.command()
        async def linkedin(self, ctx):
            await ctx.send(f'Connect with me on LinkedIn at: https://www.linkedin.com/in/z8phyr')

        @twitch_commands.command()
        async def pinterest(self, ctx):
            await ctx.send(f'Follow me on Pinterest at: https://www.pinterest.com/z8phyr')

        @twitch_commands.command()
        async def reddit(self, ctx):
            await ctx.send(f'Follow me on Reddit at: https://www.reddit.com/user/z8phyr')
          
        @twitch_commands.command()
        async def subscribe(self, ctx):
            await ctx.send(f'Subscribe to me on Twitch at: https://www.twitch.tv/subs/z8phyr \n You get access to exclusive emotes, a sub badge, and ad-free viewing!')


    def __init__(self, bot):
        self.bot = bot
        self.twitch_bot = self.TwitchBotWrapper(self)

        # Start the Twitch bot in the background
        self.bot.loop.create_task(self.twitch_bot.start())

    def cog_unload(self):
        if self.twitch_bot:
            # Stop the Twitch bot in the background
            pass

    async def relay_to_discord(self, message_content):
        discord_channel = self.bot.get_channel(DISCORD_CHANNEL_ID)
        if discord_channel:
            await discord_channel.send(message_content)

async def setup(bot):
    await bot.add_cog(TwitchChatCog(bot))
