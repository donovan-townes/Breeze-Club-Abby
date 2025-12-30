import logging
import coloredlogs
import requests
import json
from pathlib import Path

webhook_url = "https://discord.com/api/webhooks/1131233420245205003/F648Wp93ra02PDOvEA4A4QgzWHeOrZyxYAWVhBJj1XejgSBDJtrgh0HwvQ1UrcJKx0_7"

def setup_logging():
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
    
    # Set up the colored logs
    coloredlogs.install(level='INFO', fmt=log_format, level_styles=level_styles)
    

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
