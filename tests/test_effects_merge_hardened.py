"""Test suite for hardened effects merge (Phase 1).

Tests:
- Type mismatch detection and logging
- Metrics emission for observability
- Operator audit trail
- Merge determinism verification
"""

import pytest
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

from abby_core.system.effects_merger import merge_effects


@pytest.fixture
def sample_states():
    """Create sample state dictionaries for testing."""
    return [
        {
            "state_id": "winter-2026",
            "state_type": "season",
            "priority": 10,
            "start_at": datetime(2026, 1, 1),
            "effects": {
                "xp_multiplier": 1.2,  # numeric
                "holiday_mode": True,   # boolean
            }
        },
        {
            "state_id": "holiday-event",
            "state_type": "event",
            "priority": 20,
            "start_at": datetime(2026, 1, 15),
            "effects": {
                "xp_multiplier": 1.5,  # additive override
                "gift_mode": True,       # or strategy
            }
        }
    ]


class TestEffectsMergeBasic:
    """Test basic merge functionality."""
    
    def test_merge_numeric_effects(self, sample_states):
        """Test merging numeric effects (additive strategy)."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "xp_multiplier": {
                "type": "numeric",
                "merge_strategy": "additive",
                "identity": 0.0
            }
        }):
            merged = merge_effects(sample_states)
            
            # Should have xp_multiplier from both states
            assert "xp_multiplier" in merged
            # additive: 1.2 + 1.5 = 2.7
            assert merged["xp_multiplier"] == 2.7
    
    def test_merge_boolean_effects_or(self, sample_states):
        """Test merging boolean effects with OR strategy."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "holiday_mode": {
                "type": "boolean",
                "merge_strategy": "or",
                "identity": False
            },
            "gift_mode": {
                "type": "boolean",
                "merge_strategy": "or",
                "identity": False
            }
        }):
            merged = merge_effects(sample_states)
            
            assert merged.get("holiday_mode") is True
            assert merged.get("gift_mode") is True


class TestTypeMismatchDetection:
    """Test type mismatch detection and logging (Phase 1)."""
    
    def test_type_mismatch_logged_with_context(self, caplog):
        """Test that type mismatches emit WARN logs with operator context."""
        states = [
            {
                "state_id": "test-state",
                "priority": 10,
                "start_at": datetime.now(),
                "effects": {
                    "bad_effect": "string_value",  # WRONG TYPE
                }
            }
        ]
        
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "bad_effect": {
                "type": "numeric",
                "merge_strategy": "additive",
                "identity": 0.0
            }
        }):
            with caplog.at_level(logging.WARNING):
                merged = merge_effects(states, operator_id="user:operator_123")
        
        # Should emit warning
        warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
        assert len(warnings) > 0
        
        # Should include operator_id in warning
        warning_msgs = [rec.message for rec in warnings]
        assert any("user:operator_123" in msg for msg in warning_msgs), \
            "operator_id should be in type mismatch warning"
        assert any("Type mismatch" in msg for msg in warning_msgs)
    
    def test_merge_completes_despite_mismatch(self, caplog):
        """Test that merge completes despite type mismatches (graceful degradation)."""
        states = [
            {
                "state_id": "state1",
                "priority": 10,
                "start_at": datetime.now(),
                "effects": {
                    "effect1": 1.0,      # numeric
                    "effect2": "string"  # WRONG TYPE
                }
            }
        ]
        
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "effect1": {"type": "numeric", "merge_strategy": "additive", "identity": 0.0},
            "effect2": {"type": "numeric", "merge_strategy": "additive", "identity": 0.0}
        }):
            with caplog.at_level(logging.WARNING):
                merged = merge_effects(states, operator_id="system:merge")
        
        # Should have both effects (second is fallback override)
        assert "effect1" in merged
        assert "effect2" in merged  # Fallback to override
        assert merged["effect2"] == "string"


class TestMergeMetrics:
    """Test metrics emission for observability."""
    
    def test_merge_summary_logged(self, sample_states, caplog):
        """Test that merge emits summary log with operator context."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "xp_multiplier": {
                "type": "numeric",
                "merge_strategy": "additive",
                "identity": 0.0
            },
            "holiday_mode": {
                "type": "boolean",
                "merge_strategy": "or",
                "identity": False
            },
            "gift_mode": {
                "type": "boolean",
                "merge_strategy": "or",
                "identity": False
            }
        }):
            with caplog.at_level(logging.INFO):
                merged = merge_effects(sample_states, operator_id="scheduler:daily_check")
        
        # Should emit info log with summary
        info_logs = [rec for rec in caplog.records if rec.levelname == "INFO"]
        summary_logs = [rec for rec in info_logs if "Completed" in rec.message]
        
        assert len(summary_logs) > 0
        
        # Should include operator_id and counts
        summary_msg = summary_logs[0].message
        assert "scheduler:daily_check" in summary_msg
        assert "states=" in summary_msg
        assert "effects=" in summary_msg
        assert "type_mismatches=" in summary_msg


class TestOperatorAuditTrail:
    """Test operator tracking in merge operations."""
    
    def test_no_operator_defaults_to_system(self, sample_states, caplog):
        """Test that merge defaults operator_id to 'system'."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {}):
            with caplog.at_level(logging.INFO):
                merge_effects(sample_states)  # No operator_id
        
        # Should log with "system" as default
        info_logs = [rec for rec in caplog.records if rec.levelname == "INFO"]
        assert any("operator=system" in rec.message for rec in info_logs)
    
    def test_custom_operator_tracked(self, sample_states, caplog):
        """Test that custom operator_id is tracked in logs."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {}):
            with caplog.at_level(logging.INFO):
                merge_effects(sample_states, operator_id="admin:john_doe")
        
        info_logs = [rec for rec in caplog.records if rec.levelname == "INFO"]
        assert any("admin:john_doe" in rec.message for rec in info_logs)


class TestMergeDeterminism:
    """Test that merge is deterministic given same inputs."""
    
    def test_same_input_produces_same_output(self, sample_states):
        """Test that merging same states twice produces identical results."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "xp_multiplier": {
                "type": "numeric",
                "merge_strategy": "additive",
                "identity": 0.0
            },
            "holiday_mode": {
                "type": "boolean",
                "merge_strategy": "or",
                "identity": False
            },
            "gift_mode": {
                "type": "boolean",
                "merge_strategy": "or",
                "identity": False
            }
        }):
            merged1 = merge_effects(sample_states)
            merged2 = merge_effects(sample_states)
            
            assert merged1 == merged2


class TestConcurrentMerges:
    """Test concurrent merge operations (operator tracking)."""
    
    def test_concurrent_operators_tracked_separately(self, sample_states, caplog):
        """Test that concurrent merges with different operators are logged correctly."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {}):
            with caplog.at_level(logging.INFO):
                merge_effects(sample_states, operator_id="system:node1")
                merge_effects(sample_states, operator_id="system:node2")
        
        info_logs = [rec for rec in caplog.records if rec.levelname == "INFO"]
        node1_logs = [rec for rec in info_logs if "node1" in rec.message]
        node2_logs = [rec for rec in info_logs if "node2" in rec.message]
        
        assert len(node1_logs) > 0
        assert len(node2_logs) > 0


class TestErrorHandling:
    """Test error handling in merge operations."""
    
    def test_exception_during_merge_logged(self, caplog):
        """Test that exceptions during merge are logged with operator context."""
        states = [
            {
                "state_id": "broken",
                "priority": 10,
                "start_at": datetime.now(),
                "effects": {
                    "effect1": None
                }
            }
        ]
        
        # Mock registry to raise exception
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {
            "effect1": {
                "type": "numeric",
                "merge_strategy": "custom_broken",  # Invalid strategy
                "identity": 0.0
            }
        }):
            with caplog.at_level(logging.ERROR):
                # Should not raise, should handle gracefully
                merged = merge_effects(states, operator_id="admin:test")
        
        # Should log error with operator context
        error_logs = [rec for rec in caplog.records if rec.levelname == "ERROR"]
        assert any("admin:test" in rec.message for rec in error_logs)


class TestMergeWithEmptyStates:
    """Test edge cases with empty or minimal inputs."""
    
    def test_empty_states_list(self):
        """Test merging empty states list."""
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {}):
            merged = merge_effects([])
            assert merged == {}
    
    def test_states_with_no_effects(self, caplog):
        """Test states without effects."""
        states = [
            {"state_id": "test", "priority": 10, "start_at": datetime.now(), "effects": {}}
        ]
        
        with patch('abby_core.system.effects_merger.EFFECT_REGISTRY', {}):
            with caplog.at_level(logging.INFO):
                merged = merge_effects(states, operator_id="system:test")
        
        assert merged == {}
        
        # Should still log merge summary
        info_logs = [rec for rec in caplog.records if "Completed" in rec.message]
        assert len(info_logs) > 0
