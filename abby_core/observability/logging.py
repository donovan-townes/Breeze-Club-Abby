import logging
from logging.handlers import RotatingFileHandler
import coloredlogs
import requests
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import uuid

webhook_url = "https://discord.com/api/webhooks/your_webhook_url_here" # Move to config in future

# Flag to ensure setup_logging only runs once
_logging_configured = False

# Startup phase tracking
STARTUP_PHASES = {
    "INIT": "Initialization",
    "CORE_SERVICES": "Core Services",
    "COG_LOADING": "Cog Loading",
    "CONNECTION": "Discord Connection",
    "BACKGROUND_TASKS": "Background Tasks",
    "COMPLETE": "Startup Complete"
}

class StructuredJSONLFormatter(logging.Formatter):
    """Formatter that emits structured JSONL records for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, 'phase'):
            log_entry["phase"] = record.phase

        if hasattr(record, 'metrics'):
            log_entry["metrics"] = record.metrics

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def log_startup_phase(logger: logging.Logger, phase: str, message: str, metrics: dict = None):
    """Log a startup phase with structured metadata."""
    extra = {'phase': phase}
    if metrics:
        extra['metrics'] = metrics
    logger.info(message, extra=extra)

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
    
    # Check for DEBUG environment variable to enable debug logging
    debug_mode = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
    log_level = logging.DEBUG if debug_mode else logging.INFO
    root_logger.setLevel(log_level)
    
    # Suppress verbose third-party library logs (even in DEBUG mode)
    logging.getLogger('discord.client').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    logging.getLogger('pymongo.connection').setLevel(logging.WARNING)
    logging.getLogger('pymongo.serverSelection').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Create logs directory (prefer configured LOG_PATH, fallback to repository logs)
    configured_log_path = os.getenv("LOG_PATH", "").strip()
    if configured_log_path:
        log_dir = Path(configured_log_path)
    else:
        log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    # JSONL rotation controls (align with Docker defaults where possible)
    max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "3"))

    # Machine-readable JSONL log file (primary output for telemetry)
    jsonl_log_file = log_dir / 'abby.jsonl'
    jsonl_handler = RotatingFileHandler(
        jsonl_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    jsonl_handler.setFormatter(StructuredJSONLFormatter())
    jsonl_handler.setLevel(log_level)
    root_logger.addHandler(jsonl_handler)
    
    # Log startup message to verify handler is working
    startup_logger = logging.getLogger('abby.startup')
    startup_logger.info(f"Abby logging initialized - jsonl: {jsonl_log_file}")

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
