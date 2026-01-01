from discord.ext import commands
from abby_core.observability.logging import setup_logging, logging
setup_logging()
logger = logging.getLogger(__name__)


@commands.command()
async def suggest(message):
    await message.send('This command is not yet impelmented, check back later!')


suggest.description = "Shows the suggested server, but user can also input one here that sends it automatically to suggestion server! (TO BE IMPLEMENTED) :)"


def setup(bot):
    bot.add_command(suggest)
