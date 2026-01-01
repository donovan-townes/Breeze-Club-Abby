from discord.ext import commands
from abby_core.observability.logging import setup_logging, logging
import requests
from discord import app_commands
import discord

# @commands.command()

# async def random_genre(ctx, num_results: int = 5):
#     api_url = f"https://binaryjazz.us/wp-json/genrenator/v1/genre/{num_results}"
#     response = requests.get(api_url)

#     if response.status_code == 200:
#         genres = response.json()
#         for genre in genres:
#             await ctx.send(genre)
#     else:
#         await ctx.send("Failed to fetch random genres. Please try again later.")
# @commands.command()
# async def random_story(ctx, num_results: int = 5):
#     api_url = f"https://binaryjazz.us/wp-json/genrenator/v1/story/{num_results}"
#     response = requests.get(api_url)

#     if response.status_code == 200:
#         genres = response.json()
#         for genre in genres:
#             await ctx.send(genre)
#     else:
#         await ctx.send("Failed to fetch random genres. Please try again later.")

# random_genre.description = """Generates random genres. 
# Free API from https://binaryjazz.us/genrenator-api/

# """

# random_story.description = "Generates random stories."  


# def setup(bot):
#     bot.add_command(random_genre)
#     bot.add_command(random_story)


class Genrenator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="genrenator",description="Generates random genres. Free API from https://binaryjazz.us/genrenator-api/")
    async def genrenator(self, interaction: discord.Interaction, num_results: int = 5):
        api_url = f"https://binaryjazz.us/wp-json/genrenator/v1/genre/{num_results}"
        response = requests.get(api_url)

        if response.status_code == 200:
            genres = response.json()
            embed = discord.Embed(title="Random Genres", description="Here are some random genres for you to use!", color=0x00ff00)
            for genre in genres:
                embed.add_field(name="Genre", value=genre, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to fetch random genres. Please try again later.")
    
    @app_commands.command(name="story",description="Generates random stories. Free API from https://binaryjazz.us/genrenator-api/")
    async def story(self, interaction: discord.Interaction, num_results: int = 5):
        api_url = f"https://binaryjazz.us/wp-json/genrenator/v1/story/{num_results}"
        response = requests.get(api_url)

        if response.status_code == 200:
            genres = response.json()
            embed = discord.Embed(title="Random Stories", description="Here are some random stories for you to use!", color=0x00ff00)
            for genre in genres:
                embed.add_field(name="Story", value=genre, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Failed to fetch random stories. Please try again later.")

async def setup(bot):
    await bot.add_cog(Genrenator(bot))