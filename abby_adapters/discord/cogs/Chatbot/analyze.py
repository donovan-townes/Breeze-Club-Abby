from discord.ext import commands
from abby_core.llm.conversation import analyze as analyze_method
from abby_core.observability.logging import setup_logging, logging
import discord
from discord import app_commands

setup_logging()
LEAF_HEART = "<a:z8_leafheart_excited:806057904431693824>"

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

        channel_id = 1132531783884341291  # Replace with the desired channel ID
        channel = self.bot.get_channel(channel_id)  # Get the channel object
        embed = discord.Embed(title=f"Analysis of your last {amount} messages ", description=analysis, color=0x00ff00)
        embed.set_author(name=author.global_name , icon_url=author.avatar.url)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text="Analysis provided by " + self.bot.user.name, icon_url=self.bot.user.avatar.url)
        msg = await channel.send(embed=embed)  # Send the analysis to the channel
        await msg.add_reaction(LEAF_HEART)
        # await self.send_message(channel,analysis)  # Send the analysis to the channel
        await interaction.followup.send("Analysis sent to <#1132531783884341291>.", ephemeral=True)
  

async def setup(bot):
    await bot.add_cog(Analyze(bot))
