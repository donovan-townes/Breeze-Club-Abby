#!/usr/bin/env python3
"""
Phase 2 Implementation Verification Script

This script verifies that all Phase 2 changes are correctly integrated
and that the services can be initialized without errors.

Usage:
    python verify_phase2.py
"""

import sys
import os
from pathlib import Path

# Add abby-core to path
ABBY_ROOT = Path(__file__).parent
ABBY_CORE_PATH = ABBY_ROOT / "abby_core"
if str(ABBY_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(ABBY_CORE_PATH))
if str(ABBY_ROOT) not in sys.path:
    sys.path.insert(0, str(ABBY_ROOT))

def verify_imports():
    """Verify all required imports can be resolved."""
    print("=" * 70)
    print("PHASE 2 IMPLEMENTATION VERIFICATION")
    print("=" * 70)
    print("\n[1/5] Verifying imports...")
    
    try:
        from abby_core.storage.storage_manager import StorageManager
        print("    ✅ StorageManager imported successfully")
    except ImportError as e:
        print(f"    ❌ Failed to import StorageManager: {e}")
        return False
    
    try:
        from abby_core.generation.image_generator import ImageGenerator
        print("    ✅ ImageGenerator imported successfully")
    except ImportError as e:
        print(f"    ❌ Failed to import ImageGenerator: {e}")
        return False
    
    try:
        from abby_adapters.discord.config import BotConfig
        print("    ✅ BotConfig imported successfully")
    except ImportError as e:
        print(f"    ❌ Failed to import BotConfig: {e}")
        return False
    
    return True

def verify_config():
    """Verify BotConfig has StorageConfig."""
    print("\n[2/5] Verifying configuration...")
    
    from abby_adapters.discord.config import BotConfig
    
    try:
        config = BotConfig()
        print("    ✅ BotConfig instantiated successfully")
        
        # Check StorageConfig exists
        if hasattr(config, 'storage'):
            print("    ✅ StorageConfig found in BotConfig")
            print(f"       - storage_root: {config.storage.storage_root}")
            print(f"       - max_global_storage_mb: {config.storage.max_global_storage_mb}MB")
            print(f"       - max_user_storage_mb: {config.storage.max_user_storage_mb}MB")
            print(f"       - max_user_daily_gens: {config.storage.max_user_daily_gens}")
        else:
            print("    ❌ StorageConfig not found in BotConfig")
            return False
            
    except Exception as e:
        print(f"    ❌ Failed to instantiate BotConfig: {e}")
        return False
    
    return True

def verify_storage_init():
    """Verify StorageManager can be initialized."""
    print("\n[3/5] Verifying StorageManager initialization...")
    
    from abby_core.storage.storage_manager import StorageManager
    from abby_adapters.discord.config import BotConfig
    
    try:
        config = BotConfig()
        
        # Create test storage root
        test_root = Path("shared_test")
        test_root.mkdir(exist_ok=True)
        
        storage = StorageManager(
            storage_root=test_root,
            max_global_storage_mb=5000,
            max_user_storage_mb=500,
            cleanup_days=7
        )
        print("    ✅ StorageManager initialized successfully")
        
        # Test get_quota_status
        status = storage.get_quota_status("test_user_123")
        print(f"    ✅ Quota status retrieved: {status['daily']['used']}/{status['daily']['limit']} daily gens")
        
        # Cleanup
        import shutil
        shutil.rmtree(test_root, ignore_errors=True)
        
    except Exception as e:
        print(f"    ❌ Failed to initialize StorageManager: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def verify_generator_init():
    """Verify ImageGenerator can be initialized."""
    print("\n[4/5] Verifying ImageGenerator initialization...")
    
    from abby_core.generation.image_generator import ImageGenerator
    
    try:
        # Note: Will fail if STABILITY_API_KEY not set, but that's OK for init test
        generator = ImageGenerator(
            api_key="test_key_for_verification",  # Use test key
            db_path=Path("shared_test/test_stats.db"),
            max_user_daily_gens=5
        )
        print("    ✅ ImageGenerator initialized successfully")
        
        # Check available styles
        styles = generator.get_available_styles()
        print(f"    ✅ Available styles loaded: {len(styles)} styles available")
        print(f"       (enhance, anime, cinematic, digital-art, etc.)")
        
        # Cleanup test db
        if Path("shared_test/test_stats.db").exists():
            Path("shared_test/test_stats.db").unlink()
        
    except Exception as e:
        print(f"    ❌ Failed to initialize ImageGenerator: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def verify_cog_code():
    """Verify the cog has been updated correctly."""
    print("\n[5/5] Verifying cogs/creative/images.py modifications...")
    
    cog_file = Path("abby_adapters/discord/cogs/creative/images.py")
    
    if not cog_file.exists():
        print(f"    ❌ Cog file not found: {cog_file}")
        return False
    
    content = cog_file.read_text()
    checks = [
        ("self.storage = bot.storage", "Service reference initialization"),
        ("self.generator = bot.generator", "Generator reference initialization"),
        ("await self.generator.text_to_image", "ImageGenerator.text_to_image() usage"),
        ("await self.storage.save_image", "StorageManager.save_image() usage"),
        ("storage.get_quota_status", "Quota status retrieval"),
        ("filename=\"image.png\"", "Proper filename for Discord embeds"),
    ]
    
    all_good = True
    for check_str, description in checks:
        if check_str in content:
            print(f"    ✅ {description}")
        else:
            print(f"    ❌ {description} - NOT FOUND")
            all_good = False
    
    return all_good

def main():
    """Run all verification checks."""
    results = []
    
    results.append(("Imports", verify_imports()))
    results.append(("Configuration", verify_config()))
    results.append(("StorageManager Init", verify_storage_init()))
    results.append(("ImageGenerator Init", verify_generator_init()))
    results.append(("Cog Code Modifications", verify_cog_code()))
    
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check_name:.<50} {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All checks passed! Phase 2 is ready for deployment to TSERVER.")
        print("\nNext steps:")
        print("  1. Deploy code to TSERVER")
        print("  2. Set STORAGE_ROOT and STABILITY_API_KEY in .env")
        print("  3. Run: python launch.py")
        print("  4. Test /imagine command in Discord")
        return 0
    else:
        print("\n❌ Some checks failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
