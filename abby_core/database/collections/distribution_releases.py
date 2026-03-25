"""
Distribution Releases Collection Module

PURPOSE: Centralized management of music/content releases from the Proton distribution system.
Handles scheduling, release coordination, and automatic artist profile linking.

SCHEMA: Label-centric release tracking with multi-artist support
- Proton system writes release data directly
- Automatic sync to collaborating artists' user profiles (users.releases[])
- Single source of truth for distribution releases
- Independent of user documents (no data duplication)

USE CASES:
1. You schedule release in Proton admin panel
2. Bot creates distribution_releases document
3. When release goes live, bot auto-adds to each artist's users.releases[]
4. Each artist sees it in their portfolio (source: "distribution")
5. Promo system can query all label releases efficiently

RELEASE PATHWAYS:
- User-detected: Bot finds shared link → users.releases[] (source: auto_detected)
- User-curated: User adds via Discord View → users.releases[] (source: user_curated)
- Distribution: Proton system → distribution_releases → users.releases[] (source: distribution)

STRUCTURE:
{
  "_id": ObjectId,
  "label_id": "proton",
  "release_title": "Neon Visions",
  "release_type": "single|ep|album",
  "featured_artist": "Z8phyr",
  "collaborating_artists": [
    {
      "user_id": "246030816692404234",
      "name": "Z8phyr",
      "role": "producer|vocalist|feature|collaborator"
    }
  ],
  "distribution_data": {
    "proton_release_id": "PRO_2026_001",
    "status": "scheduled|released|archived",
    "scheduled_date": ISODate,
    "release_date": ISODate,
    "platforms_pending": ["spotify", "apple_music"],
    "platforms_live": [],
    "cover_art_url": "https://...",
    "duration": 180
  },
  "promotion_data": {
    "promoted_users": [],
    "feature_count": 0,
    "last_featured": null
  },
  "metadata": {
    "genres": ["synthwave", "electronic"],
    "credits": {...},
    "description": "A collaborative journey..."
  },
  "created_at": ISODate,
  "updated_at": ISODate
}

INDEXES:
- proton_release_id (unique): Lookup by Proton ID
- label_id: Filter all releases from label
- collaborating_artists.user_id: Find artist's distribution releases
- release_date (desc): Chronological queries
- status: Filter by status
- platforms_live: Discover by platform availability

SCALING:
- Current (5-10 artists): 1-2 releases/month
- Growth (50-100 artists): 5-20 releases/month
- Major (500+ artists): 50-200 releases/month
- Design supports all scales without changes
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from bson import ObjectId

if TYPE_CHECKING:
    from pymongo.collection import Collection


class DistributionReleases:
    """Distribution Releases collection manager"""

    collection_name = "distribution_releases"

    @staticmethod
    def get_collection() -> "Collection":
        """Get distribution_releases collection reference"""
        from abby_core.database import get_database
        db = get_database()
        return db[DistributionReleases.collection_name]

    @staticmethod
    def ensure_indexes() -> None:
        """Create required indexes for distribution_releases collection"""
        collection = DistributionReleases.get_collection()

        try:
            # Unique lookup by Proton release ID
            collection.create_index(
                "distribution_data.proton_release_id",
                unique=True,
                sparse=True,
                name="proton_release_id_unique"
            )

            # Filter by label
            collection.create_index(
                "label_id",
                name="label_id_lookup"
            )

            # Find artist's distribution releases
            collection.create_index(
                "collaborating_artists.user_id",
                name="artist_distribution_releases"
            )

            # Chronological queries (most recent first)
            collection.create_index(
                [("release_date", -1)],
                name="release_date_desc"
            )

            # Filter by status
            collection.create_index(
                "status",
                name="status_filter"
            )

            # Discover by platform
            collection.create_index(
                "distribution_data.platforms_live",
                name="platforms_live_search"
            )

            # Composite: label + status for efficient filtering
            collection.create_index(
                [("label_id", 1), ("status", 1)],
                name="label_status_composite"
            )

            # Promotion tracking
            collection.create_index(
                [("promotion_data.last_featured", -1)],
                name="last_featured_tracking"
            )

        except Exception as e:
            print(f"Error creating indexes on {DistributionReleases.collection_name}: {e}")

    @staticmethod
    def create_release(
        proton_release_id: str,
        release_title: str,
        release_type: str,
        featured_artist: str,
        collaborating_artists: List[Dict[str, str]],
        scheduled_date: datetime,
        cover_art_url: Optional[str] = None,
        duration: Optional[int] = None,
        genres: Optional[List[str]] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new distribution release

        Args:
            proton_release_id: Unique ID from Proton system
            release_title: Name of the release
            release_type: "single", "ep", or "album"
            featured_artist: Main artist name
            collaborating_artists: List of {"user_id": str, "name": str, "role": str}
            scheduled_date: When release is scheduled
            cover_art_url: URL to cover art
            duration: Duration in seconds
            genres: List of genres
            description: Release description
            metadata: Additional metadata

        Returns:
            Created document dict
        """
        collection = DistributionReleases.get_collection()

        release_doc = {
            "label_id": "proton",
            "release_title": release_title,
            "release_type": release_type,
            "featured_artist": featured_artist,
            "collaborating_artists": collaborating_artists,
            "distribution_data": {
                "proton_release_id": proton_release_id,
                "status": "scheduled",
                "scheduled_date": scheduled_date,
                "release_date": None,
                "platforms_pending": [],
                "platforms_live": [],
                "cover_art_url": cover_art_url,
                "duration": duration
            },
            "promotion_data": {
                "promoted_users": [],
                "feature_count": 0,
                "last_featured": None
            },
            "metadata": {
                "genres": genres or [],
                "credits": metadata.get("credits", {}) if metadata else {},
                "description": description or ""
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = collection.insert_one(release_doc)
        release_doc["_id"] = result.inserted_id
        return release_doc

    @staticmethod
    def mark_released(
        proton_release_id: str,
        platforms_live: List[str],
        release_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Mark a distribution release as live/released

        Args:
            proton_release_id: Proton release ID
            platforms_live: List of platforms now live
            release_date: Actual release date (defaults to now)

        Returns:
            Updated document
        """
        collection = DistributionReleases.get_collection()

        if release_date is None:
            release_date = datetime.utcnow()

        updated = collection.find_one_and_update(
            {"distribution_data.proton_release_id": proton_release_id},
            {
                "$set": {
                    "distribution_data.status": "released",
                    "distribution_data.release_date": release_date,
                    "distribution_data.platforms_live": platforms_live,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        return updated

    @staticmethod
    def get_by_proton_id(proton_release_id: str) -> Optional[Dict[str, Any]]:
        """Get distribution release by Proton ID"""
        collection = DistributionReleases.get_collection()
        return collection.find_one({
            "distribution_data.proton_release_id": proton_release_id
        })

    @staticmethod
    def get_artist_releases(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all distribution releases for an artist"""
        collection = DistributionReleases.get_collection()

        query = {"collaborating_artists.user_id": user_id}
        if status:
            query["distribution_data.status"] = status

        return list(collection.find(query).sort("distribution_data.release_date", -1))

    @staticmethod
    def get_label_releases(
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all releases from label, optionally filtered by status"""
        collection = DistributionReleases.get_collection()

        query = {"label_id": "proton"}
        if status:
            query["distribution_data.status"] = status

        cursor = collection.find(query).sort("distribution_data.release_date", -1)
        if limit:
            cursor = cursor.limit(limit)

        return list(cursor)

    @staticmethod
    def get_released_between(start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get releases that were released between two dates"""
        collection = DistributionReleases.get_collection()

        return list(collection.find({
            "label_id": "proton",
            "distribution_data.status": "released",
            "distribution_data.release_date": {
                "$gte": start_date,
                "$lte": end_date
            }
        }).sort("distribution_data.release_date", -1))

    @staticmethod
    def record_promotion(
        proton_release_id: str,
        user_id: str
    ) -> None:
        """Record that a release was promoted to a user"""
        collection = DistributionReleases.get_collection()

        collection.update_one(
            {"distribution_data.proton_release_id": proton_release_id},
            {
                "$push": {"promotion_data.promoted_users": user_id},
                "$inc": {"promotion_data.feature_count": 1},
                "$set": {"promotion_data.last_featured": datetime.utcnow()}
            }
        )

    @staticmethod
    def archive_release(proton_release_id: str) -> None:
        """Archive an old release"""
        collection = DistributionReleases.get_collection()

        collection.update_one(
            {"distribution_data.proton_release_id": proton_release_id},
            {
                "$set": {
                    "distribution_data.status": "archived",
                    "updated_at": datetime.utcnow()
                }
            }
        )
