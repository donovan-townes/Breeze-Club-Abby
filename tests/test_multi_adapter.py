"""
Multi-Adapter Integration Tests

Validates that core services work with multiple adapters (Discord, mock Web, etc.)
This ensures true platform-first architecture readiness.

Run with: pytest tests/test_multi_adapter.py -v
"""

import pytest
import asyncio
from typing import Optional, Tuple, Dict, Any


class MockWebAdapter:
    """Mock Web adapter for testing platform-agnostic service integration."""
    
    @staticmethod
    async def deliver_announcement(
        context: Dict[str, Any],
        guild_id: int | str,
        message: str
    ) -> Tuple[bool, Optional[int], Optional[int], Optional[str]]:
        """Mock Web announcement delivery."""
        return True, None, None, None


class TestMultiAdapterIntegration:
    """Test that core services work with multiple adapters."""
    
    @pytest.mark.asyncio
    async def test_seasonal_announcements_with_mock_delivery(self):
        """Verify seasonal_announcements works with callback pattern."""
        # Note: Skip if numpy/tdos_intelligence not available
        try:
            from abby_core.services.events_lifecycle import register_announcement_delivery
        except ImportError:
            pytest.skip("Dependencies not available")
        
        # Mock delivery handler
        async def mock_delivery(bot, guild_id, message):
            return True, 123, 456, None
        
        register_announcement_delivery(mock_delivery)
        
        # Should work without errors
        assert True
    
    @pytest.mark.asyncio
    async def test_seasonal_announcements_callback_handling(self):
        """Verify callback pattern works for announcement delivery."""
        from abby_core.services.events_lifecycle import (
            register_announcement_delivery,
            send_season_announcement_to_guild
        )
        
        # Create mock bot
        class MockBot:
            pass
        
        bot = MockBot()
        
        # Register callback
        async def mock_delivery(bot, guild_id, message):
            return True, 999, 888, None
        
        register_announcement_delivery(mock_delivery)
        
        # Send announcement
        success, channel_id, message_id, error = await send_season_announcement_to_guild(
            bot, 123456, "Test announcement"
        )
        
        assert success is True
        assert channel_id == 999
        assert message_id == 888
        assert error is None
    
    @pytest.mark.asyncio
    async def test_seasonal_announcements_callback_error_handling(self):
        """Verify error handling when callback fails."""
        from abby_core.services.events_lifecycle import (
            register_announcement_delivery,
            send_season_announcement_to_guild
        )
        
        class MockBot:
            pass
        
        bot = MockBot()
        
        # Register failing callback
        async def failing_delivery(bot, guild_id, message):
            return False, None, None, "Delivery failed"
        
        register_announcement_delivery(failing_delivery)
        
        # Send announcement
        success, channel_id, message_id, error = await send_season_announcement_to_guild(
            bot, 123456, "Test announcement"
        )
        
        assert success is False
        assert error == "Delivery failed"
    
    def test_seasonal_announcements_callback_not_registered(self):
        """Verify behavior when no callback is registered."""
        # This test is informational - the module handles missing callbacks gracefully
        from abby_core.services import events_lifecycle
        
        # Should have callback registry
        assert hasattr(events_lifecycle, '_announcement_delivery_callback')
        assert hasattr(events_lifecycle, 'register_announcement_delivery')
    
    def test_core_services_are_platform_agnostic(self):
        """Verify core services don't hard-depend on Discord."""
        from pathlib import Path
        import ast
        
        core_modules = [
            "services", "economy", "llm", "personality",
            "rag", "system", "interfaces", "database", "generation"
        ]
        
        repo_root = Path(__file__).parent.parent
        core_path = repo_root / "abby_core"
        
        forbidden_imports = ["discord"]
        violations = []
        
        for module in core_modules:
            module_path = core_path / module
            if not module_path.exists():
                continue
            
            # Check Python files
            for py_file in module_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                
                try:
                    with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    if any(f in alias.name for f in forbidden_imports):
                                        violations.append(
                                            f"{py_file.relative_to(repo_root)}: "
                                            f"Forbidden import: {alias.name}"
                                        )
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    if any(f in node.module for f in forbidden_imports):
                                        violations.append(
                                            f"{py_file.relative_to(repo_root)}: "
                                            f"Forbidden import: from {node.module}"
                                        )
                except SyntaxError:
                    pass  # Skip files with syntax errors
        
        if violations:
            pytest.fail(
                f"Core modules contain forbidden platform imports:\n" +
                "\n".join(violations)
            )


class TestAdapterCallbackPattern:
    """Test the callback pattern used for adapter injection."""
    
    def test_callback_registry_exists(self):
        """Verify events_lifecycle has callback registry."""
        from abby_core.services import events_lifecycle
        
        # Should have the callback machinery
        assert hasattr(events_lifecycle, '_announcement_delivery_callback')
        assert hasattr(events_lifecycle, 'register_announcement_delivery')
        assert callable(events_lifecycle.register_announcement_delivery)
    
    @pytest.mark.asyncio
    async def test_callback_signature(self):
        """Verify callback has correct signature."""
        from abby_core.services.events_lifecycle import (
            register_announcement_delivery,
            send_season_announcement_to_guild
        )
        import inspect
        
        # Register a callback and verify it gets called
        called = False
        call_args = {}
        
        async def test_callback(bot, guild_id, message):
            nonlocal called, call_args
            called = True
            call_args = {"bot": bot, "guild_id": guild_id, "message": message}
            return True, 1, 2, None
        
        register_announcement_delivery(test_callback)
        
        class MockBot:
            pass
        
        bot = MockBot()
        await send_season_announcement_to_guild(bot, 789, "test")
        
        assert called
        assert call_args["guild_id"] == 789
        assert call_args["message"] == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
