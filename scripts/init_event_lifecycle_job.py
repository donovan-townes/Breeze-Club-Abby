"""
Initialize Event Lifecycle Job in MongoDB

This script adds the system.event_lifecycle job to the scheduler_jobs collection.
Run this once to enable automatic event start/end based on date boundaries.

Usage:
    python scripts/init_event_lifecycle_job.py
"""

from datetime import datetime, timezone
from abby_core.database.mongodb import get_database
from tdos_intelligence.observability import logging

logger = logging.getLogger(__name__)


def init_event_lifecycle_job():
    """Add event_lifecycle job to scheduler_jobs collection."""
    db = get_database()
    jobs_collection = db["scheduler_jobs"]
    
    # Check if job already exists
    existing = jobs_collection.find_one({"job_type": "system.event_lifecycle"})
    if existing:
        logger.info("[📅] Event lifecycle job already exists")
        return
    
    # Create job document
    job_doc = {
        "job_type": "system.event_lifecycle",
        "enabled": True,
        "schedule": {
            "type": "daily",
            "time": "00:00",  # Check daily at midnight UTC
            "timezone": "UTC"
        },
        "last_run_at": None,
        "next_run_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "description": "Platform-wide event auto-start/auto-end based on date boundaries",
    }
    
    result = jobs_collection.insert_one(job_doc)
    logger.info(f"[✅] Event lifecycle job created with ID: {result.inserted_id}")
    logger.info("[📅] Job will check event boundaries daily at 00:00 UTC")
    logger.info("[📅] Events: Valentine's (Feb 1-14), Easter (computed), 21 Days (Dec 1-21)")


if __name__ == "__main__":
    init_event_lifecycle_job()
