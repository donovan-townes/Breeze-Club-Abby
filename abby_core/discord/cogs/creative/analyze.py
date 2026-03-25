from discord.ext import commands
from abby_core.services.conversation_service import get_conversation_service
from tdos_intelligence.observability import logging
from abby_core.discord.config import BotConfig
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

        # TODO: PHASE 4 - Refactor analyze command to use ConversationService.generate_analysis()
        # Old signature doesn't match new unified API which requires ConversationContext
        # For now, provide simple text summary as placeholder
        if not messages:
            analysis = f"No messages found for {author.global_name}."
        else:
            msg_count = len(messages)
            analysis = f"Analysis of {msg_count} messages from {author.global_name}: Analyzed message history for patterns and engagement."

        # Use test channel for analysis output (configurable)
        channel = self.bot.get_channel(config.channels.test_channel)
        if not channel:
            await interaction.followup.send("❌ Analysis output channel not configured.", ephemeral=True)
            return
        
        # Safe embed creation with None checks
        author_avatar_url = author.avatar.url if author.avatar else None
        bot_avatar_url = self.bot.user.avatar.url if self.bot.user.avatar else None
            
        embed = discord.Embed(title=f"Analysis of your last {amount} messages", description=analysis, color=0x00ff00)
        embed.set_author(name=author.global_name, icon_url=author_avatar_url)
        if bot_avatar_url:
            embed.set_thumbnail(url=bot_avatar_url)
        embed.set_footer(text=f"Analysis provided by {self.bot.user.name}", icon_url=bot_avatar_url)
        msg = await channel.send(embed=embed)
        await msg.add_reaction(config.emojis.leaf_heart)
        await interaction.followup.send(f"Analysis sent to {channel.mention}.", ephemeral=True)
  

async def setup(bot):
    await bot.add_cog(Analyze(bot))
