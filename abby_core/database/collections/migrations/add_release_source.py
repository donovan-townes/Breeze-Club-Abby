"""
Migration Script: Add source field to existing releases

PURPOSE: Migrate existing user releases to include the "source" field
that identifies how they were created:
- "auto_detected": Bot found a shared link
- "user_curated": User manually added via Discord View
- "distribution": From Proton distribution system

BACKGROUND:
Before this migration, all releases were either auto_detected or user_curated.
We're now adding the source field to distinguish between them for better
tracking and future distribution system integration.

MIGRATION STRATEGY:
- All existing releases are marked as "user_curated" (safest assumption)
- When Proton integration is live, new releases from distribution system
  will have source: "distribution"
- As auto-detection is added, those will have source: "auto_detected"

RUN THIS MIGRATION:
1. In Python shell or script:
   from abby_core.database.collections.migrations.add_release_source import run_migration
   result = run_migration()
   print(result)

2. Or from command line:
   python -c "from abby_core.database.collections.migrations.add_release_source import run_migration; print(run_migration())"
"""

from typing import Dict, Any
from datetime import datetime

from abby_core.database.collections.users import Users
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def run_migration() -> Dict[str, Any]:
    """
    Add source field to existing releases.

    Returns:
        Migration report with counts
    """
    collection = Users.get_collection()

    report = {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "users_updated": 0,
        "releases_updated": 0,
        "errors": [],
        "warnings": []
    }

    try:
        # Find all users with releases
        users_with_releases = collection.find(
            {"releases": {"$exists": True}},
            {"_id": 1, "user_id": 1, "releases": 1}
        )

        for user_doc in users_with_releases:
            user_id = user_doc.get("user_id", "unknown")
            releases = user_doc.get("releases", [])

            if not releases:
                continue

            # Check if any releases are missing source field
            needs_update = False
            updated_releases = []

            for release in releases:
                if "source" not in release:
                    # Add source field - default to "user_curated" (safest assumption)
                    release["source"] = "user_curated"
                    # Also ensure distribution_release_id is present (null if not linked)
                    if "distribution_release_id" not in release:
                        release["distribution_release_id"] = None
                    needs_update = True
                    report["releases_updated"] += 1

                updated_releases.append(release)

            # Update user document if needed
            if needs_update:
                collection.update_one(
                    {"_id": user_doc["_id"]},
                    {
                        "$set": {
                            "releases": updated_releases,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                report["users_updated"] += 1
                logger.debug(
                    f"[Migration] Updated user {user_id}: "
                    f"{report['releases_updated']} releases added source field"
                )

        report["status"] = "success"
        logger.info(
            f"[Migration] Complete: {report['users_updated']} users updated, "
            f"{report['releases_updated']} releases updated"
        )

    except Exception as e:
        report["status"] = "error"
        report["errors"].append(str(e))
        logger.error(f"[Migration] Error running migration: {e}")

    return report


def verify_migration() -> Dict[str, Any]:
    """
    Verify that all releases have source field.

    Returns:
        Verification report
    """
    collection = Users.get_collection()

    report = {
        "status": "checking",
        "timestamp": datetime.utcnow().isoformat(),
        "total_users_with_releases": 0,
        "users_with_unsourced_releases": 0,
        "total_releases": 0,
        "sourced_releases": 0,
        "unsourced_releases": 0,
        "source_breakdown": {}
    }

    try:
        users_with_releases = collection.find(
            {"releases": {"$exists": True}},
            {"releases": 1}
        )

        for user_doc in users_with_releases:
            releases = user_doc.get("releases", [])
            if not releases:
                continue

            report["total_users_with_releases"] += 1

            unsourced = []
            for release in releases:
                report["total_releases"] += 1
                source = release.get("source", "MISSING")

                if source == "MISSING":
                    unsourced.append(release)
                    report["unsourced_releases"] += 1
                else:
                    report["sourced_releases"] += 1
                    report["source_breakdown"][source] = report["source_breakdown"].get(source, 0) + 1

            if unsourced:
                report["users_with_unsourced_releases"] += 1

        report["status"] = "verified"
        logger.info(
            f"[Verification] {report['sourced_releases']}/{report['total_releases']} "
            f"releases have source field"
        )

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        logger.error(f"[Verification] Error checking migration: {e}")

    return report


if __name__ == "__main__":
    # Run migration if executed directly
    print("Running migration: Add source field to releases...")
    result = run_migration()
    print(f"Migration result: {result}")

    print("\nVerifying migration...")
    verification = verify_migration()
    print(f"Verification result: {verification}")
