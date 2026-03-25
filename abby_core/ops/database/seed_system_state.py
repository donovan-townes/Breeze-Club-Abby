"""System and seasonal initialization script for E2E setup.

This script combines:
1. System state seeding (instances, changelog)
2. Seasonal system initialization (predefined seasons, Winter 2026 activation)
3. Verification and recovery options

Usage:
    python scripts/seed_system_state.py                      # Initialize both systems
    python scripts/seed_system_state.py --verify-only        # Verify only
    python scripts/seed_system_state.py --force-activate winter-2026  # Force season
    python scripts/seed_system_state.py --env dev|prod       # Specify environment
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from abby_core.database.mongodb import get_database, connect_to_mongodb
from abby_core.system.system_changelog import initialize_changelog_entries
from abby_core.observability.logging import setup_logging, logging
from abby_core.system.system_state import (
    initialize_predefined_seasons,
    get_active_season,
    get_state_by_id,
    activate_state,
    list_all_states,
)

setup_logging()
logger = logging.getLogger(__name__)


def seed_system_state_instances():
    """Seed system_state_instances with predefined seasonal states.
    
    Creates instances for the four canonical seasons with proper priority
    and timestamp boundaries.
    """
    db = get_database()
    instances_collection = db["system_state_instances"]
    
    # Check if already initialized
    if instances_collection.count_documents({}) > 0:
        logger.info("[✓] system_state_instances already initialized, skipping seed")
        return True
    
    logger.info("[⚙️] Seeding system_state_instances...")
    
    now = datetime.utcnow()
    
    # Hardcoded 2026 season boundaries (aligned with system_state.py)
    season_instances = [
        {
            "state_id": "winter-2026",
            "state_type": "season",
            "scope": "global",
            "priority": 10,
            "active": True,
            "activated_at": now,
            "activated_by": "system_seed",
            "start_at": datetime(2025, 12, 21),
            "end_at": datetime(2026, 3, 19, 23, 59, 59),
        },
        {
            "state_id": "spring-2026",
            "state_type": "season",
            "scope": "global",
            "priority": 10,
            "active": False,
            "activated_at": None,
            "activated_by": None,
            "start_at": datetime(2026, 3, 20),
            "end_at": datetime(2026, 6, 20, 23, 59, 59),
        },
        {
            "state_id": "summer-2026",
            "state_type": "season",
            "scope": "global",
            "priority": 10,
            "active": False,
            "activated_at": None,
            "activated_by": None,
            "start_at": datetime(2026, 6, 21),
            "end_at": datetime(2026, 9, 21, 23, 59, 59),
        },
        {
            "state_id": "fall-2026",
            "state_type": "season",
            "scope": "global",
            "priority": 10,
            "active": False,
            "activated_at": None,
            "activated_by": None,
            "start_at": datetime(2026, 9, 22),
            "end_at": datetime(2026, 12, 20, 23, 59, 59),
        },
    ]
    
    try:
        result = instances_collection.insert_many(season_instances)
        logger.info(f"[✓] Seeded {len(result.inserted_ids)} seasonal instances")
        return True
    except Exception as exc:
        logger.error(f"[✗] Failed to seed instances: {exc}")
        return False


def seed_system_changelog():
    """Seed the system changelog with initial entries."""
    logger.info("[⚙️] Seeding system_changelog...")
    try:
        initialize_changelog_entries()
        logger.info("[✓] System changelog initialized")
        return True
    except Exception as exc:
        logger.error(f"[✗] Failed to initialize changelog: {exc}")
        return False


def initialize_seasonal_system():
    """Initialize and activate Winter 2026."""
    logger.info("[🌍] Starting seasonal system initialization...")
    
    try:
        # Step 1: Initialize predefined seasons
        logger.info("[📋] Step 1: Creating predefined seasons...")
        initialize_predefined_seasons()
        logger.info("[✅] Predefined seasons created (or already exist)")
        
        # Step 2: Verify all seasons exist
        logger.info("[📋] Step 2: Verifying season collection...")
        all_seasons = list_all_states("season")
        logger.info(f"[✅] Found {len(all_seasons)} seasons in database")
        
        for season in all_seasons:
            logger.debug(f"  - {season.get('state_id')}: {season.get('label')}")
        
        # Step 3: Check current active season
        logger.info("[📋] Step 3: Checking current active season...")
        active = get_active_season()
        
        if active:
            active_id = active.get("state_id")
            active_label = active.get("label")
            logger.info(f"[✅] Active season: {active_label} ({active_id})")
            
            # Verify it's valid
            now = datetime.utcnow()
            start = active.get("start_at")
            end = active.get("end_at")
            
            if isinstance(start, datetime) and isinstance(end, datetime):
                if start <= now <= end:
                    logger.info(f"[✅] Active season is valid for current date ({now.date()})")
                    return True
                else:
                    logger.warning(f"[⚠️] Active season boundary mismatch!")
                    logger.warning(f"    Active: {active_id}")
                    logger.warning(f"    Now: {now.date()}")
                    logger.warning(f"    Period: {start.date()} – {end.date()}")
        else:
            logger.warning("[⚠️] No active season found")
        
        # Step 4: Activate Winter 2026 if needed
        logger.info("[📋] Step 4: Activating Winter 2026...")
        winter = get_state_by_id("winter-2026")
        if not winter:
            logger.error("[❌] Winter 2026 not found in database!")
            return False
        
        if activate_state("winter-2026"):
            logger.info("[✅] Winter 2026 activated")
            active = get_active_season()
            if active:
                logger.info(f"[✅] Confirmed active season: {active.get('label')}")
            return True
        else:
            logger.error("[❌] Failed to activate Winter 2026")
            return False
            
    except Exception as e:
        logger.error(f"[❌] Initialization failed: {e}", exc_info=True)
        return False


def verify_seasonal_system():
    """Verify seasonal system is properly initialized."""
    logger.info("[🔍] Verifying seasonal system state...")
    
    try:
        # Check database connection
        logger.info("[📋] Checking database connection...")
        db = get_database()
        system_state = db["system_state"]
        count = system_state.count_documents({})
        logger.info(f"[✅] system_state collection has {count} documents")
        
        # Check predefined seasons
        logger.info("[📋] Checking predefined seasons...")
        all_seasons = list_all_states("season")
        expected_seasons = ["winter-2026", "spring-2026", "summer-2026", "fall-2026"]
        
        found_ids = [s.get("state_id") for s in all_seasons]
        missing = [s for s in expected_seasons if s not in found_ids]
        
        if missing:
            logger.warning(f"[⚠️] Missing seasons: {missing}")
            logger.warning("[💡] Run without --verify-only to initialize them")
            return False
        else:
            logger.info(f"[✅] All expected seasons present: {', '.join(expected_seasons)}")
        
        # Check active season
        logger.info("[📋] Checking active season...")
        active = get_active_season()
        if not active:
            logger.error("[❌] No active season found!")
            return False
        
        logger.info(f"[✅] Active season: {active.get('label')} ({active.get('state_id')})")
        
        # Check season boundaries
        now = datetime.utcnow()
        start = active.get("start_at")
        end = active.get("end_at")
        
        if isinstance(start, datetime) and isinstance(end, datetime):
            if start <= now <= end:
                logger.info(f"[✅] Season boundary valid for {now.date()}")
            else:
                logger.error(f"[❌] Season boundary invalid!")
                logger.error(f"    Now: {now.date()}")
                logger.error(f"    Period: {start.date()} – {end.date()}")
                return False
        
        # Check canon reference
        canon_ref = active.get("canon_ref")
        logger.info(f"[✅] Canon reference: {canon_ref}")
        
        # Check effects
        effects = active.get("effects", {})
        if effects.get("xp_reset"):
            logger.info("[✅] XP reset enabled for this season")
        else:
            logger.warning("[⚠️] XP reset not enabled!")
        
        logger.info("[✅] Seasonal system verification passed!")
        return True
    
    except Exception as e:
        logger.error(f"[❌] Verification failed: {e}", exc_info=True)
        return False


def force_activate(season_id: str) -> bool:
    """Force activate a specific season."""
    logger.info(f"[🌍] Forcing activation of season: {season_id}")
    
    try:
        season = get_state_by_id(season_id)
        if not season:
            logger.error(f"[❌] Season not found: {season_id}")
            return False
        
        if activate_state(season_id):
            logger.info(f"[✅] Activated: {season.get('label')}")
            return True
        else:
            logger.error(f"[❌] Failed to activate {season_id}")
            return False
    
    except Exception as e:
        logger.error(f"[❌] Force activation failed: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed and initialize system state and seasonal system"
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        default="dev",
        help="Environment (dev or prod)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify, don't initialize"
    )
    parser.add_argument(
        "--force-activate",
        type=str,
        metavar="SEASON_ID",
        help="Force activate a specific season (e.g., winter-2026)"
    )
    
    args = parser.parse_args()
    
    logger.info("[🚀] System State and Seasonal Initialization")
    logger.info("=" * 60)
    
    if args.verify_only:
        logger.info("[🔍] Verification Mode")
        success = verify_seasonal_system()
    elif args.force_activate:
        logger.info(f"[🔧] Force Activate Mode: {args.force_activate}")
        success = force_activate(args.force_activate)
        if success:
            verify_seasonal_system()
    else:
        logger.info("[⚙️] Full Initialization Mode")
        result1 = seed_system_state_instances()
        result2 = seed_system_changelog()
        result3 = initialize_seasonal_system()
        success = result1 and result2 and result3
    
    logger.info("=" * 60)
    if success:
        logger.info("[✅] System state initialization ready!")
        return 0
    else:
        logger.error("[❌] System state initialization incomplete")
        return 1


if __name__ == "__main__":
    sys.exit(main())
