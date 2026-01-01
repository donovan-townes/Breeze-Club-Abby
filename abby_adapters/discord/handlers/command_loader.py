import os
import importlib
import sys
from pathlib import Path
from tabulate import tabulate
from abby_core.observability.logging import setup_logging,logging
import discord
from discord.ext import commands, tasks
import inspect
import asyncio 
import time
import hashlib


# Use environment variable for working directory (Windows-compatible)
WORKING_DIRECTORY = Path(os.getenv("WORKING_DIRECTORY", os.getcwd()))
FOLDER = str(WORKING_DIRECTORY)

class CommandHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.last_reload_times = {}

    async def load_commands(self):  
        loaded_items = []  # List to store the loaded commands and cogs

        await self.load_cog_files(loaded_items)
        await self.load_handler_files(self.bot, loaded_items)
        await self.load_command_files(self.bot, loaded_items)

        headers = ["Status", "Category", "Item Name", "Message"]
        table = tabulate(loaded_items, headers=headers, tablefmt="simple_outline")
        self.logger.info(f"\n{table}")

    async def load_command_files(self, bot, loaded_items):
        loaded_commands = 0  # Initialize a variable to count the loaded commands
        commands_dir = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'commands')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        for root, dirs, files in os.walk(commands_dir):
            for file_name in files:
                if file_name.endswith(".py") and file_name != "__init__.py":
                    module_name = file_name[:-3]  # Remove the .py extension
                    # Convert file path to module path (relative to adapter root)
                    rel_path = os.path.relpath(os.path.join(root, module_name), start=adapters_root)
                    module_path = "abby_adapters." + rel_path.replace(os.sep, ".")
                    folder_name = os.path.basename(root)

                    # Check if the module is already loaded
                    if module_path in sys.modules:
                        module = importlib.reload(sys.modules[module_path])
                    else:
                        try:
                            module = importlib.import_module(module_path)
                        except Exception as e:
                            self.logger.warning(f"⚠️  [{module_name}] Error: {str(e)}")
                            continue

                    # Check if its a command
                    if hasattr(module, "setup") and callable(module.setup):
                        # self.logger.info(f"[🐰] Loading {module_name} command")
                        try:
                            # Check if setup is async and await if necessary
                            if inspect.iscoroutinefunction(module.setup):
                                await module.setup(bot)
                            else:
                                module.setup(bot)
                            loaded_items.append(("✅", folder_name, module_name, "Success"))
                            # self.logger.info(f"[🐰] Loading {module_name} command")
                            loaded_commands += 1
                        except Exception as e:
                            loaded_items.append(("❌", folder_name, module_name, f"Error setting up command: {str(e)}"))

                    else:
                        # self.logger.warning(f"⚠️  [{module_name}] is neither a cog nor a command.")
                        pass

        # Append the number of loaded commands to the list
        loaded_items.append(("🐰", "Commands", "Loaded", loaded_commands))
    
    async def load_handler_files(self, bot, loaded_items):
        """Load handler files from the handlers/ directory"""
        loaded_handlers = 0
        handlers_dir = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'handlers')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        
        for file_name in os.listdir(handlers_dir):
            if file_name.endswith(".py") and file_name not in ["__init__.py", "command_loader.py"]:
                module_name = file_name[:-3]
                module_path = f"abby_adapters.discord.handlers.{module_name}"
                
                # Check if the module is already loaded
                if module_path in sys.modules:
                    module = importlib.reload(sys.modules[module_path])
                else:
                    try:
                        module = importlib.import_module(module_path)
                    except Exception as e:
                        self.logger.warning(f"⚠️  [{module_name}] Error: {str(e)}")
                        continue
                
                # Check if it has setup function
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
        
        # Append the number of loaded handlers to the list
        if loaded_handlers > 0:
            loaded_items.append(("🐰", "Handlers", "Loaded", loaded_handlers))
    
    async def load_cog_files(self, loaded_items):
        main_directory = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'cogs')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        cogs = []
        for root, dirs, files in os.walk(main_directory):
            if root != main_directory:
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":
                        full_path = os.path.join(root, file)

                        # Extract the category and item name
                        category = os.path.basename(os.path.dirname(full_path))
                        item_name = os.path.basename(full_path)[:-3]  # Remove the .py extension

                        # Construct module path correctly
                        rel_path = os.path.relpath(full_path, start=adapters_root)
                        module_path = "abby_adapters." + rel_path[:-3].replace(os.sep, ".")
                        
                        try:
                            module = importlib.import_module(module_path)
                            if hasattr(module, "setup") and inspect.iscoroutinefunction(module.setup):
                                # Calculate hash of the file
                                file_hash = hashlib.sha256(open(full_path, 'rb').read()).hexdigest()
                                self.last_reload_times[module_path] = file_hash
                                await self.bot.load_extension(module_path)
                                cogs.append(module_path)
                                loaded_items.append(("✅", category, item_name, "Success"))  # Use category and item_name
                        except ImportError as ie:
                            loaded_items.append(("❌", category, item_name, f"ImportError: {str(ie)}"))
                        except Exception as e:
                            loaded_items.append(("❌", category, item_name, f"Error: {str(e)}"))
        # Append the number of loaded cogs to the list
        loaded_items.append(("🐰", "Cogs", "Loaded", len(cogs)))

    async def reload_cogs(self, ctx):
        main_directory = str(WORKING_DIRECTORY / 'abby_adapters' / 'discord' / 'cogs')
        adapters_root = str(WORKING_DIRECTORY / 'abby_adapters')
        modified_cogs = []

   
        for root, dirs, files in os.walk(main_directory):
            if root != main_directory:
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":                
                        full_path = os.path.join(root, file)
                        # Construct module path correctly
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

        # Print the table of modified cogs
        headers = ["Status", "Cog", "Message"]
        print(tabulate(modified_cogs, headers=headers, tablefmt="simple_outline"))

        # Notify the command invoker about the reloaded cogs
        await ctx.send(f'Reloaded {len(modified_cogs)} cogs.')

