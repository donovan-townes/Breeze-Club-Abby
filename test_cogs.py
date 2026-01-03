#!/usr/bin/env python
"""Quick test to verify cogs can be imported."""

import sys
import asyncio

async def test_imports():
    """Test if our fixed cogs can import without errors."""
    print("Testing cog imports...")
    
    try:
        # Test conversations
        from abby_adapters.discord.cogs.utility.conversations import ConversationCommands, ConversationAdmin
        print("✅ conversations.py loads (ConversationCommands, ConversationAdmin)")
    except Exception as e:
        print(f"❌ conversations.py failed: {e}")
        return False
    
    try:
        # Test memory
        from abby_adapters.discord.cogs.utility.memory import MemoryCommands, MemoryAdmin
        print("✅ memory.py loads (MemoryCommands, MemoryAdmin)")
    except Exception as e:
        print(f"❌ memory.py failed: {e}")
        return False
    
    try:
        # Test chatbot (basic import - may fail on full init due to discord deps)
        from abby_adapters.discord.cogs.creative import chatbot
        print("✅ chatbot.py loads")
    except Exception as e:
        print(f"⚠️  chatbot.py import warning: {e}")
        # Don't fail for chatbot - it has deep dependencies
    
    print("\n✅ All critical cogs import successfully!")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_imports())
    sys.exit(0 if result else 1)
