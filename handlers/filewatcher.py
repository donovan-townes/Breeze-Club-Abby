import os
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import importlib
import sys
from utils.log_config import logging, setup_logging
from discord.ext import commands,tasks
import asyncio
import schedule


 
setup_logging()
logger = logging.getLogger(__name__)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, folder_path, bot):
        self.folder_path = folder_path
        self.bot = bot
        self.file_hashes = {}
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                self.file_hashes[file_path] = self.get_file_hash(file_path)

    def get_file_hash(self, file_path, block_size=65536):
        """Calculate the hash value of a file."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(block_size)
                if not data:
                    break
                hasher.update(data)
        return hasher.hexdigest()

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.py') or '__pycache__' in event.src_path:
            return
    
        file_path = event.src_path
        file_hash = self.get_file_hash(file_path)
        if self.file_hashes.get(file_path) != file_hash:
            # get name of file
            modified_file_name = os.path.basename(file_path)
            self.file_hashes[file_path] = file_hash
            
            # Reload/load the commands using the provided bot
            try:
                # get folder
                folder_name = os.path.basename(os.path.dirname(file_path))
                # get module name
                module_name = modified_file_name[:-3]
                module_path = f"Commands.{os.path.join(folder_name, module_name).replace(os.sep, '.')}"

                if module_path in sys.modules:
                    module = importlib.reload(sys.modules[module_path])
                else:
                    try:
                        module = importlib.import_module(module_path)
                    except Exception as e:
                        # throw error
                        logger.warning(f"[👁‍🗨] Error Loading Module: {str(e)}")
                        return
                if hasattr(module, "setup") and callable(module.setup):
                    try:
                        logger.info(f"[👁‍🗨] Reloading {module_name}")
                        self.bot.remove_command(module_name)
                        module.setup(self.bot)

                    except Exception as e:
                        logger.warning(f"[👁‍🗨] Error setting up command module: {str(e)}")
                        return
            except Exception as e:
                logger.warning(f"[👁‍🗨] Error Loading Modules: {str(e)}")
                return
def watch_files(bot):
    folder_path = "/home/Abby_BreezeClub/Discord/Commands"  # Replace with your desired folder path

    event_handler = FileChangeHandler(folder_path, bot)
    observer = Observer()
    observer.schedule(event_handler, path=folder_path, recursive=True)
    observer.start()

    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

class FileWatcherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.folder_path = "/home/Abby_BreezeClub/Discord/Commands"  # Replace with your desired folder path
        self.start_watching()
        
  

    def start_watching(self):
        logger.info(f"[👁‍🗨] Watching {self.folder_path}")
        event_handler = FileChangeHandler(self.folder_path, self.bot)
        observer = Observer()
        observer.schedule(event_handler, path=self.folder_path, recursive=True)
        observer.start()
        try:
            observer.join()
        except KeyboardInterrupt:
            observer.stop()

        observer.join()

    async def cog_unload(self):
        # Stop the observer when the cog is unloaded
        await self.observer.stop()
        await self.observer.join()

# async def setup(bot):
#     await bot.add_cog(FileWatcherCog(bot))
