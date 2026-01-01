import logging
import coloredlogs
import requests
import json
import sys
from pathlib import Path

webhook_url = "https://discord.com/api/webhooks/your_webhook_url_here" # Move to config in future

def setup_logging():
    # Fix Windows console encoding for emoji support
    if sys.platform == 'win32':
        try:
            # Try to set UTF-8 encoding for stdout/stderr
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, Exception):
            # If reconfigure not available or fails, install a safe handler
            pass
    
    log_format = (
        "[%(asctime)s] [%(levelname)s] - [%(name)s]: %(message)s"
    )

    # Define the colors for the log levels
    level_styles = {
        'debug': {'color': 'blue'},
        'info': {},
        'warning': {'color': 'yellow'},
        'error': {'color': 'red'},
        'critical': {'color': 'red', 'bold': True},
    }
    
    # Set up the colored logs with error handling for encoding issues
    try:
        coloredlogs.install(level='INFO', fmt=log_format, level_styles=level_styles)
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Fallback to basic logging if colored logs fail
        logging.basicConfig(level=logging.INFO, format=log_format)
    

    # Get the root logger
    root_logger = logging.getLogger()
    # Check if a file handler already exists and add it if not
    if not any(isinstance(handler, logging.FileHandler) for handler in root_logger.handlers):
        # Create logs directory if it doesn't exist (cross-platform)
        log_dir = Path(__file__).parent.parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'logfile.log'
        
        # Create a file handler with UTF-8 encoding to support emojis
        file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)

    # Set the logging level
    root_logger.setLevel(logging.INFO)

    
setup_logging()
logger = logging.getLogger(__name__)

async def error_webhook_message(content):
    data = {
        "content": content
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = await requests.post(webhook_url, data=json.dumps(data), headers=headers)
    if response.status_code != 204:
        logger.info("Failed to send webhook message")
