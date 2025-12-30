from discord.ext import commands
import asyncio
from abby_core.utils.log_config import setup_logging, logging
import re
from discord import app_commands
import discord
setup_logging
logger = logging.getLogger(__name__)

class RemindMe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def time_amount(self, value):
        #case match
        switcher = {
            1: "1 minute",
            5: "5 minutes",
            10: "10 minutes",
            15: "15 minutes",
            30: "30 minutes",
            60: "1 hour",
            120: "2 hours",
            240: "4 hours",
            480: "8 hours",
            720: "12 hours",
            1440: "24 hours"
        }
        return switcher.get(value, "Invalid time amount")
    

    @app_commands.command(name="remindme")
    async def remind_me(self, interaction: discord.Interaction, message: str):
        """Set a reminder for yourself up to 24 hours in the future"""
        view = ReminderTime()
        user = interaction.user
        await interaction.response.send_message(f"When should I remind you?", view=view, ephemeral=True)
        await view.wait()
        time_amount = int(view.value) * 60
        time_unit = self.time_amount(int(view.value))
        
        # remind the user
        await interaction.edit_original_response(content=f"Alright, I'll remind you in {time_unit}.", view=None)
        await asyncio.sleep(time_amount)  # wait for the specified amount of time
        embed = discord.Embed(title="Reminder", description=f"{user.mention}, your reminder:\n {message}", color=0x00ff00)
        await interaction.channel.send(f"{user.mention}!", embed=embed)

class ReminderTime(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.amount = None

    @discord.ui.select(placeholder='Select a time', options=[
        discord.SelectOption(label='1 minute', description='Remind me in 1 minute', value=1, emoji='⏰'),
        discord.SelectOption(label='5 minutes', description='Remind me in 5 minutes', value=5, emoji='⏰'),
        discord.SelectOption(label='10 minutes', description='Remind me in 10 minutes', value=10, emoji='⏰'),
        discord.SelectOption(label='15 minutes', description='Remind me in 15 minutes', value=15, emoji='⏰'),
        discord.SelectOption(label='30 minutes', description='Remind me in 30 minutes', value=30, emoji='⏰'),
        discord.SelectOption(label='1 hour', description='Remind me in 1 hour', value=60, emoji='⏰'),
        discord.SelectOption(label='2 hours', description='Remind me in 2 hours', value=120, emoji='⏰'),
        discord.SelectOption(label='4 hours', description='Remind me in 4 hours', value=240, emoji='⏰'),
        discord.SelectOption(label='8 hours', description='Remind me in 8 hours', value=480, emoji='⏰'),
        discord.SelectOption(label='12 hours', description='Remind me in 12 hours', value=720, emoji='⏰'),
        discord.SelectOption(label='24 hours', description='Remind me in 24 hours', value=1440, emoji='⏰')
    ])

    async def callback(self, interaction: discord.Interaction,select: discord.ui.Select):
        self.value = select.values[0]
        self.stop()

async def setup(bot):
    await bot.add_cog(RemindMe(bot))
