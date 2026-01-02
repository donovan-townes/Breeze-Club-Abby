import logging
import coloredlogs
import requests
import json
import sys
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

class StructuredJSONLHandler(logging.Handler):
    """Custom handler that writes structured JSONL logs for machine parsing."""
    
    def __init__(self, filename: Path):
        super().__init__()
        self.filename = filename
        self.filename.parent.mkdir(parents=True, exist_ok=True)
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record as JSONL."""
        try:
            # Build structured log entry
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # Add phase if present
            if hasattr(record, 'phase'):
                log_entry["phase"] = record.phase
            
            # Add metrics if present
            if hasattr(record, 'metrics'):
                log_entry["metrics"] = record.metrics
            
            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.format(record)
            
            # Append to JSONL file
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        except Exception:
            self.handleError(record)


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
    root_logger.setLevel(logging.INFO)
    
    # Create logs directory if it doesn't exist (cross-platform)
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Machine-readable JSONL log file (primary output for telemetry)
    jsonl_log_file = log_dir / 'abby.jsonl'
    jsonl_handler = StructuredJSONLHandler(jsonl_log_file)
    jsonl_handler.setLevel(logging.INFO)
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
