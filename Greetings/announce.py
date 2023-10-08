from discord.ext import commands
from discord import app_commands
import asyncio
import discord
import datetime
from dateutil import parser
from discord.interactions import Interaction
from utils.log_config import setup_logging, logging
from discord.ui import View, Button, ChannelSelect, RoleSelect, MentionableSelect

from typing import Optional, Union, List
setup_logging()
logger = logging.getLogger(__name__)

# Announcements
class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = bot
        self.logger = logger
        self.EMOJI = '<a:Abby_run:1135375927589748899>'

    # Helper Functions        
    async def post_announcement(self,interaction,channel,announcement_title,announcement_message,notified_members_roles=None):
        channel = self.bot.get_channel(channel.id)
        if notified_members_roles:
            mentions = ""
            for role in notified_members_roles:
                mentions += f"{role.mention} "
            await channel.send(f"Attention {mentions}!")
        else:
            await channel.send(f"Attention @everyone !")

        author = interaction.user
        server_nickname = author.display_name

        embed = discord.Embed(title=announcement_title, description=announcement_message, color=0x00ff00)
        embed.set_author(name=server_nickname or author.display_name, icon_url=author.avatar.url)    
        posted_message = await channel.send(embed=embed)                
        
        # Add the reaction to the posted message
        await posted_message.add_reaction(self.EMOJI)

    async def schedule_announcement(self, interaction, channel, announcement_title, announcement_message, notified_members_roles, scheduled_time):
        time_until_announcement, human_readable_time = self.obtain_time(scheduled_time)
        # Schedule the announcement using an asynchronous loop
        self.logger.info(f"Waiting {human_readable_time} post announcement.")
        await asyncio.sleep(time_until_announcement)
        # Post the announcement
        await self.post_announcement(interaction, channel, announcement_title, announcement_message, notified_members_roles)

    def obtain_time(self,scheduled_time):
        time_until_announcement = (scheduled_time - datetime.datetime.now()).total_seconds()
        #Convert to hours/minutes/seconds
        hours, remainder = divmod(time_until_announcement, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours < 1:
            human_readable_time = f"{int(minutes)} minutes and {int(seconds)} seconds"
        elif minutes < 1:
            human_readable_time = f"{int(seconds)} seconds"
        else:
            human_readable_time = f"{int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds"
        return time_until_announcement, human_readable_time

    # Slash Command
    @app_commands.command(name='announce', description='Create an announcement for the server')
    async def announce(self, interaction: discord.Interaction):
        message_modal = MessageModal()
        await interaction.response.send_modal(message_modal)
        await message_modal.wait()
        title = message_modal.title if message_modal.title else 'Announcement'
        message = message_modal.message
        
        options = AnnounceOptions()
        option_msg = await interaction.followup.send('Select options', view=options, ephemeral=True)
        option_id = option_msg.id
        await options.wait()
        
        channel = options.channel if options.channel else interaction.channel
        # If the user selected multiple roles, add all the notified roles to role_mentions
        roles = options.roles

        scheduled = options.schedule
        scheduled_time = options.scheduled_date

        embed_prev = discord.Embed(title=title, description=message)
        embed_prev.add_field(name='Channel', value=channel.mention)
        if roles:
            role_mentions = ""
            for role in roles:
                role_mentions += f"{role.mention} "
            embed_prev.add_field(name='Roles', value=role_mentions)
        embed_prev.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        view = AnnouncementView()

        if scheduled == "Yes":       
            embed_prev.add_field(name='Scheduled Time', value=scheduled_time.strftime('%B %d at %I:%M%p'))
            
            view = AnnouncementView()
            await interaction.followup.edit_message(message_id=option_id,content=f"Are you sure you want to schedule this announcement?",embed=embed_prev,view=view)
            await view.wait()

            if view.value:
                human_readable_time = self.obtain_time(scheduled_time)[1]
                await interaction.followup.edit_message(message_id=option_id,content=f'Announcement scheduled in {human_readable_time}.',embed=None,view=None)
                await self.schedule_announcement(interaction, channel, title, message, roles, scheduled_time)
                return
            else:
                await interaction.followup.edit_message(message_id=option_id,content=f'Announcement cancelled.',embed=None,view=None)
                return

        else:
            await interaction.followup.edit_message(message_id=option_id,content=f"Are you sure you want to post this announcement?",embed=embed_prev,view=view)
            await view.wait()
            if view.value:
                    await self.post_announcement(interaction,channel, title, message, roles)
                    await interaction.followup.edit_message(message_id=option_id,content='Announcement posted.',embed=None,view=None)
                    return
            else:
                await interaction.followup.edit_message(message_id=option_id,content='Announcement cancelled.',embed=None,view=None)
                return

# UI Components        
class MessageModal(discord.ui.Modal, title="Create an announcement"):
    title = None
    message = None

    title_input = discord.ui.TextInput(label='Title', placeholder="Announcement Title (Optional)",required=False)
    message_input = discord.ui.TextInput(label='Message', placeholder="Message",style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(error)
        self.stop()

    async def on_timeout(self) -> None:
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()

    async def interaction_check(self, interaction: Interaction[discord.Interaction]) -> bool:
        self.title = self.title_input.value
        self.message = self.message_input.value
        return True
    
class AnnounceOptions(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.channel = None
        self.schedule = None
        self.scheduled_date = None
        self.roles = []

    @discord.ui.select(cls=ChannelSelect,channel_types=[discord.ChannelType.text,discord.ChannelType.news], placeholder='Select a channel (Optional)', min_values=1, max_values=1)
    async def select_channels(self, interaction: discord.Interaction, select: ChannelSelect):
        if select.values:
            self.channel = select.values[0]
        else:
            self.channel = None
        await interaction.response.defer()
        await self.wait()

    @discord.ui.select(cls=RoleSelect, placeholder='Notify any roles? (Optional)', min_values=0, max_values=3)
    async def select_roles(self, interaction: discord.Interaction, select: RoleSelect):
        if select.values:
            for value in select.values:
                self.roles.append(value)
        else:
            self.role = None
        await interaction.response.defer()
        await self.wait()

    @discord.ui.select(placeholder='Schedule announcement?', options=[
        discord.SelectOption(label='Post it now!', description='Post announcement now', emoji='📣'),
        discord.SelectOption(label='Schedule it!', description='Schedule announcement', emoji='📅'),
    ])
    async def select_schedule(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "Yes":
            modal=ScheduleInput()
            await interaction.response.send_modal(modal)
            await modal.wait()
            self.schedule = select.values[0]
            self.scheduled_date = modal.scheduled_time
        else:
            self.schedule = select.values[0]
        
        await interaction.response.defer()
        self.stop()

class AnnouncementView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None


    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, emoji='☑️')
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, emoji='✖️')
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        self.stop()

    async def on_timeout(self) -> None:
        return False

class ScheduleInput(discord.ui.Modal, title="Schedule the announcement"):

    scheduled_time = None
    scheduled_date_input = discord.ui.TextInput(label='Date and Time', placeholder="May 6 at 12:00 pm or `12:05am`")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        logger.error(error)
        self.scheduled_time = None
        self.stop()

    async def on_timeout(self) -> None:
        self.scheduled_time = None
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.scheduled_time = None
        self.stop()

    async def interaction_check(self, interaction: Interaction[discord.Interaction]) -> bool:
        try:
            self.scheduled_time = parser.parse(self.scheduled_date_input.value)
            return True
        except ValueError:
            await self.wait()

async def setup(bot):
    await bot.add_cog(Announcements(bot))
