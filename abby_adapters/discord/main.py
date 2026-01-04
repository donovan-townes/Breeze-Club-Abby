import discord
from discord.ext import commands, tasks
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import time

# Add abby_core to Python path (two levels up from adapter)
ABBY_ROOT = Path(__file__).parent.parent.parent
ABBY_CORE_PATH = ABBY_ROOT / "abby_core"
if str(ABBY_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ABBY_CORE_PATH))
if str(ABBY_ROOT) not in sys.path:
    sys.path.insert(0, str(ABBY_ROOT))

# Import from abby_core
from abby_core.observability.logging import setup_logging, logging, log_startup_phase, STARTUP_PHASES
from abby_core.observability.telemetry import emit_heartbeat, emit_error
from abby_core.database.mongodb import get_active_sessions_count, get_pending_submissions_count
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
    def __init__(self, mode: str | None = None):
        intents = discord.Intents.all()
        super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)
        self.mode = (mode or os.getenv('ABBY_MODE') or 'prod').lower()
        self.token = None
        self.command_handler = CommandHandler(self)
        self.start_time = None
        self.init_start_time = time.time()  # Track init timing
        
        # Initialize BotConfig
        self.config = BotConfig()

        # Resolve token based on mode
        if self.mode == "dev" and self.config.api.developer_token:
            self.token = self.config.api.developer_token
        else:
            self.token = self.config.api.discord_token

        # Optional DB override for dev
        if self.mode == "dev" and os.getenv("MONGODB_DB_DEV"):
            os.environ["MONGODB_DB"] = os.getenv("MONGODB_DB_DEV")
        
        # Phase 1: Core Services Initialization
        log_startup_phase(logger, STARTUP_PHASES["CORE_SERVICES"], 
                         f"[🐰] Initializing core services (mode={self.mode})...")
        
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
            self.generator = ImageGenerator(
                api_key=self.config.api.stability_key,
                api_host=self.config.api.stability_api_host
            )
            log_startup_phase(logger, STARTUP_PHASES["CORE_SERVICES"],
                            f"[🐰] Core services initialized (storage: {self.config.storage.storage_root}, image gen: {self.config.api.stability_api_host})")
        except Exception as e:
            logger.error(f"[🐰] Failed to initialize core services: {e}")
            self.storage = None
            self.generator = None

    async def setup_hook(self):
        """Called when bot is starting up."""
        log_startup_phase(logger, STARTUP_PHASES["CONNECTION"], "[🐰] Abby setup hook running...")
        # Start heartbeat task
        self.heartbeat_task.start()

    async def on_ready(self):
        """Called when bot successfully connects to Discord."""
        import time
        self.start_time = time.time()
        init_duration = time.time() - (self.init_start_time if hasattr(self, 'init_start_time') else self.start_time)
        
        log_startup_phase(logger, STARTUP_PHASES["CONNECTION"],
                         f"[🐰] Connected as {self.user} to {len(self.guilds)} guilds")
        
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
            emit_error(
                error_type=type(e).__name__,
                message=f"Failed to emit initial heartbeat: {str(e)}",
                recovery_action="Bot continues but TDOS signals unavailable"
            )
        
        # Wait for background tasks to initialize (small delay)
        await asyncio.sleep(0.5)
        
        # Final startup summary with metrics
        cog_count = len(self.cogs)
        command_count = len([c for c in self.walk_commands()])
        log_startup_phase(
            logger, 
            STARTUP_PHASES["COMPLETE"],
            f"[🐰] Startup complete: {cog_count} cogs, {command_count} commands ({init_duration:.1f}s)",
            metrics={
                "cog_count": cog_count,
                "command_count": command_count,
                "startup_duration_seconds": round(init_duration, 2),
                "guild_count": len(self.guilds)
            }
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
            active_sessions = get_active_sessions_count()
            pending_submissions = get_pending_submissions_count()
            
            # Probe Ollama latency if available
            ollama_latency_ms = await self._probe_ollama_latency()
            
            emit_heartbeat(
                uptime_seconds=uptime,
                active_sessions=active_sessions,
                pending_submissions=pending_submissions,
                ollama_latency_ms=ollama_latency_ms
            )
            logger.debug(f"[TDOS] Heartbeat emitted (uptime: {uptime}s, ollama: {ollama_latency_ms}ms)")
        
        except Exception as e:
            logger.error(f"[TDOS] Failed to emit periodic heartbeat: {e}")

    async def _probe_ollama_latency(self) -> int | None:
        """Probe Ollama API for latency check (lightweight health endpoint)."""
        import aiohttp
        ollama_host = self.config.llm.ollama_host
        if not ollama_host or self.config.llm.provider != "ollama":
            return None
        
        try:
            import time
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ollama_host}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        latency_ms = int((time.time() - start) * 1000)
                        return latency_ms
            return None
        except Exception as e:
            logger.debug(f"[TDOS] Ollama latency probe failed: {e}")
            return None

    @heartbeat_task.before_loop
    async def before_heartbeat_task(self):
        """Wait until bot is ready before starting heartbeat."""
        await self.wait_until_ready()

    async def main(self):
        async with self:
            await self.command_handler.load_commands()
            await self.start(self.token, reconnect=True)
        logger.info(f"[🐰️] Abby is starting")
        
def run(mode: str | None = None):
    """Entry point for launch.py"""
    resolved_mode = (mode or os.getenv("ABBY_MODE", "prod")).lower()
    manager = Abby(mode=resolved_mode)
    asyncio.run(manager.main())

if __name__ == "__main__":
    run()