import discord
import discord.ui
from discord import app_commands, TextStyle, Interaction
from discord.ui import View, Button, Select, TextInput, Modal

from discord.ext import commands

from utils.log_config import logging, setup_logging
setup_logging()
logger = logging.getLogger(__name__)


class PollConfirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None


    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        self.stop()



class PollInput(Modal):
    def __init__(self, title: str, options: int) -> None:
        super().__init__(title=title, timeout=None)
        self.options: list[TextInput] = []
        for i in range(options):
            option = TextInput(
                label=f"Poll Option {i+1}", style=TextStyle.short, max_length=50, required=False
            )
            self.add_item(option)
            self.options.append(option)

    async def on_submit(self, inter: Interaction) -> None:
        await inter.response.defer()
        self.stop()
        # options = [opt.value for opt in self.options]
        # await inter.response.send_message("\n".join(options))


class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.polls = {}
        self.recent_poll_id = None

    @app_commands.command(name="poll", description="Create a poll")
    async def startpoll(self, interaction: discord.Interaction, question: str):    
        modal = PollInput(title=f"Set the poll options", options=5)
        await interaction.response.send_modal(modal)
        await modal.wait()
        # Enumerate through the options and add them to a list if they are not empty
        options = []
        for option in modal.options:
            if option.value != "":
                options.append(option.value)
        # Check if there are at least 2 options
        if len(options) < 2:
            await interaction.followup.send("You need to provide at least 2 options.")
            return
        

        # Confirm the poll
        confirm_view = PollConfirm()
        confirm_embed = discord.Embed(
            title=f"🗳️ Poll: {question}",
            description="React with the corresponding emoji to vote!",
            color=discord.Color.blue(),
        )
        confirm_embed.add_field(name="Options", value="\n".join(options), inline=False)

        followup = await interaction.followup.send(f"Are you sure you want to create this poll?",embed=confirm_embed, view=confirm_view, ephemeral=True)
        followup_id = followup.id
        await confirm_view.wait()
        
        if confirm_view.value is None:
            await interaction.followup.edit_message(message_id=followup_id,content="You did not select an option.",view=None,embed=None)
            return
        elif confirm_view.value is True:
            await interaction.followup.edit_message(message_id=followup_id, content="Poll confirmed!",view=None,embed=None)
            # Create the embed
            embed = discord.Embed(
                title=f"🗳️ Poll: {question}",
                description="React with the corresponding emoji to vote!",
                color=discord.Color.blue(),
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
            # Add the options to the embed
            for idx, option in enumerate(options):
                emoji = self._get_emoji(idx)
                embed.add_field(name=f"{emoji} Option {idx + 1}", value=option, inline=False)
            # Send the embed
            poll_message = await interaction.channel.send(embed=embed)
            # Add the reactions
            for idx in range(len(options)):
                emoji = self._get_emoji(idx)
                await poll_message.add_reaction(emoji)
        else:
            await interaction.followup.send("Poll cancelled.",view=None, ephemeral=True)
            return
    

    def _get_emoji(self, index):
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        return emojis[index]

async def setup(bot):
    await bot.add_cog(PollCog(bot))
    
