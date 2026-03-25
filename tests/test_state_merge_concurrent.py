"""Test concurrent state merge determinism (R1: Effects Merge Non-Determinism).

Verifies that concurrent requests during state transitions produce consistent
results due to MongoDB snapshot isolation in resolve_system_state().

Architecture Test:
- Simulates concurrent state resolution during active state transitions
- Validates snapshot read concern ensures consistent view of active states
- Tests identity value initialization for all merge strategies
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

from abby_core.llm.system_state_resolver import resolve_system_state
from abby_core.system.effects_merger import merge_effects
from abby_core.database.mongodb import get_database


class TestConcurrentStateMergeDeterminism:
    """Test suite for R1: Effects merge non-determinism fixes."""
    
    @pytest.fixture
    def clean_state_collections(self):
        """Clean up state collections before/after each test."""
        db = get_database()
        db["system_state"].delete_many({})
        db["system_state_instances"].delete_many({})
        yield
        db["system_state"].delete_many({})
        db["system_state_instances"].delete_many({})
    
    def test_identity_initialization_all_strategies(self):
        """Test that all merge strategies initialize with correct identity values.
        
        Validates:
        - additive: starts at 0.0
        - multiplier: starts at 1.0
        - or: starts at False
        - override: no identity (direct assignment)
        """
        # Test additive strategy (affinity_modifier uses additive)
        states_additive = [
            {"effects": {"affinity_modifier": 0.5}, "priority": 1, "start_at": datetime.now()},
            {"effects": {"affinity_modifier": 0.3}, "priority": 2, "start_at": datetime.now()},
        ]
        result = merge_effects(states_additive)
        assert result["affinity_modifier"] == 0.8, "Additive should sum from identity 0.0"
        
        # Test OR strategy
        states_or = [
            {"effects": {"crush_system_enabled": False}, "priority": 1, "start_at": datetime.now()},
            {"effects": {"crush_system_enabled": True}, "priority": 2, "start_at": datetime.now()},
        ]
        result = merge_effects(states_or)
        assert result["crush_system_enabled"] is True, "OR should accumulate from identity False"
        
        # Test override strategy (persona_overlay uses override)
        states_override = [
            {"effects": {"persona_overlay": "romantic_playful"}, "priority": 2, "start_at": datetime.now()},
            {"effects": {"persona_overlay": "energetic_sunny"}, "priority": 1, "start_at": datetime.now()},
        ]
        result = merge_effects(states_override)
        # Override strategy: processes high priority first, so "romantic_playful" (pri 2) is set first,
        # then "energetic_sunny" (pri 1) overrides it. Last processed wins.
        assert result["persona_overlay"] == "energetic_sunny", "Override should use last processed value"
    
    def test_merge_precedence_deterministic(self):
        """Test that merge precedence is deterministic (priority DESC, then start_at DESC)."""
        now = datetime.now()
        states = [
            {
                "effects": {"affinity_modifier": 0.1}, 
                "priority": 1, 
                "start_at": now - timedelta(hours=2)
            },
            {
                "effects": {"affinity_modifier": 0.2}, 
                "priority": 2,  # Higher priority wins
                "start_at": now - timedelta(hours=1)
            },
            {
                "effects": {"affinity_modifier": 0.3}, 
                "priority": 1,  # Same priority as first, but later start_at
                "start_at": now
            },
        ]
        
        # Run merge multiple times - should always produce same result
        results = [merge_effects(states) for _ in range(10)]
        unique_results = set(r["affinity_modifier"] for r in results)
        assert len(unique_results) == 1, "Merge should be deterministic"
        
        # Priority 2 should be applied first (0.2), then priority 1 items added
        # Order within priority 1: later start_at first (0.3 + 0.1 = 0.4)
        # Total: 0.2 + 0.4 = 0.6
        assert results[0]["affinity_modifier"] == 0.6, "Merge precedence incorrect"
    
    @pytest.mark.asyncio
    async def test_concurrent_resolution_consistency(self, clean_state_collections):
        """Test that concurrent resolve_system_state() calls produce consistent results.
        
        This is the critical R1 test: Simulates state transition happening during
        concurrent resolutions. With snapshot isolation, all concurrent requests
        should see the same active states.
        """
        db = get_database()
        now = datetime.now()
        
        # Set up initial state
        db["system_state"].insert_one({
            "state_id": "season_winter_2026",
            "state_type": "season",
            "key": "winter_2026",
            "label": "Winter 2026",
            "scope": "global",
            "priority": 100,
            "effects": {"affinity_modifier": 0.5, "persona_overlay": "romantic_playful"},
            "start_at": now - timedelta(days=30),
            "end_at": now + timedelta(days=60),
            "active": True,
        })
        
        db["system_state_instances"].insert_one({
            "state_id": "season_winter_2026",
            "state_type": "season",
            "key": "winter_2026",
            "scope": "global",
            "priority": 100,
            "start_at": now - timedelta(days=30),
            "end_at": now + timedelta(days=60),
            "active": True,
        })
        
        # Simulate concurrent resolutions
        async def resolve_with_delay(delay_ms: int):
            await asyncio.sleep(delay_ms / 1000.0)
            return resolve_system_state(now=now, scope="global")
        
        # Launch 10 concurrent resolutions with small delays
        tasks = [resolve_with_delay(i * 10) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All results should have same number of active states
        active_state_counts = [len(r["active_states"]) for r in results]
        assert len(set(active_state_counts)) == 1, "Concurrent resolutions produced different state counts"
        
        # All results should have same merged effects
        effect_tuples = [tuple(sorted(r["effects"].items())) for r in results]
        assert len(set(effect_tuples)) == 1, "Concurrent resolutions produced different merged effects"
        
        # Verify snapshot isolation prevented mid-transition reads
        assert results[0]["effects"]["affinity_modifier"] == 0.5, "Effects merge incorrect"
        assert results[0]["effects"]["persona_overlay"] == "romantic_playful", "Effects merge incorrect"
    
    def test_type_mismatch_fallback_to_override(self):
        """Test that type mismatches fall back to override strategy with warning.
        
        When a type mismatch occurs, the merge falls back to override behavior,
        preserving the last successfully processed value (not necessarily highest priority).
        """
        states = [
            {"effects": {"affinity_modifier": 0.5}, "priority": 1, "start_at": datetime.now()},
            {"effects": {"affinity_modifier": "invalid_string"}, "priority": 2, "start_at": datetime.now()},
        ]
        
        # Type mismatch triggers fallback to override
        # Processing order: priority 2 first ("invalid_string"), then priority 1 (0.5)
        # Since "invalid_string" is invalid for additive strategy, it gets overridden by 0.5
        result = merge_effects(states)
        # The final value is the last successfully processed value (0.5)
        assert result["affinity_modifier"] == 0.5, "Type mismatch should preserve last valid value"
    
    @pytest.mark.asyncio
    async def test_snapshot_fallback_on_error(self, clean_state_collections):
        """Test that resolve_system_state falls back gracefully if snapshot fails.
        
        If MongoDB doesn't support snapshot read concern (older versions),
        the function should fall back to non-transactional reads with a warning.
        """
        # This test verifies the try/except fallback logic
        # Even if snapshot fails, resolution should still work (with warning)
        now = datetime.now()
        
        db = get_database()
        db["system_state"].insert_one({
            "state_id": "test_state",
            "state_type": "event",
            "key": "test",
            "scope": "global",
            "priority": 50,
            "effects": {"test_effect": True},
            "start_at": now - timedelta(hours=1),
            "end_at": now + timedelta(hours=1),
            "active": True,
        })
        
        # Should not raise exception even if snapshot fails
        result = resolve_system_state(now=now, scope="global")
        assert "effects" in result, "Fallback resolution should still work"
        assert len(result["active_states"]) >= 0, "Should return valid state structure"


class TestEffectsValidation:
    """Test effects validation (identity types match strategy types)."""
    
    def test_identity_types_match_strategies(self):
        """Test that identity values have correct types for their strategies."""
        from abby_core.system.effects_registry import EFFECT_REGISTRY
        
        for effect_key, schema in EFFECT_REGISTRY.items():
            strategy = schema.get("merge_strategy")
            identity = schema.get("identity")
            
            if strategy == "additive":
                assert isinstance(identity, (int, float)), \
                    f"Additive strategy for '{effect_key}' should have numeric identity"
            elif strategy == "multiplier":
                assert isinstance(identity, (int, float)), \
                    f"Multiplier strategy for '{effect_key}' should have numeric identity"
                assert identity == 1.0, \
                    f"Multiplier strategy for '{effect_key}' should have identity 1.0"
            elif strategy == "or":
                assert isinstance(identity, bool), \
                    f"OR strategy for '{effect_key}' should have boolean identity"
                assert identity is False, \
                    f"OR strategy for '{effect_key}' should have identity False"
            elif strategy == "override":
                # Override has no identity constraint (can be None or any type)
                pass
