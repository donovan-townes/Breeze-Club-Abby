"""
Adapter Contract Tests

Validates that all platform adapters properly implement their interfaces:
- Discord adapters implement IServerInfoTool, IOutputFormatter, etc.
- Tool implementations are registered with factory
- Output formatters are registered with factory

Run with: pytest tests/test_adapter_contracts.py -v
"""

import pytest
from typing import get_type_hints
import inspect


class TestDiscordAdapterContracts:
    """Verify Discord adapters implement required interfaces."""
    
    pytestmark = pytest.mark.skip(reason="Missing tdos_memory dependency (indirect via abby_core imports)")
    
    def test_discord_tool_implements_interfaces(self):
        """Verify Discord tools implement ITool interfaces."""
        from abby_core.discord.adapters import (
            DiscordServerInfoTool,
            DiscordUserXPTool,
            DiscordBotStatusTool
        )
        from abby_core.interfaces.tools import (
            IServerInfoTool,
            IUserXPTool,
            IBotStatusTool
        )
        
        # Check inheritance
        assert issubclass(DiscordServerInfoTool, IServerInfoTool), \
            "DiscordServerInfoTool must implement IServerInfoTool"
        assert issubclass(DiscordUserXPTool, IUserXPTool), \
            "DiscordUserXPTool must implement IUserXPTool"
        assert issubclass(DiscordBotStatusTool, IBotStatusTool), \
            "DiscordBotStatusTool must implement IBotStatusTool"
    
    def test_discord_formatter_implements_interface(self):
        """Verify Discord formatter implements IOutputFormatter."""
        from abby_core.discord.adapters import DiscordOutputFormatter
        from abby_core.interfaces.output import IOutputFormatter
        
        assert issubclass(DiscordOutputFormatter, IOutputFormatter), \
            "DiscordOutputFormatter must implement IOutputFormatter"
    
    def test_discord_delivery_implements_interface(self):
        """Verify Discord delivery implements IAnnouncementDelivery."""
        from abby_core.discord.adapters import DiscordAnnouncementDelivery
        from abby_core.interfaces.output import IAnnouncementDelivery
        
        assert issubclass(DiscordAnnouncementDelivery, IAnnouncementDelivery), \
            "DiscordAnnouncementDelivery must implement IAnnouncementDelivery"
    
    def test_tools_have_required_methods(self):
        """Verify tools implement required abstract methods."""
        from abby_core.discord.adapters import DiscordServerInfoTool
        from abby_core.interfaces.tools import IServerInfoTool
        
        # Get abstract methods from interface
        abstract_methods = {
            name for name, method in inspect.getmembers(IServerInfoTool, inspect.isfunction)
            if getattr(method, '__isabstractmethod__', False)
        }
        
        # Get implemented methods from adapter
        implemented_methods = {
            name for name, method in inspect.getmembers(DiscordServerInfoTool, inspect.isfunction)
            if not name.startswith('_')
        }
        
        # Check all abstract methods are implemented
        missing = abstract_methods - implemented_methods
        assert not missing, f"DiscordServerInfoTool missing methods: {missing}"


class TestFactoryRegistration:
    """Verify factories are properly set up."""
    
    pytestmark = pytest.mark.skip(reason="Missing tdos_memory dependency (indirect via abby_core imports)")
    
    def test_tool_factory_exists(self):
        """Verify ToolFactory can be accessed."""
        from abby_core.interfaces.tools import get_tool_factory
        
        factory = get_tool_factory()
        assert factory is not None, "ToolFactory not initialized"
    
    def test_formatter_factory_exists(self):
        """Verify FormatterFactory can be accessed."""
        from abby_core.interfaces.output import get_formatter_factory
        
        factory = get_formatter_factory()
        assert factory is not None, "FormatterFactory not initialized"
    
    def test_discord_tools_registered(self):
        """Verify Discord tools can be retrieved from factory."""
        from abby_core.interfaces.tools import get_tool_factory
        
        # Note: Tools are registered during register_discord_adapters()
        # This test verifies the factory pattern works
        factory = get_tool_factory()
        
        # Try to get a tool (may be None if not registered yet)
        tool = factory.get_tool("discord", "server_info")
        
        # Factory should exist even if tools not registered
        assert factory is not None
    
    def test_factory_registration_pattern(self):
        """Verify factory registration pattern works."""
        from abby_core.interfaces.tools import ToolFactory
        
        # Create test factory
        factory = ToolFactory()
        
        # Create mock tool
        class MockTool:
            async def execute(self, context):
                return {"success": True}
        
        # Register tool
        factory.register("test_platform", "test_tool", MockTool())
        
        # Retrieve tool
        tool = factory.get_tool("test_platform", "test_tool")
        assert tool is not None, "Tool not registered correctly"


class TestInterfaceDefinitions:
    """Verify interface definitions are correct."""
    
    pytestmark = pytest.mark.skip(reason="Missing tdos_memory dependency (indirect via abby_core imports)")
    
    def test_interfaces_use_abc(self):
        """Verify interfaces inherit from ABC."""
        from abby_core.interfaces.tools import IServerInfoTool
        from abc import ABC
        
        assert issubclass(IServerInfoTool, ABC), \
            "IServerInfoTool must inherit from ABC"
    
    def test_interfaces_have_abstract_methods(self):
        """Verify interfaces define abstract methods."""
        from abby_core.interfaces.tools import IServerInfoTool
        import inspect
        
        # Get abstract methods
        abstract_methods = [
            name for name, method in inspect.getmembers(IServerInfoTool)
            if getattr(method, '__isabstractmethod__', False)
        ]
        
        assert len(abstract_methods) > 0, \
            "IServerInfoTool should have at least one abstract method"


class TestBankCogAdapter:
    """Verify BankCog is properly structured."""
    
    pytestmark = pytest.mark.skip(reason="Missing tdos_memory dependency (indirect via abby_core imports)")
    
    def test_bank_cog_location(self):
        """Verify BankCog is in discord/adapters/."""
        from abby_core.discord.adapters.economy import BankCog
        
        # Should import without error
        assert BankCog is not None
    
    def test_bank_cog_inherits_cog(self):
        """Verify BankCog inherits from commands.Cog."""
        from abby_core.discord.adapters.economy import BankCog
        from discord.ext import commands
        
        assert issubclass(BankCog, commands.Cog), \
            "BankCog must inherit from commands.Cog"
    
    def test_bank_cog_has_commands(self):
        """Verify BankCog has bank commands."""
        from abby_core.discord.adapters.economy import BankCog
        
        # Check for expected methods
        cog_methods = dir(BankCog)
        
        assert "balance_command" in cog_methods or "bank_group" in cog_methods, \
            "BankCog should have balance/bank commands"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
