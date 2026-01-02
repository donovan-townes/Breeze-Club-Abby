import logging
import coloredlogs
import requests
import json
import sys
from pathlib import Path

webhook_url = "https://discord.com/api/webhooks/your_webhook_url_here" # Move to config in future

# Flag to ensure setup_logging only runs once
_logging_configured = False

def setup_logging():
    global _logging_configured
    
    # Only configure once - prevent duplicate handlers
    if _logging_configured:
        return
    
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

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Create logs directory if it doesn't exist (cross-platform)
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'abby.log'
    
    # Create a file handler with UTF-8 encoding to support emojis
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # Explicit level for file handler
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)
    
    # Log startup message to verify file handler is working
    startup_logger = logging.getLogger('abby.startup')
    startup_logger.info(f"Abby logging initialized - writing to {log_file}")

    # Define the colors for the log levels
    level_styles = {
        'debug': {'color': 'blue'},
        'info': {},
        'warning': {'color': 'yellow'},
        'error': {'color': 'red'},
        'critical': {'color': 'red', 'bold': True},
    }
    
    # Set up colored console logs (for local dev)
    # Only use coloredlogs if not running as a service (has a tty)
    try:
        if sys.stdout.isatty():
            coloredlogs.install(level='INFO', fmt=log_format, level_styles=level_styles, logger=root_logger)
        else:
            # Running as service - use basic console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(log_format))
            root_logger.addHandler(console_handler)
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        # Fallback to basic console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)
    
    # Mark as configured
    _logging_configured = True

    
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
