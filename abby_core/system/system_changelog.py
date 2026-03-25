"""System changelog management for devlog injection (system namespace)."""

from datetime import datetime
from typing import Dict, Any, Optional, List

from abby_core.database.mongodb import get_database
from abby_core.observability.logging import logging

logger = logging.getLogger(__name__)


# ==================== COLLECTION ACCESS ====================

def get_system_changelog_collection():
    """Get the system_changelog collection from configured database."""
    db = get_database()
    return db["system_changelog"]


# ==================== ENTRY CREATION ====================

def record_changelog_entry(
    domain: str,
    summary: str,
    details: List[str],
    visible_to_users: bool = True,
    operator_id: Optional[int] = None,
) -> Optional[str]:
    """Record a new system changelog entry."""
    collection = get_system_changelog_collection()
    
    entry = {
        "domain": domain.lower(),
        "summary": summary,
        "details": details,
        "visible_to_users": visible_to_users,
        "introduced_at": datetime.utcnow(),
        "operator_id": operator_id,
    }
    
    try:
        result = collection.insert_one(entry)
        entry_id = str(result.inserted_id)
        logger.info(
            f"[changelog] Recorded entry: domain={domain}, visible={visible_to_users}, id={entry_id}"
        )
        return entry_id
    except Exception as exc:
        logger.error(f"[changelog] Failed to record entry: {exc}")
        return None


# ==================== RETRIEVAL ====================

def get_recent_changelog_entries(
    max_entries: int = 10,
    domain: Optional[str] = None,
    visible_only: bool = True,
) -> List[Dict[str, Any]]:
    """Get recent changelog entries, sorted by recency (newest first)."""
    collection = get_system_changelog_collection()
    
    query: Dict[str, Any] = {}
    if visible_only:
        query["visible_to_users"] = True
    if domain:
        query["domain"] = domain.lower()
    
    try:
        entries = list(
            collection.find(query).sort("introduced_at", -1).limit(max_entries)
        )
        return entries
    except Exception as exc:
        logger.error(f"[changelog] Failed to retrieve entries: {exc}")
        return []


def get_changelog_summary(
    max_entries: int = 5,
    visible_only: bool = True,
) -> Optional[str]:
    """Get a formatted devlog summary for LLM injection."""
    entries = get_recent_changelog_entries(
        max_entries=max_entries,
        visible_only=visible_only,
    )
    
    if not entries:
        return None
    
    lines = ["Recent system updates and improvements:"]
    
    for entry in entries:
        summary = entry.get("summary", "")
        domain = entry.get("domain", "unknown")
        introduced_at = entry.get("introduced_at")
        
        # Format date nicely
        date_str = ""
        if introduced_at:
            try:
                date_str = introduced_at.strftime("%B %d, %Y")
            except Exception:
                date_str = str(int(introduced_at))[:10] if hasattr(introduced_at, "__int__") else str(introduced_at)[:10]
        
        header = f"- [{domain.title()}] {summary}"
        if date_str:
            header += f" ({date_str})"
        lines.append(header)
        
        details = entry.get("details", [])
        for detail in details[:3]:
            lines.append(f"  • {detail}")
    
    return "\n".join(lines)


def get_changelog_summary_for_intent(intent: str) -> Optional[str]:
    """Get changelog summary for a specific intent context."""
    if intent != "meta_system":
        return None
    
    return get_changelog_summary(max_entries=5, visible_only=True)


# ==================== INITIALIZATION ====================

def initialize_changelog_entries():
    """Seed the changelog with initial entries (for fresh setup)."""
    collection = get_system_changelog_collection()
    
    if collection.count_documents({}) > 0:
        logger.info("[changelog] Changelog already initialized, skipping seed")
        return
    
    logger.info("[changelog] Seeding initial changelog entries...")
    
    seed_entries = [
        {
            "domain": "infra",
            "summary": "Implemented system state resolver for platform-wide overlay effects.",
            "details": [
                "Added system_state_resolver.py for seasonal/event state management",
                "Integrated system state context into conversation pipeline",
                "Supports hierarchical state stacking with priority-based merging",
            ],
            "visible_to_users": True,
            "introduced_at": datetime.utcnow(),
            "operator_id": None,
        },
        {
            "domain": "persona",
            "summary": "Added intent-driven devlog injection for META_SYSTEM queries.",
            "details": [
                "New META_SYSTEM intent for self-referential questions",
                "Devlog entries only injected when user asks about Abby",
                "Prevents hallucination by reading facts from database, not generating them",
            ],
            "visible_to_users": True,
            "introduced_at": datetime.utcnow(),
            "operator_id": None,
        },
    ]
    
    try:
        result = collection.insert_many(seed_entries)
        logger.info(f"[changelog] Seeded {len(result.inserted_ids)} initial entries")
    except Exception as exc:
        logger.error(f"[changelog] Failed to seed entries: {exc}")
