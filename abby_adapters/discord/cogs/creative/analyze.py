from discord.ext import commands
from abby_core.llm.conversation import analyze as analyze_method
from abby_core.observability.logging import logging
from abby_adapters.discord.config import BotConfig
import discord
from discord import app_commands

logger = logging.getLogger(__name__)
config = BotConfig()

class Analyze(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)


    async def send_message(self, channel, message):
        if len(message) <= 2000:
            await channel.send(message)
        else:
            chunks = [message[i: i + 1999] for i in range(0, len(message), 1999)]
            for chunk in chunks:
                await channel.send(chunk)


    async def fetch_user_messages(self, channel, author, limit=10):
        # Initiate an empty list for the messages
        messages = []

        # Fetch the messages from the channel
        async for msg in channel.history(limit=None):
            # Check if the message was sent by the author
            if msg.author == author:
                # Ignore messages that start with '!' or are one word
                if not msg.content.startswith('!') and len(msg.content.split()) > 1:
                    # If so, add it to the messages list
                    messages.append(msg.content)

            # If we've reached the required number of messages, stop fetching
            if len(messages) == limit:
                break

        return messages


    @app_commands.command(name = "analyze")
    async def analyze(self, interaction: discord.Interaction, amount: int = 10):
        '''Analyze your last <amount> of messages sent in this channel (defaults to last 10)'''
        # Fetch the message from the author
        await interaction.response.send_message(f"Analyzing your last {amount} messages..",ephemeral=True)
        message = interaction.channel
        author = interaction.user
        messages = await self.fetch_user_messages(message, author, amount)

        analysis = analyze_method(author, messages)

        # Use test channel for analysis output (configurable)
        channel = self.bot.get_channel(config.channels.test_channel)
        if not channel:
            await interaction.followup.send("❌ Analysis output channel not configured.", ephemeral=True)
            return
            
        embed = discord.Embed(title=f"Analysis of your last {amount} messages ", description=analysis, color=0x00ff00)
        embed.set_author(name=author.global_name , icon_url=author.avatar.url)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text="Analysis provided by " + self.bot.user.name, icon_url=self.bot.user.avatar.url)
        msg = await channel.send(embed=embed)
        await msg.add_reaction(config.emojis.leaf_heart)
        await interaction.followup.send(f"Analysis sent to {channel.mention}.", ephemeral=True)
  

async def setup(bot):
    await bot.add_cog(Analyze(bot))
