import discord
from discord.interactions import Interaction
from discord.ui import Button, View
from discord.ext import commands
import traceback

class MyView(View):

    @discord.ui.button(label='My First Button!',style=discord.ButtonStyle.green,emoji='👍')
    async def my_first_button(self, button: discord.ui.Button, interaction: discord.Interaction):  
        button.label = 'My First Clicked Button!'
        button.style = discord.ButtonStyle.red
        await interaction.response.send_message(view=self, ephemeral=True)

    @discord.ui.button(label='My Second Button!',style=discord.ButtonStyle.red,emoji='👎')
    async def my_second_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.label = 'My Second Clicked Button!'
        button.style = discord.ButtonStyle.green
        await interaction.response.send_message(view=self, ephemeral=True)
            

# Define a simple View that gives us a counter button
class Counter(discord.ui.View):

    # Define the actual button
    # When pressed, this increments the number displayed until it hits 5.
    # When it hits 5, the counter button is disabled and it turns green.
    # note: The name of the function does not matter to the library

    @discord.ui.button(label='0', style=discord.ButtonStyle.red)
    async def count(self, interaction: discord.Interaction, button: discord.ui.Button):
        number = int(button.label) if button.label else 0
        if number + 1 >= 5:
            button.style = discord.ButtonStyle.green
            button.disabled = True
        button.label = str(number + 1)

        # Make sure to update the message with our updated selves
        await interaction.response.edit_message(view=self)



