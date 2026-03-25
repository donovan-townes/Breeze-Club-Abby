"""Integration test for Discord scheduler adapter with heartbeat service.
"""

import pytest

def test_discord_scheduler_integration():
    pass
def mock_bot():
    """Create a mock Discord bot."""
    bot = AsyncMock()
    bot.start_time = 1000
    bot.get_cog = Mock(return_value=None)
    return bot


class TestSchedulerAdapterIntegration:
    """Test scheduler adapter integration with heartbeat service."""
    
    def test_heartbeat_job_handler_initialization(self, reset_hb, mock_bot):
        """Test HeartbeatJobHandler initializes with heartbeat service."""
        from abby_core.discord.adapters.scheduler_bridge import HeartbeatJobHandler
        
        handler = HeartbeatJobHandler(mock_bot)
        
        assert handler.bot is mock_bot
        assert handler.scheduler_heartbeat is not None
        assert handler.scheduler_heartbeat == get_scheduler_heartbeat()
    
    def test_announcement_delivery_job_handler_initialization(self, reset_hb, mock_bot):
        """Test AnnouncementDeliveryJobHandler initializes with heartbeat service."""
        from abby_core.discord.adapters.scheduler_bridge import AnnouncementDeliveryJobHandler
        
        handler = AnnouncementDeliveryJobHandler(mock_bot)
        
        assert handler.bot is mock_bot
        assert handler.scheduler_heartbeat is not None
    
    @pytest.mark.asyncio
    async def test_heartbeat_job_handler_records_metrics(self, reset_hb, mock_bot):
        """Test HeartbeatJobHandler can generate heartbeat during execution."""
        from abby_core.discord.adapters.scheduler_bridge import HeartbeatJobHandler
        
        # Mock the database functions
        with patch('abby_core.discord.adapters.scheduler_bridge.get_active_sessions_count', return_value=5), \
             patch('abby_core.discord.adapters.scheduler_bridge.get_pending_submissions_count', return_value=2), \
             patch('abby_core.discord.adapters.scheduler_bridge.emit_heartbeat'):
            
            handler = HeartbeatJobHandler(mock_bot)
            handler.scheduler_heartbeat.start()
            
            # Record some test metrics
            handler.scheduler_heartbeat.register_guild("guild-1")
            handler.scheduler_heartbeat.record_announcement_sent("guild-1")
            
            # Execute handler
            result = await handler.execute({}, {})
            
            assert result["status"] == "ok"
            assert handler.scheduler_heartbeat.get_health_status() == SchedulerHealth.HEALTHY
    
    @pytest.mark.asyncio
    async def test_announcement_delivery_handler_error_records_recovery(self, reset_hb, mock_bot):
        """Test AnnouncementDeliveryJobHandler records recovery on error."""
        from abby_core.discord.adapters.scheduler_bridge import AnnouncementDeliveryJobHandler
        
        # Mock the job execution to fail
        with patch('abby_core.discord.adapters.scheduler_bridge.execute_daily_world_announcements', 
                   side_effect=Exception("Test error")):
            
            handler = AnnouncementDeliveryJobHandler(mock_bot)
            handler.scheduler_heartbeat.start()
            
            # Execute handler (should fail)
            result = await handler.execute({}, {})
            
            assert result["status"] == "error"
            # Should have recorded recovery attempt
            assert handler.scheduler_heartbeat._recovery_attempts > 0
    
    def test_register_scheduler_jobs_initializes_heartbeat(self, reset_hb, mock_bot):
        """Test register_scheduler_jobs initializes the scheduler heartbeat."""
        from abby_core.discord.adapters.scheduler_bridge import register_scheduler_jobs
        from abby_core.services.scheduler import get_scheduler_service
        
        # Mock the database and scheduler service
        with patch('abby_core.discord.adapters.scheduler_bridge.get_database'), \
             patch('abby_core.discord.adapters.scheduler_bridge.get_scheduler_service') as mock_get_sched, \
             patch('abby_core.discord.adapters.scheduler_bridge.USE_PLATFORM_SCHEDULER', True):
            
            mock_scheduler = AsyncMock()
            mock_scheduler.register_handler = Mock()
            mock_get_sched.return_value = mock_scheduler
            
            # Call register
            register_scheduler_jobs(mock_bot)
            
            # Verify heartbeat was started
            heartbeat = get_scheduler_heartbeat()
            assert heartbeat._running is True
            assert heartbeat is not None
    
    def test_heartbeat_service_persistence_across_handlers(self, reset_hb):
        """Test that heartbeat service is the same singleton across all handlers."""
        from abby_core.discord.adapters.scheduler_bridge import (
            HeartbeatJobHandler,
            AnnouncementDeliveryJobHandler,
        )
        
        mock_bot = Mock()
        
        handler1 = HeartbeatJobHandler(mock_bot)
        handler2 = AnnouncementDeliveryJobHandler(mock_bot)
        
        # Should be the same singleton instance
        assert handler1.scheduler_heartbeat is handler2.scheduler_heartbeat
        
        # Metrics recorded in one should be visible in the other
        handler1.scheduler_heartbeat.record_announcement_sent("guild-1")
        hb = handler2.scheduler_heartbeat.get_last_heartbeat()
        
        # Give it a moment to process
        if hb:
            assert hb.announcements_sent_this_hour > 0 or handler2.scheduler_heartbeat._announcements_sent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
