import os
from twitchio.ext import commands
import logging

# logging.basicConfig(level=logging.DEBUG)

# Twitch bot configuration
bot_token = "oauth:g40phfb3enb81z6p8iq8zbwkhhtb5r"
bot_nick = "ohai_bot"
bot_prefix = "!"

# Create the bot instance
class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=bot_token,
            nick=bot_nick,
            prefix=bot_prefix,
            initial_channels=["verdagames"],
        )

    async def event_ready(self):
        target_channel = "verdagames"  # Replace with your channel name
        await self.get_channel(target_channel).send("Bot is now online!")
        print(f"Bot connected to Twitch chat as {bot_nick}")

    # Command to greet viewers
    @commands.command(name="hello")
    async def say_hello(self,ctx):
        await ctx.send(f"Hello, {ctx.author.name}!")

    # Command to display bot information
    @commands.command(name="info")
    async def bot_info(self,ctx):
        await ctx.send("I am a chatbot for this channel. You can use !hello to say hi!")    
    
# Run the bot
if __name__ == "__main__":
    twitchbot = TwitchBot()
    twitchbot.run()
