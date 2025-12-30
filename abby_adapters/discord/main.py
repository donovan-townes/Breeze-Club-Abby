import discord
from discord.ext import commands, tasks
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio

# Add abby-core to Python path (two levels up from adapter)
ABBY_ROOT = Path(__file__).parent.parent.parent
ABBY_CORE_PATH = ABBY_ROOT / "abby-core"
if str(ABBY_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ABBY_CORE_PATH))
if str(ABBY_ROOT) not in sys.path:
    sys.path.insert(0, str(ABBY_ROOT))

# Import from abby-core
from abby_core.utils.log_config import setup_logging, logging
from abby_core.utils.tdos_events import emit_heartbeat, emit_error

# Import from adapter
from .handlers import command_loader as commandhandler

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
        self.start_time = None  # Track bot startup time

    async def setup_hook(self):
        """Called when bot is starting up."""
        logger.info("[🐰] Abby setup hook running...")
        # Start heartbeat task
        self.heartbeat_task.start()

    async def on_ready(self):
        """Called when bot successfully connects to Discord."""
        import time
        self.start_time = time.time()
        
        logger.info(f"[🐰] Abby is online as {self.user}")
        logger.info(f"[🐰] Connected to {len(self.guilds)} guilds")
        
        # Emit initial TDOS heartbeat
        try:
            emit_heartbeat(
                uptime_seconds=0,
                active_sessions=0,
                pending_submissions=0,
            )
            logger.info("[TDOS] Initial heartbeat emitted")
        except Exception as e:
            logger.error(f"[TDOS] Failed to emit initial heartbeat: {e}")
            # Emit error event about heartbeat failure
            emit_error(
                error_type=type(e).__name__,
                message=f"Failed to emit initial heartbeat: {str(e)}",
                recovery_action="Bot continues but TDOS signals unavailable"
            )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Global error handler for commands."""
        logger.error(f"[🐰] Command error in {ctx.command}: {error}")
        
        # Emit TDOS error event
        try:
            emit_error(
                error_type=type(error).__name__,
                message=str(error),
                stack_trace=None,  # Could add full traceback if needed
                recovery_action="Error logged; command failed"
            )
        except Exception as emit_err:
            logger.error(f"[TDOS] Failed to emit error event: {emit_err}")

    @tasks.loop(seconds=60)
    async def heartbeat_task(self):
        """Periodic TDOS heartbeat emission."""
        import time
        
        if self.start_time is None:
            return
        
        try:
            uptime = int(time.time() - self.start_time)
            
            # TODO: Get actual active sessions count from MongoDB
            active_sessions = 0
            
            # TODO: Get actual pending submissions count from MongoDB
            pending_submissions = 0
            
            # TODO: Check Ollama latency if available
            ollama_latency_ms = None
            
            emit_heartbeat(
                uptime_seconds=uptime,
                active_sessions=active_sessions,
                pending_submissions=pending_submissions,
                ollama_latency_ms=ollama_latency_ms
            )
            logger.debug(f"[TDOS] Heartbeat emitted (uptime: {uptime}s)")
        
        except Exception as e:
            logger.error(f"[TDOS] Failed to emit periodic heartbeat: {e}")

    @heartbeat_task.before_loop
    async def before_heartbeat_task(self):
        """Wait until bot is ready before starting heartbeat."""
        await self.wait_until_ready()

    async def main(self):
        async with self:
            await self.command_handler.load_commands()
            await self.start(self.token, reconnect=True)
        logger.info(f"[🐰️] Abby is starting")
        
def run():
    """Entry point for launch.py"""
    manager = Abby()
    asyncio.run(manager.main())

if __name__ == "__main__":
    run()