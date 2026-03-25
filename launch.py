"""
Abby Discord Bot Launcher
Launches the Discord adapter from the new abby-adapters structure.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add abby-core to Python path
ABBY_ROOT = Path(__file__).parent
sys.path.insert(0, str(ABBY_ROOT))

# Load environment variables from .env file
# Priority: /srv/tserver/compose/abby.env (production mount) -> .env in current dir (dev)
env_file_prod = "/srv/tserver/compose/abby.env"
env_file_dev = ABBY_ROOT / ".env"
if os.path.exists(env_file_prod):
    load_dotenv(env_file_prod)
elif os.path.exists(env_file_dev):
    load_dotenv(env_file_dev)


def _parse_mode(argv) -> str:
    """Return runtime mode from CLI flags (defaults to prod)."""
    if "--dev" in argv:
        return "dev"
    for arg in argv:
        if arg.startswith("--mode="):
            return arg.split("=", 1)[1].strip() or "prod"
    return os.getenv("ABBY_MODE", "prod")


# Below is commented out for DEV ONLY because tdos_intelligence is located within abby_bot now. But
# tdos_intelligence will be moved out of this, so we keep this here for deployment until
# this becomes a package that can be installed via pip.

# Add tdos libs to Python path for tdos_intelligence and other shared libraries
# Uncomment this when tdos_intelligence is moved out of abby_bot but not yet a pip package.

# TDOS_LIBS = ABBY_ROOT.parent.parent / "libs"
# sys.path.insert(0, str(TDOS_LIBS))



# Launch Discord adapter
if __name__ == "__main__":
    mode = _parse_mode(sys.argv[1:])
    os.environ["ABBY_MODE"] = mode

    # Automatically use dev database when --dev mode is enabled
    if mode == "dev":
        # Use dev database unless explicitly overridden by MONGODB_DB_DEV env var
        dev_db = os.getenv("MONGODB_DB_DEV", "Abby_Database_Dev")
        os.environ["MONGODB_DB"] = dev_db
    # In production mode, NEVER override MONGODB_DB with MONGODB_DB_DEV
    # The production environment should have MONGODB_DB set correctly
    # Clear any MONGODB_DB_DEV that may have leaked from .env files
    if mode == "prod" and "MONGODB_DB_DEV" in os.environ:
        del os.environ["MONGODB_DB_DEV"]

    from abby_core.discord import main as discord_main
    discord_main.run(mode=mode)
