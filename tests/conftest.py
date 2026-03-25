"""
Pytest Configuration and Shared Fixtures

Provides shared test fixtures and configuration for all test modules.
"""

import pytest
import sys
from pathlib import Path

# Add abby_core to Python path
ABBY_ROOT = Path(__file__).parent.parent
if str(ABBY_ROOT) not in sys.path:
    sys.path.insert(0, str(ABBY_ROOT))


@pytest.fixture(scope="session")
def abby_root():
    """Path to Abby root directory."""
    return ABBY_ROOT


@pytest.fixture(scope="session")
def core_path():
    """Path to abby_core directory."""
    return ABBY_ROOT / "abby_core"


@pytest.fixture
def mock_bot():
    """Mock Discord bot for testing (if needed)."""
    class MockBot:
        def __init__(self):
            self.user = MockUser()
            self.guilds = []
        
        def get_guild(self, guild_id):
            return None
        
        def get_channel(self, channel_id):
            return None
    
    class MockUser:
        def __init__(self):
            self.id = 123456789
            self.name = "TestBot"
    
    return MockBot()


@pytest.fixture
def test_guild_id():
    """Test guild ID."""
    return 999999999


@pytest.fixture
def test_user_id():
    """Test user ID."""
    return 111111111


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "architecture: tests for architecture compliance"
    )
    config.addinivalue_line(
        "markers", "adapters: tests for adapter contracts"
    )
    config.addinivalue_line(
        "markers", "state: tests for state management"
    )
    config.addinivalue_line(
        "markers", "integration: integration tests requiring database"
    )
