"""
Abby Discord Bot Launcher
Launches the Discord adapter from the new abby-adapters structure.
"""
import sys
from pathlib import Path

# Add abby-core to Python path
ABBY_ROOT = Path(__file__).parent
sys.path.insert(0, str(ABBY_ROOT))

# Launch Discord adapter
if __name__ == "__main__":
    from abby_adapters.discord import main as discord_main
    discord_main.run()
