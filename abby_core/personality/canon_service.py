"""Canon staging and commit service.

Provides staging, approval, and rejection flows for canon documents.
All commit logic is centralized here; Discord/UI layers must call these
helpers instead of touching collections directly.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from abby_core.database import mongodb
from abby_core.observability.logging import logging
from abby_core.personality.schema import (
    CanonArtifact,
    CanonCommit,
    CanonOriginType,
    CanonStagingDocument,
    CanonStatus,
    CanonType,
    CanonicalDocument,
)

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 12000

CANON_COLLECTION_BY_TYPE = {
    CanonType.BOOK: mongodb.get_canon_frontmatter_collection,
    CanonType.LORE: mongodb.get_canon_lore_collection,
    CanonType.PERSONA: mongodb.get_canon_persona_identity_collection,
    CanonType.APPENDIX: mongodb.get_canon_appendix_collection,
}


def _slugify(text: str, max_length: int = 64) -> str:
    """Create a safe slug for canonical ids."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = uuid4().hex[:8]
    return slug[:max_length]


def _resolve_target_collection(canon_type: CanonType):
    if canon_type not in CANON_COLLECTION_BY_TYPE:
        raise ValueError(f"Unsupported canon type: {canon_type}")
    return CANON_COLLECTION_BY_TYPE[canon_type]()


def _compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _generate_canonical_id(artifact: CanonArtifact, canon_type: CanonType, version: int = 1) -> str:
    """Generate deterministic canonical ID from artifact structure."""
    parts = [canon_type.value]
    
    # Lore: Skip artifact name (redundant - canon_type already scopes it)
    # Use domain.topic directly for cleaner IDs
    if canon_type == CanonType.LORE:
        # Lore uses domain.topic structure only
        if artifact.domain:
            parts.append(artifact.domain.lower().replace("-", "_"))
        if artifact.topic:
            parts.append(_slugify(artifact.topic))
    else:
        # Books, Persona, Appendix: Include artifact name
        parts.append(_slugify(artifact.name))
        
        # Add structural parts based on artifact type
        # Use underscores for section/domain (not hyphens)
        if artifact.section:
            parts.append(artifact.section.lower().replace("-", "_"))
        if artifact.chapter:
            parts.append(_slugify(artifact.chapter))
        if artifact.topic:
            parts.append(_slugify(artifact.topic))
        # Persona can have optional domain (scope: global, book, moderation)
        if canon_type == CanonType.PERSONA and artifact.domain:
            parts.append(artifact.domain.lower().replace("-", "_"))
    
    # Add version suffix
    canonical_id = ".".join(parts)
    return f"{canonical_id}.v{version}"


def stage_document(
    *,
    title: str,
    canon_type: CanonType,
    artifact: CanonArtifact,
    content: str,
    submitted_by: str,
    origin_type: CanonOriginType,
    part_label: Optional[str] = None,
    source_ref: Optional[Dict[str, str]] = None,
) -> Dict:
    """Stage a document for review. Mutable until approved/rejected."""
    clean_content = content.strip()
    if len(clean_content) > MAX_CONTENT_LENGTH:
        raise ValueError("Content exceeds maximum length of 12000 characters")

    target_collection_name = {
        CanonType.BOOK: "book_frontmatter",
        CanonType.LORE: "lore_documents",
        CanonType.PERSONA: "persona_identity",
        CanonType.APPENDIX: "canon_appendix",
    }[canon_type]

    target_id_preview = _generate_canonical_id(artifact, canon_type)

    staged = CanonStagingDocument(
        title=title.strip(),
        canon_type=canon_type,
        artifact=artifact,
        content=clean_content,
        part_label=part_label.strip() if part_label else None,
        status=CanonStatus.STAGED,
        submitted_by=submitted_by,
        origin_type=origin_type,
        source_ref=source_ref,
        target_collection=target_collection_name,
        target_id_preview=target_id_preview,
    )

    doc = staged.model_dump(by_alias=True)
    col = mongodb.get_canon_staging_collection()
    col.insert_one(doc)
    logger.info("[CANON] Staged document %s (%s) by %s", staged.id, canon_type.value, submitted_by)
    return doc


def list_staged_documents(statuses: Optional[List[CanonStatus]] = None, limit: int = 20) -> List[Dict]:
    col = mongodb.get_canon_staging_collection()
    query = {}
    if statuses:
        query["status"] = {"$in": [s.value for s in statuses]}
    cursor = col.find(query).sort("submitted_at", -1).limit(limit)
    return list(cursor)


def get_staging_document(staging_id: str) -> Optional[Dict]:
    col = mongodb.get_canon_staging_collection()
    return col.find_one({"_id": staging_id})


def get_persona_overlays(persona: str, domains: List[str], persona_aliases: Optional[List[str]] = None) -> List[Dict]:
    """Retrieve approved persona canon overlays for given domains.
    
    Args:
        persona: Primary persona name (e.g., 'bunny')
        persona_aliases: Optional additional names/aliases (e.g., ['abby', 'Abby'])
        domains: List of domain scopes to query (e.g., ['global', 'writing'])
    
    Returns:
        List of persona canon documents matching domains, ordered by specificity
    
    Example:
        overlays = get_persona_overlays('bunny', ['global', 'writing'], persona_aliases=['abby'])
        # Matches persona.abby.* and persona.bunny.*
    """
    logger.info(f"[CANON] 🔍 Fetching persona overlays for '{persona}' with domains: {domains}")
    try:
        collection = mongodb.get_canon_persona_identity_collection()

        # Build set of slugged persona keys (lowercase, dash separated) to match canonical_id prefixes
        raw_names = [persona] + (persona_aliases or [])
        slugged_names = []
        for name in raw_names:
            if not name:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or name.lower()
            slugged_names.append(slug)
        persona_keys = list({n for n in slugged_names if n}) or [persona.lower()]

        # Regex that matches any of the persona keys, case-insensitive
        if len(persona_keys) == 1:
            persona_regex = f"^persona\\.{persona_keys[0]}\\."
        else:
            joined = "|".join(re.escape(k) for k in persona_keys)
            persona_regex = f"^persona\\.(?:{joined})\\."

        domains_lower = [d.lower() for d in domains]
        domain_filter_values = list({*domains_lower, *domains, *[d.title() for d in domains_lower]})
        
        # Build query: match persona name (case-insensitive) and domain in list (or null for global)
        query: Dict[str, Any] = {
            "canonical_id": {"$regex": persona_regex, "$options": "i"}
        }
        
        # Filter by domains if provided
        # Domain can be in canonical_id or in artifact.domain
        if domains:
            # Match either: no domain (implicit global) or explicit domain in ID (case-insensitive list)
            query["$or"] = [
                {"artifact.domain": {"$in": domain_filter_values}},
                {"artifact.domain": {"$exists": False}},  # Treat missing as global
                {"artifact.domain": None},
            ]
        
        logger.debug(f"[CANON] Query: {query}")
        
        # Get latest version of each slot
        overlays = list(collection.find(query).sort([
            ("artifact.domain", 1),  # global (None) first, then specific domains
            ("version", -1),  # Latest version
        ]))
        total_for_persona = collection.count_documents({
            "canonical_id": {"$regex": persona_regex, "$options": "i"}
        })
        
        if overlays:
            logger.info(f"[CANON] ✅ Retrieved {len(overlays)} persona overlays (keys={persona_keys}):")
            for overlay in overlays:
                slot = overlay.get("artifact", {}).get("topic", "unknown")
                domain = overlay.get("artifact", {}).get("domain", "global")
                canonical_id = overlay.get("canonical_id", "unknown")
                content_preview = overlay.get("content", "")[:50] + "..." if len(overlay.get("content", "")) > 50 else overlay.get("content", "")
                logger.info(f"[CANON]   - {canonical_id} | slot={slot} domain={domain} | \"{content_preview}\"")
        else:
            logger.info(
                f"[CANON] ℹ️ No persona overlays found for keys={persona_keys} with domains {domains}. "
                f"Total overlays for persona keys (any domain): {total_for_persona}"
            )
        
        return overlays
    
    except Exception as e:
        logger.error(f"[CANON] Failed to get persona overlays: {e}", exc_info=True)
        return []


def approve_document(staging_id: str, approver_id: str, approval_notes: Optional[str] = None) -> Dict:
    """Approve and canonize a staged document. Immutable commit."""
    col = mongodb.get_canon_staging_collection()
    staged = col.find_one({"_id": staging_id})
    if not staged:
        raise ValueError("Staged document not found")

    status = staged.get("status")
    if status not in {CanonStatus.STAGED.value, CanonStatus.REVIEWED.value}:
        raise ValueError(f"Cannot approve document in status '{status}'")

    canon_type = CanonType(staged["canon_type"])
    target_collection_name = staged["target_collection"]
    target_collection = _resolve_target_collection(canon_type)

    canonical_id = staged.get("target_id_preview")
    existing_count = target_collection.count_documents({"canonical_id": canonical_id})
    version = existing_count + 1

    checksum = _compute_checksum(staged["content"])

    # Reconstruct artifact from staged document
    artifact_data = staged.get("artifact", {})
    artifact = CanonArtifact(**artifact_data)

    canonical_doc = CanonicalDocument(
        canonical_id=canonical_id,
        version=version,
        title=staged["title"],
        artifact=artifact,
        content=staged["content"],
        part_label=staged.get("part_label"),
        canon_type=canon_type,
        approved_by=approver_id,
        staging_id=staging_id,
        checksum=checksum,
        metadata={
            "origin_type": staged.get("origin_type"),
            "source_ref": staged.get("source_ref"),
        },
    ).model_dump()

    target_collection.insert_one(canonical_doc)

    commit_doc = CanonCommit(
        staging_id=staging_id,
        canonical_id=canonical_id,
        canonical_collection=target_collection_name,
        version=version,
        approved_by=approver_id,
        checksum=checksum,
    ).model_dump()
    mongodb.get_canon_commits_collection().insert_one(commit_doc)

    col.update_one(
        {"_id": staging_id},
        {
            "$set": {
                "status": CanonStatus.APPROVED.value,
                "reviewed_by": approver_id,
                "reviewed_at": datetime.utcnow(),
                "approval_notes": approval_notes,
            }
        },
    )

    logger.info("[CANON] Approved %s -> %s v%s", staging_id, canonical_id, version)
    return {
        "canonical_id": canonical_id,
        "version": version,
        "checksum": checksum,
        "canonical_collection": target_collection_name,
    }


def reject_document(staging_id: str, reviewer_id: str, notes: Optional[str] = None) -> Dict:
    """Reject a staged document. Terminal state."""
    col = mongodb.get_canon_staging_collection()
    staged = col.find_one({"_id": staging_id})
    if not staged:
        raise ValueError("Staged document not found")

    status = staged.get("status")
    if status not in {CanonStatus.STAGED.value, CanonStatus.REVIEWED.value}:
        raise ValueError(f"Cannot reject document in status '{status}'")

    col.update_one(
        {"_id": staging_id},
        {
            "$set": {
                "status": CanonStatus.REJECTED.value,
                "reviewed_by": reviewer_id,
                "reviewed_at": datetime.utcnow(),
                "approval_notes": notes,
            }
        },
    )
    logger.info("[CANON] Rejected %s by %s", staging_id, reviewer_id)
    return {"status": CanonStatus.REJECTED.value}