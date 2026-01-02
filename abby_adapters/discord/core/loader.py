"""
Core command and cog loader for dynamic discovery and loading.
Handles recursive loading of all cogs from the cogs/ directory and commands from legacy commands/ directory.
"""

import os
import importlib
import sys
from pathlib import Path
from tabulate import tabulate
from abby_core.observability.logging import setup_logging, logging
from discord.ext import commands
import inspect
import hashlib

# Import config for centralized path management
try:
    from abby_adapters.discord.config import BotConfig
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False

# Use centralized config or fall back to environment variable
if HAS_CONFIG:
    try:
        _config = BotConfig.from_env()
        WORKING_DIRECTORY = _config.paths.working_dir
    except Exception:
        WORKING_DIRECTORY = Path(os.getenv("WORKING_DIRECTORY", os.getcwd()))
else:
    WORKING_DIRECTORY = Path(os.getenv("WORKING_DIRECTORY", os.getcwd()))

FOLDER = str(WORKING_DIRECTORY)


class CommandHandler(commands.Cog):
    """Handles dynamic loading of cogs and commands from the filesystem."""
    
    def __init__(self, bot):
        self.bot = bot
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.last_reload_times = {}

    async def load_commands(self):  
        """Load all commands, cogs, and handlers."""
        loaded_items = []

        await self.load_cog_files(loaded_items)
        await self.load_handler_files(self.bot, loaded_items)
        await self.load_command_files(self.bot, loaded_items)

        headers = ["Status", "Category", "Item Name", "Message"]
        table = tabulate(loaded_items, headers=headers, tablefmt="simple_outline")
        self.logger.info(f"\n{table}")

    async def load_command_files(self, bot, loaded_items):
        """Load legacy command files from commands/ directory (deprecated, phase-out in progress)."""
        loaded_commands = 0
        commands_dir = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'commands')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        
        # Skip if commands directory doesn't exist
        if not os.path.exists(commands_dir):
            return
            
        for root, dirs, files in os.walk(commands_dir):
            for file_name in files:
                if file_name.endswith(".py") and file_name != "__init__.py":
                    module_name = file_name[:-3]
                    rel_path = os.path.relpath(os.path.join(root, module_name), start=adapters_root)
                    module_path = "abby_adapters." + rel_path.replace(os.sep, ".")
                    folder_name = os.path.basename(root)

                    if module_path in sys.modules:
                        module = importlib.reload(sys.modules[module_path])
                    else:
                        try:
                            module = importlib.import_module(module_path)
                        except Exception as e:
                            self.logger.warning(f"⚠️  [{module_name}] Error: {str(e)}")
                            continue

                    if hasattr(module, "setup") and callable(module.setup):
                        try:
                            if inspect.iscoroutinefunction(module.setup):
                                await module.setup(bot)
                            else:
                                module.setup(bot)
                            loaded_items.append(("✅", folder_name, module_name, "Success"))
                            loaded_commands += 1
                        except Exception as e:
                            loaded_items.append(("❌", folder_name, module_name, f"Error setting up command: {str(e)}"))

        if loaded_commands > 0:
            loaded_items.append(("🐰", "Commands", "Loaded", loaded_commands))
    
    async def load_handler_files(self, bot, loaded_items):
        """Load handler files from the handlers/ directory (deprecated, being migrated to cogs/)."""
        loaded_handlers = 0
        handlers_dir = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'handlers')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        
        # Skip if handlers directory doesn't exist
        if not os.path.exists(handlers_dir):
            return
        
        for file_name in os.listdir(handlers_dir):
            if file_name.endswith(".py") and file_name not in ["__init__.py", "command_loader.py"]:
                module_name = file_name[:-3]
                module_path = f"abby_adapters.discord.handlers.{module_name}"
                
                if module_path in sys.modules:
                    module = importlib.reload(sys.modules[module_path])
                else:
                    try:
                        module = importlib.import_module(module_path)
                    except Exception as e:
                        self.logger.warning(f"⚠️  [{module_name}] Error: {str(e)}")
                        continue
                
                if hasattr(module, "setup") and callable(module.setup):
                    try:
                        if inspect.iscoroutinefunction(module.setup):
                            await module.setup(bot)
                        else:
                            module.setup(bot)
                        loaded_items.append(("✅", "Handlers", module_name, "Success"))
                        loaded_handlers += 1
                    except Exception as e:
                        loaded_items.append(("❌", "Handlers", module_name, f"Error: {str(e)}"))
        
        if loaded_handlers > 0:
            loaded_items.append(("🐰", "Handlers", "Loaded", loaded_handlers))
    
    async def load_cog_files(self, loaded_items):
        """Load cog files from cogs/ directory recursively."""
        main_directory = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'cogs')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        cogs = []
        
        # Skip if cogs directory doesn't exist
        if not os.path.exists(main_directory):
            return
            
        for root, dirs, files in os.walk(main_directory):
            if root != main_directory:
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":
                        full_path = os.path.join(root, file)
                        category = os.path.basename(os.path.dirname(full_path))
                        item_name = os.path.basename(full_path)[:-3]

                        rel_path = os.path.relpath(full_path, start=adapters_root)
                        module_path = "abby_adapters." + rel_path[:-3].replace(os.sep, ".")
                        
                        try:
                            module = importlib.import_module(module_path)
                            if hasattr(module, "setup") and inspect.iscoroutinefunction(module.setup):
                                file_hash = hashlib.sha256(open(full_path, 'rb').read()).hexdigest()
                                self.last_reload_times[module_path] = file_hash
                                await self.bot.load_extension(module_path)
                                cogs.append(module_path)
                                loaded_items.append(("✅", category, item_name, "Success"))
                        except ImportError as ie:
                            loaded_items.append(("❌", category, item_name, f"ImportError: {str(ie)}"))
                        except Exception as e:
                            loaded_items.append(("❌", category, item_name, f"Error: {str(e)}"))
        
        loaded_items.append(("🐰", "Cogs", "Loaded", len(cogs)))

    async def reload_cogs(self, ctx):
        """Reload modified cog files (file watcher integration)."""
        main_directory = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'cogs')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        modified_cogs = []

        # Skip if cogs directory doesn't exist
        if not os.path.exists(main_directory):
            await ctx.send("Cogs directory not found.")
            return

        for root, dirs, files in os.walk(main_directory):
            if root != main_directory:
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":                
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, start=adapters_root)
                        module_path = "abby_adapters." + rel_path[:-3].replace(os.sep, ".")

                        try:
                            module = importlib.import_module(module_path)
                            if hasattr(module, "setup") and inspect.iscoroutinefunction(module.setup):
                                current_hash = hashlib.sha256(open(os.path.join(root, file), 'rb').read()).hexdigest()
                                last_hash = self.last_reload_times.get(module_path)
                                if last_hash == current_hash:
                                    continue
                                self.logger.info(f"Reloading {module_path} because it has changed.")
                                self.last_reload_times[module_path] = current_hash

                                await self.bot.reload_extension(module_path)
                                modified_cogs.append(("✅", module_path, "Success"))
                        except ImportError as e:
                            modified_cogs.append(("❌", module_path, f"ImportError: {str(e)}"))
                            self.logger.error(f'ImportError for {module_path}: {str(e)}')
                        except Exception as e:
                            modified_cogs.append(("❌", module_path, f"Error: {str(e)}"))
                            self.logger.error(f'Error for {module_path}: {str(e)}')

        headers = ["Status", "Cog", "Message"]
        print(tabulate(modified_cogs, headers=headers, tablefmt="simple_outline"))
        await ctx.send(f'Reloaded {len(modified_cogs)} cogs.')
