from discord.ext  import commands
from abby_core.utils.mongo_db import get_genres


@commands.command()
async def genres(message):
    genre_dict = get_genres()  # get genres from your MongoDB
    genre_list = [f"**{key}**: {value}\n" for key, value in genre_dict.items()]

    genre_message = "\n".join(genre_list)

    await message.channel.send("Here are the available genres:")
    await message.channel.send(genre_message)

    return



def setup(bot):
    bot.add_command(genres)
