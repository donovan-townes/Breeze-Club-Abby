"""Utility helpers for configuration loading."""

import os
from dotenv import load_dotenv

# Ensure environment variables from .env are available
load_dotenv()


def getenv_bool(key: str, default: str = "false") -> bool:
    """Return boolean environment variable value with fallback."""
    return os.getenv(key, default).lower() == "true"


def getenv_int(key: str, default: str) -> int:
    """Return integer environment variable value with fallback."""
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return int(default)


def getenv_float(key: str, default: str) -> float:
    """Return float environment variable value with fallback."""
    try:
        return float(os.getenv(key, default))
    except (ValueError, TypeError):
        return float(default)
