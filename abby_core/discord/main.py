import discord
from discord.ext import commands
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import time
import uuid
import platform
import signal

# Version and build information
__version__ = "2.0.0"
__build_date__ = "2026-02-15"
__python_version__ = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

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
from abby_core.storage.storage_manager import StorageManager
from abby_core.generation.image_generator import ImageGenerator
from abby_core.discord.adapters import register_discord_adapters
from abby_core.services.scheduler import get_scheduler_service

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
        self.mode = (mode or os.getenv('ABBY_MODE') or os.getenv('APP_ENV') or 'prod').lower()
        # Normalize mode: 'development' → 'dev', 'production' → 'prod'
        if self.mode == 'development':
            self.mode = 'dev'
        elif self.mode == 'production':
            self.mode = 'prod'
        
        self.token: str = ""
        self.command_handler = CommandHandler(self)
        self.start_time = None
        self.init_start_time = time.time()  # Track init timing
        self.startup_id = str(uuid.uuid4())[:8]  # Correlation ID for this startup
        self.phase_timings = {}  # Track timing for each phase
        self.connection_start_time = None  # Track when connection started
        self.health_status = {  # Track component health for summary
            'mongodb': False,
            'storage': False,
            'image_gen': False,
            'scheduler': False,
        }
        self.config = BotConfig()

        # Resolve token based on mode using new get_token() method
        self.token = self.config.bot.get_token(is_dev=(self.mode == 'dev'))

        # Optional DB override for dev
        if self.mode == "dev":
            _dev_db = os.getenv("MONGODB_DB_DEV")
            if _dev_db:
                os.environ["MONGODB_DB"] = _dev_db
        
        # Startup header with version and system info
        logger.info("=" * 70)
        logger.info(f"Abby Bot v{__version__} | Build: {__build_date__} | Startup ID: {self.startup_id}")
        logger.info(f"Python {__python_version__} | {platform.system()} {platform.release()} | Mode: {self.mode.upper()}")

        # Phase 1: Core Services Initialization
        phase_start = time.time()
        log_startup_phase(
            logger,
            STARTUP_PHASES["CORE_SERVICES"],
            f"[🐰] Initializing core services (mode={self.mode})...",
        )

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
                api_host=self.config.api.stability_api_host,
            )
            logger.debug(
                f"[🐰] Core services initialized (storage={self.config.storage.storage_root}, image_gen={self.config.api.stability_api_host})"
            )
            self.phase_timings["core_services"] = time.time() - phase_start

            # Configuration validation warnings
            warnings = []
            if not self.config.api.stability_key:
                warnings.append("Image generation disabled (no Stability API key)")
            if not self.token:
                warnings.append("No Discord token configured")
            if warnings:
                logger.warning(f"[⚠️] Configuration warnings: {'; '.join(warnings)}")

            # Mark core services health
            self.health_status["storage"] = bool(self.storage)
            self.health_status["image_gen"] = bool(self.generator and self.config.api.stability_key)
        except Exception as e:
            logger.error(f"[🐰] Failed to initialize core services: {e}")
            self.storage = None
            self.generator = None

    def _count_slash_commands(self) -> tuple[int, int, int]:
        """Return (total, global, guild_specific) slash command counts."""
        try:
            global_cmds = self.tree.get_commands()
            global_keys = {cmd.qualified_name for cmd in global_cmds}
            global_count = len(global_keys)

            guild_specific_count = 0
            seen = set()
            for guild in self.guilds:
                for cmd in self.tree.get_commands(guild=guild):
                    key = f"{guild.id}:{cmd.qualified_name}"
                    if key in seen:
                        continue
                    seen.add(key)
                    if cmd.qualified_name not in global_keys:
                        guild_specific_count += 1

            total = global_count + guild_specific_count
            return total, global_count, guild_specific_count
        except Exception as e:
            logger.debug(f"[startup] Unable to count slash commands: {e}")
            return 0, 0, 0

    async def setup_hook(self):
        """Called when bot is starting up."""
        logger.debug("[🐰] Executing post-connection setup hooks...")
        
        # Register announcement delivery callback (core -> adapter bridge)
        try:
            from abby_core.services.events_lifecycle import register_announcement_delivery
            from abby_core.discord.adapters.delivery import send_announcement_to_guild
            register_announcement_delivery(send_announcement_to_guild)
            logger.debug("[🐰] Announcement delivery callback registered")
        except Exception as e:
            logger.warning(f"[🐰] Failed to register announcement delivery: {e}")
        

    async def on_ready(self):
        """Called when bot successfully connects to Discord."""
        # Only run startup sequence once (on_ready can fire multiple times)
        if hasattr(self, '_startup_complete'):
            return
        self._startup_complete = True
        
        # Capture connection timing now that we're connected
        if self.connection_start_time:
            self.phase_timings['connection'] = time.time() - self.connection_start_time
        
        log_startup_phase(logger, STARTUP_PHASES["CONNECTION"],
                         f"[🌐] Connected to Discord Gateway ({len(self.guilds)} guild{'s' if len(self.guilds) != 1 else ''})")
        
        # Initialize guild configs for all existing guilds (v2.0 schema)
        from abby_core.database.collections.guild_configuration import initialize_guild_config
        try:
            initialized_count = 0
            for guild in self.guilds:
                success = await initialize_guild_config(guild.id, guild.name)
                if success:
                    initialized_count += 1
            logger.info(f"[⚙️] Guild configurations initialized ({initialized_count}/{len(self.guilds)})")
        except Exception as e:
            logger.error(f"[guild_config] Error initializing guild configs: {e}")
        
        # Emit initial TDOS heartbeat
        try:
            emit_heartbeat(
                uptime_seconds=0,
                active_sessions=0,
                pending_submissions=0,
            )
            logger.debug("[❤️] Initial telemetry heartbeat emitted")
        except Exception as e:
            logger.error(f"[TDOS] Failed to emit initial heartbeat: {e}")
            emit_error(
                error_type=type(e).__name__,
                message=f"Failed to emit initial heartbeat: {str(e)}",
                recovery_action="Bot continues but TDOS signals unavailable"
            )
        
        # Wait for background tasks to initialize
        await asyncio.sleep(0.5)
        
        # Print startup summary now that everything is ready
        self._print_startup_summary()
    
    def _print_startup_summary(self):
        """Print final startup summary with accurate timings."""
        # Calculate total startup time
        total_startup_time = time.time() - self.init_start_time
        
        # Build health status summary
        health_status = [
            f"MongoDB: {'OK' if self.health_status['mongodb'] else 'DEGRADED'}",
            f"Storage: {'OK' if self.health_status['storage'] else 'DISABLED'}",
            f"Image Gen: {'OK' if self.health_status['image_gen'] else 'DISABLED'}",
            f"Scheduler: {'OK' if self.health_status['scheduler'] else 'DEGRADED'}"
        ]
        
        # Final startup summary with metrics
        cog_count = getattr(self, "startup_cog_count", len(self.cogs))
        slash_total, slash_global, slash_guild = self._count_slash_commands()
        if slash_total == 0:
            command_count = getattr(self, "startup_command_count", len([c for c in self.walk_commands()]))
        else:
            command_count = slash_total
        
        logger.info("=" * 70)
        log_startup_phase(
            logger, 
            STARTUP_PHASES["COMPLETE"],
            f"[✓] System operational - {cog_count} cogs, {command_count} commands ({total_startup_time:.1f}s)",
            metrics={
                "startup_id": self.startup_id,
                "cog_count": cog_count,
                "command_count": command_count,
                "startup_duration_seconds": round(total_startup_time, 2),
                "guild_count": len(self.guilds),
                "health_status": health_status
            }
        )
        logger.info(f"[💚] Health: {' | '.join(health_status)}")
        if slash_total > 0:
            logger.debug(f"[startup] Slash commands: {slash_total} (global={slash_global}, guild={slash_guild})")
            if self.mode == "dev":
                try:
                    global_cmds = sorted({cmd.qualified_name for cmd in self.tree.get_commands()})
                    logger.debug(
                        f"[startup] Slash commands (global={len(global_cmds)}): {', '.join(global_cmds)}"
                    )
                    for guild in self.guilds:
                        guild_cmds = sorted({cmd.qualified_name for cmd in self.tree.get_commands(guild=guild)})
                        logger.debug(
                            f"[startup] Slash commands (guild {guild.id}={len(guild_cmds)}): {', '.join(guild_cmds)}"
                        )
                except Exception as e:
                    logger.debug(f"[startup] Unable to list slash commands: {e}")
        logger.info(f"[⏱️] Timing: Core={self.phase_timings.get('core_services', 0):.2f}s | DB={self.phase_timings.get('mongodb', 0):.2f}s | Scheduler={self.phase_timings.get('scheduler', 0):.2f}s | Cogs={self.phase_timings.get('cogs', 0):.2f}s | Connect={self.phase_timings.get('connection', 0):.2f}s")
        logger.info(f"[🔗] Ready to serve {len(self.guilds)} guild(s) | Startup ID: {self.startup_id}")
        logger.info("=" * 70)

    async def close(self):
        """Clean shutdown - stop background services before closing."""
        try:
            logger.info("[🐰] Initiating graceful shutdown...")
            
            # Stop scheduler
            try:
                scheduler = get_scheduler_service()
                if scheduler.running:
                    await scheduler.stop()
                    logger.debug("[⏰] Scheduler stopped")
            except Exception as e:
                logger.debug(f"[⏰] Error stopping scheduler: {e}")
            
            # Call parent close
            await super().close()
            logger.info("[🐰] Shutdown complete")
        except Exception as e:
            logger.error(f"[🐰] Error during shutdown: {e}", exc_info=True)

    async def on_guild_join(self, guild):
        """Called when bot joins a new guild."""
        from abby_core.database.collections.guild_configuration import initialize_guild_config
        try:
            await initialize_guild_config(guild.id, guild.name)
            logger.info(f"[guild_config] Initialized config for new guild: {guild.name} ({guild.id})")
        except Exception as e:
            logger.error(f"[guild_config] Failed to initialize config for new guild {guild.id}: {e}")

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

    # NOTE: Heartbeat emission moved to UnifiedHeartbeatService
    # All heartbeats now run via platform scheduler (HeartbeatJobHandler)
    # This consolidates fragmented heartbeat logic into single source of truth

    async def _probe_ollama_latency(self) -> int | None:
        """Probe Ollama API for latency check (lightweight health endpoint)."""
        import aiohttp
        # ollama_base_url is in api config, provider is in llm config
        ollama_base_url = self.config.api.ollama_base_url
        provider = self.config.llm.provider
        
        if not ollama_base_url or provider != "ollama":
            return None
        
        try:
            import time
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ollama_base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        latency_ms = int((time.time() - start) * 1000)
                        return latency_ms
            return None
        except Exception as e:
            logger.debug(f"[TDOS] Ollama latency probe failed: {e}")
            return None

    async def main(self):
        # Phase 2: MongoDB Health Check
        phase_start = time.time()
        from abby_core.database.mongodb import check_mongodb_health
        self.health_status['mongodb'] = await asyncio.get_event_loop().run_in_executor(None, check_mongodb_health)
        if self.health_status['mongodb']:
            log_startup_phase(logger, STARTUP_PHASES["CORE_SERVICES"], 
                             "[📗] MongoDB connected and operational")
            
            # Initialize all registered database collections (indexes + defaults)
            from abby_core.database import initialize_all_collections
            await asyncio.get_event_loop().run_in_executor(None, initialize_all_collections)
        else:
            logger.warning("[📗] MongoDB unavailable - some features may be limited")
        self.phase_timings['mongodb'] = time.time() - phase_start

        # Phase 3: Start scheduler
        phase_start = time.time()
        from abby_core.services.scheduler import get_scheduler_service, reset_scheduler_service
        
        # Reset scheduler to ensure clean state (in case of previous crash)
        reset_scheduler_service()
        
        scheduler = get_scheduler_service()
        await scheduler.start()
        self.health_status['scheduler'] = True
        self.phase_timings['scheduler'] = time.time() - phase_start
        
        # Phase 4: Register Discord adapters (after core dependencies ready)
        from abby_core.services.heartbeat_service import reset_heartbeat_service
        reset_heartbeat_service()  # Clean state for this startup instance
        register_discord_adapters(self)
        
        # Phase 5: Load cogs and connect
        phase_start = time.time()
        async with self:
            await self.command_handler.load_commands()
            self.phase_timings['cogs'] = time.time() - phase_start
            
            if not self.token:
                logger.error("[🐰] Discord token not configured. Set ABBY_TOKEN or DEVELOPER_TOKEN.")
                raise RuntimeError("Discord token not configured")
            
            # Start connection timing
            self.connection_start_time = time.time()
            log_startup_phase(logger, STARTUP_PHASES["CONNECTION"],
                             "[🔗] Connecting to Discord Gateway...")
            await self.start(self.token, reconnect=True)
        
def run(mode: str | None = None):
    """Entry point for launch.py"""
    resolved_mode = (mode or os.getenv("ABBY_MODE", "prod")).lower()
    manager = Abby(mode=resolved_mode)
    
    async def runner():
        scheduler = get_scheduler_service()
        try:
            await manager.main()
        finally:
            # Ensure scheduler is stopped during shutdown
            try:
                await scheduler.stop()
            except Exception as e:
                logger.debug(f"[⏰] Error stopping scheduler in finally: {e}")
    
    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        logger.info("[🐰] Shutdown completed")
    except RuntimeError as e:
        if "Session is closed" in str(e):
            logger.error("[🐰] Discord session closed unexpectedly - possible port/token conflict")
            logger.error(f"[🐰] Try: Check token validity, restart system, or verify no other bots using same token")
        else:
            logger.error(f"[🐰] Runtime error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[🐰] Fatal error during bot execution: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    run()