import discord
from discord.ext import commands
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)

# List of authorized user IDs who can use shutdown/restart commands
AUTHORIZED_USERS = [
    246030816692404234,  # Add your Discord user ID here
]


class ShutdownCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='shutdown', aliases=['stop'])
    @commands.is_owner()  # Only bot owner can use this
    async def shutdown(self, ctx):
        """Gracefully shutdown the bot"""
        logger.info(f"[🛑] Shutdown requested by {ctx.author} ({ctx.author.id})")
        
        embed = discord.Embed(
            title="🛑 Shutting Down",
            description="Abby is shutting down gracefully...",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        
        # Close all connections gracefully
        await self.bot.close()

    @commands.command(name='restart', aliases=['reboot'])
    @commands.is_owner()  # Only bot owner can use this
    async def restart(self, ctx):
        """Restart the bot (requires external process manager)"""
        logger.info(f"[🔄] Restart requested by {ctx.author} ({ctx.author.id})")
        
        embed = discord.Embed(
            title="🔄 Restarting",
            description="Abby is restarting... Be back in a moment!",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        
        # Close and let external process manager restart
        # For this to work, you need to run the bot with a process manager
        # or use a simple bash/batch script that restarts on exit
        await self.bot.close()

    @shutdown.error
    async def shutdown_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Only the bot owner can shutdown the bot!")

    @restart.error
    async def restart_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Only the bot owner can restart the bot!")


async def setup(bot):
    await bot.add_cog(ShutdownCommands(bot))
    logger.info("[🛑] Shutdown commands loaded")
