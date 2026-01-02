import discord
from discord.ext import commands, tasks
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio

# Add abby_core to Python path (two levels up from adapter)
ABBY_ROOT = Path(__file__).parent.parent.parent
ABBY_CORE_PATH = ABBY_ROOT / "abby_core"
if str(ABBY_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ABBY_CORE_PATH))
if str(ABBY_ROOT) not in sys.path:
    sys.path.insert(0, str(ABBY_ROOT))

# Import from abby_core
from abby_core.observability.logging import setup_logging, logging
from abby_core.observability.telemetry import emit_heartbeat, emit_error
from abby_core.storage.storage_manager import StorageManager
from abby_core.generation.image_generator import ImageGenerator

# Import from adapter (command loader moved to core/)
from .core.loader import CommandHandler
from .config import BotConfig

# Load environment variables
load_dotenv()
setup_logging()
logger = logging.getLogger("Main")

#Abby
class Abby(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)
        self.token = os.getenv('ABBY_TOKEN')
        self.command_handler = CommandHandler(self)
        self.start_time = None  # Track bot startup time
        
        # Initialize BotConfig
        self.config = BotConfig()
        
        # Initialize storage and generation services
        try:
            self.storage = StorageManager(
                storage_root=self.config.storage.storage_root,
                max_global_storage_mb=self.config.storage.max_global_storage_mb,
                max_user_storage_mb=self.config.storage.max_user_storage_mb,
                max_user_daily_gens=self.config.storage.max_user_daily_gens,
                cleanup_days=self.config.storage.cleanup_days,
                owner_user_ids=self.config.storage.quota_overrides.owner_user_ids,
                owner_daily_limit=self.config.storage.quota_overrides.owner_daily_limit,
                role_daily_limits=self.config.storage.quota_overrides.role_daily_limits,
                level_bands=self.config.storage.quota_overrides.level_bands,
            )
            logger.info("[🐰] StorageManager initialized successfully")
        except Exception as e:
            logger.error(f"[🐰] Failed to initialize StorageManager: {e}")
            self.storage = None
        
        try:
            self.generator = ImageGenerator(
                api_key=self.config.api.stability_key,
                api_host=self.config.api.stability_api_host
            )
            logger.info("[🐰] ImageGenerator initialized successfully")
        except Exception as e:
            logger.error(f"[🐰] Failed to initialize ImageGenerator: {e}")
            self.generator = None

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
        # Use ASCII-safe logging to avoid Windows console encoding issues
        try:
            logger.error(f"[ABBY] Command error in {ctx.command}: {error}")
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Fallback if emojis cause encoding issues
            logger.error(f"Command error in {ctx.command}: {repr(error)}")
        
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