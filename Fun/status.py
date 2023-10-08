import discord
from discord.ext import commands
from discord import app_commands
from utils.log_config import setup_logging, logging
setup_logging()
logger = logging.getLogger(__name__)

class BotStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='status', description='Change bot status' )
    async def status(self,interaction: discord.Interaction, message: str):
        view = StatusView()
        await interaction.response.send_message('Select status', view=view, ephemeral=True)
        await view.wait()
        logger.info(f'User {interaction.user} selected {view.value}')  

        activity_type = view.value
        # Convert activity type to lowercase
        activity_type = activity_type.lower()

        if activity_type == None or activity_type == 'none':
            # Just change the bots message activity
            await self.bot.change_presence(activity=discord.Game(name=message))
            await interaction.edit_original_response(content=f'Status updated to: {message}', view=None)
            return
        if activity_type == 'playing':
            activity = discord.Game(name=message)
        elif activity_type == 'watching':
            activity = discord.Activity(type=discord.ActivityType.watching, name=message)
        elif activity_type == 'listening':
            activity = discord.Activity(type=discord.ActivityType.listening, name=message)
        elif activity_type == 'streaming':
            activity = discord.Streaming(name=message, url='your_twitch_or_stream_url')
 
        await self.bot.change_presence(activity=activity)
        await interaction.edit_original_response(content=f'Status updated to: {activity_type} {message}',view=None)
            

class StatusView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
    
    @discord.ui.select(placeholder='Select status', options=[
        discord.SelectOption(label='Playing', description='Set playing status', emoji='🎮'),
        discord.SelectOption(label='Watching', description='Set watching status', emoji='👀'),
        discord.SelectOption(label='Listening', description='Set listening status', emoji='🎧'),
        discord.SelectOption(label='Streaming', description='Set streaming status', emoji='📡'),
    ])

    async def select_status(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.value = select.values[0]    
        self.stop()

async def setup(bot):
    await bot.add_cog(BotStatus(bot))
