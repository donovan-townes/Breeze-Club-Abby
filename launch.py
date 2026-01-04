"""
Abby Discord Bot Launcher
Launches the Discord adapter from the new abby-adapters structure.
"""
import os
import sys
from pathlib import Path

# Add abby-core to Python path
ABBY_ROOT = Path(__file__).parent
sys.path.insert(0, str(ABBY_ROOT))


def _parse_mode(argv) -> str:
    """Return runtime mode from CLI flags (defaults to prod)."""
    if "--dev" in argv:
        return "dev"
    for arg in argv:
        if arg.startswith("--mode="):
            return arg.split("=", 1)[1].strip() or "prod"
    return os.getenv("ABBY_MODE", "prod")


# Launch Discord adapter
if __name__ == "__main__":
    mode = _parse_mode(sys.argv[1:])
    os.environ["ABBY_MODE"] = mode

    # Optional: allow DB override for dev via env
    if mode == "dev" and os.getenv("MONGODB_DB_DEV"):
        os.environ["MONGODB_DB"] = os.getenv("MONGODB_DB_DEV")

    from abby_adapters.discord import main as discord_main
    discord_main.run(mode=mode)
