"""
Regression tests for ISSUE-005: NUDGE_CHANNEL_ID configuration validation.

Tests verify that:
1. When NUDGE_ENABLED=true but NUDGE_CHANNEL_ID is unconfigured, startup should fail OR warning is rate-limited
2. When NUDGE_ENABLED=false, no warnings should be logged regardless of NUDGE_CHANNEL_ID
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import logging
from io import StringIO


class TestNudgeChannelConfiguration(unittest.TestCase):
    """Test nudge feature configuration validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger("abby_core.discord.cogs.community.nudge_handler")
        self.handler = logging.StreamHandler(StringIO())
        self.logger.addHandler(self.handler)

    def tearDown(self):
        """Clean up after tests."""
        self.logger.handlers.clear()

    @patch("abby_core.discord.cogs.community.nudge_handler.config")
    def test_nudge_enabled_without_channel_raises_validation_error(self, mock_config):
        """
        REQUIREMENT: When NUDGE_ENABLED=true but NUDGE_CHANNEL_ID=0,
        initialization should raise ConfigurationError or similar.
        
        This prevents silent failures and ensures operators fix config upfront.
        """
        from abby_core.discord.cogs.community.nudge_handler import NudgeHandler
        
        # Mock config with nudge enabled but no channel
        mock_config.features.nudge_enabled = True
        mock_config.timing.nudge_interval_hours = 24
        mock_config.channels.nudge_channel = 0  # Invalid channel ID
        
        # Mock Discord bot/context
        mock_bot = Mock()
        mock_bot.get_cog = Mock(return_value=None)
        
        # Test: Initialization with missing channel should fail loudly
        with self.assertRaises(ValueError) as ctx:
            handler = NudgeHandler(mock_bot)
        
        # Verify error message mentions the issue
        self.assertIn("NUDGE_ENABLED", str(ctx.exception))
        self.assertIn("NUDGE_CHANNEL_ID", str(ctx.exception))
        
    @patch("abby_core.config.features.FEATURE_NUDGE_ENABLED", False)
    @patch("abby_core.discord.config.BotConfig.nudge_channel_id", 0)
    async def test_nudge_disabled_does_not_warn_about_missing_channel(self):
        """
        REQUIREMENT: When NUDGE_ENABLED=false, the nudge feature is completely
        disabled and should not log warning about missing NUDGE_CHANNEL_ID.
        """
        from abby_core.discord.cogs.community.nudge_handler import NudgeHandler
        
        # Mock Discord bot and dependencies
        mock_bot = Mock()
        mock_bot.get_cog = Mock(return_value=None)
        
        # Create handler (should not fail even with missing channel when disabled)
        with patch.object(NudgeHandler, "nudge_users_tick"):
            handler = NudgeHandler(mock_bot)
            # Handler creation should succeed when feature is disabled
            self.assertIsNotNone(handler)

    @patch("abby_core.config.features.FEATURE_NUDGE_ENABLED", True)
    @patch("abby_core.discord.config.BotConfig.nudge_channel_id", 123456789)
    async def test_nudge_warning_not_repeated_per_user(self):
        """
        REQUIREMENT: If nudge_tick runs and warning is logged, it should NOT
        be duplicated per inactive user. Should be single warning per execution,
        not per user.
        
        Root cause: Current code warns once per inactive user per tick (spammy).
        Fix: Warning should be logged once max per tick, or not at all if channel is valid.
        """
        from abby_core.discord.cogs.community.nudge_handler import NudgeHandler
        
        # Set up logging capture
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("abby_core.discord.cogs.community.nudge_handler")
        logger.addHandler(handler)
        
        try:
            # Mock Discord bot
            mock_bot = Mock()
            mock_bot.get_cog = Mock(return_value=None)
            
            # Mock get_channel to return valid channel
            mock_channel = Mock()
            mock_bot.get_channel = Mock(return_value=mock_channel)
            
            nudge_handler = NudgeHandler(mock_bot)
            
            # Simulate multiple inactive users detected
            with patch.object(
                nudge_handler, 
                "_get_inactive_users",
                return_value=[{"user_id": i, "inactivity_days": 10} for i in range(5)]
            ):
                # Run tick
                await nudge_handler.nudge_users_tick()
            
            # Check logs: should have 0 or 1 config warning, NOT 5+ warnings
            log_output = log_capture.getvalue()
            config_warnings = log_output.count("NUDGE_CHANNEL_ID not configured")
            
            # ASSERTION: Either no warnings (configured) or max 1 warning (rate-limited)
            self.assertLessEqual(
                config_warnings, 1,
                f"Expected ≤1 'NUDGE_CHANNEL_ID not configured' warning, got {config_warnings}. "
                f"Logs show user-per-warning spam. Full logs:\n{log_output}"
            )
        finally:
            logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
