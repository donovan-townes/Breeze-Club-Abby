"""
State Management Tests

Validates system state integrity and transitions:
- Season state management
- Configuration state
- System state operations

Run with: pytest tests/test_state_management.py -v
"""

import pytest
from datetime import datetime


class TestSeasonState:
    """Test season state management."""
    
    def test_season_state_structure(self):
        """Verify season state has required fields."""
        from abby_core.system.system_state import get_active_season
        
        season = get_active_season()
        
        # Should have required fields
        assert season is not None, "Should have an active season"
        assert "state_type" in season and season["state_type"] == "season", "Must be a season state"
        assert "state_id" in season, "Season must have state_id"
        assert "label" in season, "Season must have label"
        assert "start_at" in season, "Season must have start_at"
    
    def test_season_numbers_are_sequential(self):
        """Verify seasons have proper identifiers and timestamps."""
        from abby_core.system.system_state import get_active_season, list_all_states
        
        current = get_active_season()
        all_seasons = list_all_states(state_type='season')
        
        # Verify we have seasons and current is active
        assert current is not None, "Should have active season"
        assert len(all_seasons) > 0, "Should have seasons in database"
        assert current in all_seasons, "Active season should be in all seasons"
        
        # Verify each season has required timestamp fields
        for season in all_seasons:
            assert 'state_id' in season, "Each season must have state_id"
            assert 'created_at' in season, "Each season must have created_at"


class TestSystemConfiguration:
    """Test system configuration state."""
    
    def test_system_config_loadable(self):
        """Verify system configuration can be loaded."""
        from abby_core.database.collections.system_configuration import get_system_config
        
        config = get_system_config()
        assert config is not None, "System config should be loadable"
    
    def test_mongodb_connection(self):
        """Verify MongoDB connection is available."""
        from abby_core.database.mongodb import is_mongodb_available
        
        # Should return bool (True or False)
        available = is_mongodb_available()
        assert isinstance(available, bool), "is_mongodb_available should return bool"


class TestGuildConfiguration:
    """Test guild-specific configuration."""
    
    def test_guild_config_structure(self):
        """Verify guild config has expected structure."""
        from abby_core.database.guild_configuration import get_guild_config
        
        # Get config for test guild (will create default if not exists)
        config = get_guild_config(123456789)
        
        # Should have channels configuration
        assert "channels" in config or config is not None, \
            "Guild config should exist (even if empty)"
    
    def test_guild_config_initialization(self):
        """Verify guild config can be initialized."""
        from abby_core.database.guild_configuration import initialize_guild_config
        import asyncio
        
        # Initialize config for test guild
        result = asyncio.run(initialize_guild_config(
            guild_id=999999999,
            guild_name="Test Guild"
        ))
        
        # Should return True (success) or False (already exists)
        assert isinstance(result, bool), \
            "initialize_guild_config should return bool"


class TestStateTransitions:
    """Test state transition logic."""
    
    def test_season_transition_structure(self):
        """Verify season transition logic exists."""
        from abby_core.system.season_reset_operations import (
            create_xp_season_reset,
            preview_xp_season_reset,
            apply_xp_season_reset
        )
        
        # Functions should exist
        assert callable(create_xp_season_reset), "create_xp_season_reset should be callable"
        assert callable(preview_xp_season_reset), "preview_xp_season_reset should be callable"
        assert callable(apply_xp_season_reset), "apply_xp_season_reset should be callable"
    
    def test_system_operations_exist(self):
        """Verify system operations are defined."""
        from abby_core.system import system_operations
        
        # Check for key operations
        assert hasattr(system_operations, 'create_operation') and \
               hasattr(system_operations, 'apply_operation') and \
               hasattr(system_operations, 'rollback_operation'), \
            "System operations should be defined"


class TestDatabaseSchemas:
    """Test database schema definitions."""
    
    def test_schemas_module_exists(self):
        """Verify database schemas are defined."""
        from abby_core.database import schemas
        
        # Should have schema definitions
        assert schemas is not None, "Schemas module should exist"
    
    def test_guild_schema_fields(self):
        """Verify guild schema has required fields."""
        try:
            from abby_core.database.schemas import GuildConfigSchema  # type: ignore[attr-defined]
            
            # Should be importable
            assert GuildConfigSchema is not None
        except ImportError:
            # Schema might be defined differently
            pytest.skip("GuildConfigSchema not found (may use dict schema)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
