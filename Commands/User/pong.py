from discord.ext import commands


@commands.command()
async def pong(message):
    await message.send('SHMOOOONG!!!')

pong.description = "SHMONGS the bot! :)"


def setup(bot):
    bot.add_command(pong)
