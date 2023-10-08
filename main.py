import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from utils.log_config import setup_logging, logging
import asyncio
import handlers.command_loader as commandhandler


load_dotenv()
setup_logging()
logger = logging.getLogger("Main")

#Abby
class Abby(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)
        self.token = os.getenv('ABBY_TOKEN')
        self.command_handler = commandhandler.CommandHandler(self)

    async def main(self):
        async with self:
            await self.command_handler.load_commands()
            await self.start(self.token, reconnect=True)
        logger.info(f"[🐰️] Abby is starting")
        
if __name__ == "__main__":
        manager = Abby()
        asyncio.run(manager.main())