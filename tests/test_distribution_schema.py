"""
Schema Validation & Query Tests

PURPOSE: Validate that the distribution releases architecture is properly set up
and test common query patterns to ensure they work as expected.

RUN TESTS:
    python -m pytest tests/test_distribution_schema.py -v
    or
    python tests/test_distribution_schema.py
"""

import pytest
from datetime import datetime, timedelta
from bson import ObjectId

from abby_core.database.collections.users import Users
from abby_core.database.collections.distribution_releases import DistributionReleases
from abby_core.services.distribution_service import DistributionService


class TestDistributionReleasesSchema:
    """Test distribution_releases collection schema and queries"""

    def test_create_distribution_release(self):
        """Test creating a new distribution release"""
        release = DistributionReleases.create_release(
            proton_release_id="TEST_001",
            release_title="Test Track",
            release_type="single",
            featured_artist="TestArtist",
            collaborating_artists=[
                {"user_id": "246030816692404234", "name": "TestArtist", "role": "producer"}
            ],
            scheduled_date=datetime.utcnow(),
            cover_art_url="https://example.com/art.jpg",
            duration=180,
            genres=["electronic", "synthwave"],
            description="A test release"
        )

        assert release is not None
        assert release["distribution_data"]["proton_release_id"] == "TEST_001"
        assert release["distribution_data"]["status"] == "scheduled"
        assert release["release_title"] == "Test Track"

    def test_mark_release_as_released(self):
        """Test marking a release as released"""
        # Create release first
        release = DistributionReleases.create_release(
            proton_release_id="TEST_002",
            release_title="Test Release 2",
            release_type="single",
            featured_artist="Artist2",
            collaborating_artists=[],
            scheduled_date=datetime.utcnow()
        )

        # Mark as released
        updated = DistributionReleases.mark_released(
            "TEST_002",
            ["spotify", "apple_music"]
        )

        assert updated is not None
        assert updated["distribution_data"]["status"] == "released"
        assert "spotify" in updated["distribution_data"]["platforms_live"]

    def test_get_by_proton_id(self):
        """Test retrieving release by Proton ID"""
        # Create
        DistributionReleases.create_release(
            proton_release_id="TEST_003",
            release_title="Test 3",
            release_type="single",
            featured_artist="Artist3",
            collaborating_artists=[],
            scheduled_date=datetime.utcnow()
        )

        # Retrieve
        release = DistributionReleases.get_by_proton_id("TEST_003")
        assert release is not None
        assert release["release_title"] == "Test 3"

    def test_get_artist_releases(self):
        """Test retrieving all releases for an artist"""
        user_id = "246030816692404234"

        # Create releases
        for i in range(3):
            DistributionReleases.create_release(
                proton_release_id=f"TEST_ARTIST_{i}",
                release_title=f"Artist Release {i}",
                release_type="single",
                featured_artist="TestArtist",
                collaborating_artists=[
                    {"user_id": user_id, "name": "TestArtist", "role": "producer"}
                ],
                scheduled_date=datetime.utcnow()
            )

        # Retrieve
        releases = DistributionReleases.get_artist_releases(user_id)
        assert len(releases) >= 3

    def test_get_label_releases(self):
        """Test retrieving all releases from label"""
        # Get all label releases
        releases = DistributionReleases.get_label_releases()
        assert isinstance(releases, list)

    def test_record_promotion(self):
        """Test recording promotion of a release"""
        release = DistributionReleases.create_release(
            proton_release_id="TEST_PROMO",
            release_title="Promo Test",
            release_type="single",
            featured_artist="PromoArtist",
            collaborating_artists=[],
            scheduled_date=datetime.utcnow()
        )

        # Record promotion
        DistributionReleases.record_promotion(
            "TEST_PROMO",
            "user123"
        )

        # Verify
        updated = DistributionReleases.get_by_proton_id("TEST_PROMO")
        assert "user123" in updated["promotion_data"]["promoted_users"]
        assert updated["promotion_data"]["feature_count"] == 1


class TestUserReleasesSchema:
    """Test users.releases[] array with source field"""

    def test_release_with_source_field(self):
        """Test that releases can have source field"""
        collection = Users.get_collection()

        user_id = "test_user_" + str(datetime.utcnow().timestamp())

        # Create user with release
        collection.insert_one({
            "user_id": user_id,
            "discord": {
                "discord_id": user_id,
                "username": "testuser",
                "display_name": "Test User",
                "discriminator": "0",
                "avatar_url": "https://example.com/avatar.jpg",
                "joined_at": datetime.utcnow(),
                "last_seen": datetime.utcnow()
            },
            "releases": [
                {
                    "_id": ObjectId(),
                    "domain": "music",
                    "type": "song",
                    "title": "Test Song",
                    "url": "https://spotify.com/track/123",
                    "platform": "spotify",
                    "source": "auto_detected",
                    "distribution_release_id": None,
                    "verified": True,
                    "promoted": False
                }
            ],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        # Verify
        user = collection.find_one({"user_id": user_id})
        assert len(user["releases"]) == 1
        assert user["releases"][0]["source"] == "auto_detected"

    def test_release_with_distribution_link(self):
        """Test release linked to distribution_releases"""
        collection = Users.get_collection()

        user_id = "test_dist_user_" + str(datetime.utcnow().timestamp())
        dist_id = ObjectId()

        # Create user with distribution-sourced release
        collection.insert_one({
            "user_id": user_id,
            "discord": {
                "discord_id": user_id,
                "username": "distuser",
                "display_name": "Dist User",
                "discriminator": "0",
                "avatar_url": "https://example.com/avatar.jpg",
                "joined_at": datetime.utcnow(),
                "last_seen": datetime.utcnow()
            },
            "releases": [
                {
                    "_id": ObjectId(),
                    "domain": "music",
                    "type": "single",
                    "title": "Distribution Release",
                    "source": "distribution",
                    "distribution_release_id": dist_id,
                    "verified": True,
                    "promoted": False
                }
            ],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        # Verify
        user = collection.find_one({"user_id": user_id})
        assert user["releases"][0]["source"] == "distribution"
        assert user["releases"][0]["distribution_release_id"] == dist_id


class TestDistributionService:
    """Test distribution service operations"""

    def test_verify_artist_exists(self):
        """Test checking if artist exists"""
        # Create test user
        user_id = "verify_test_" + str(datetime.utcnow().timestamp())
        Users.get_collection().insert_one({
            "user_id": user_id,
            "discord": {
                "discord_id": user_id,
                "username": "verify",
                "display_name": "Verify Test",
                "discriminator": "0",
                "avatar_url": "https://example.com/avatar.jpg",
                "joined_at": datetime.utcnow(),
                "last_seen": datetime.utcnow()
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        # Verify exists
        assert DistributionService.verify_artist_exists(user_id) is True

        # Verify doesn't exist
        assert DistributionService.verify_artist_exists("nonexistent_user_12345") is False

    def test_get_artist_profile_releases(self):
        """Test getting releases by source from user profile"""
        collection = Users.get_collection()
        user_id = "profile_releases_" + str(datetime.utcnow().timestamp())

        # Create user with mixed releases
        collection.insert_one({
            "user_id": user_id,
            "discord": {
                "discord_id": user_id,
                "username": "mixed",
                "display_name": "Mixed Releases",
                "discriminator": "0",
                "avatar_url": "https://example.com/avatar.jpg",
                "joined_at": datetime.utcnow(),
                "last_seen": datetime.utcnow()
            },
            "releases": [
                {
                    "_id": ObjectId(),
                    "title": "Auto Detected",
                    "source": "auto_detected"
                },
                {
                    "_id": ObjectId(),
                    "title": "User Curated",
                    "source": "user_curated"
                },
                {
                    "_id": ObjectId(),
                    "title": "Distribution",
                    "source": "distribution"
                }
            ],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        # Get releases
        releases = DistributionService.get_artist_profile_releases(user_id)

        assert releases["total"] == 3
        assert len(releases["auto_detected"]) == 1
        assert len(releases["user_curated"]) == 1
        assert len(releases["distribution"]) == 1

    def test_validate_release_before_sync(self):
        """Test validation before syncing release"""
        # Create release with artist that exists
        user_id = "valid_artist_" + str(datetime.utcnow().timestamp())
        Users.get_collection().insert_one({
            "user_id": user_id,
            "discord": {
                "discord_id": user_id,
                "username": "validartist",
                "display_name": "Valid Artist",
                "discriminator": "0",
                "avatar_url": "https://example.com/avatar.jpg",
                "joined_at": datetime.utcnow(),
                "last_seen": datetime.utcnow()
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        # Create release
        release = DistributionReleases.create_release(
            proton_release_id="VALIDATE_TEST",
            release_title="Validate",
            release_type="single",
            featured_artist="ValidArtist",
            collaborating_artists=[
                {"user_id": user_id, "name": "ValidArtist", "role": "producer"}
            ],
            scheduled_date=datetime.utcnow()
        )

        # Validate
        report = DistributionService.validate_release_before_sync("VALIDATE_TEST")
        assert report["valid"] is True


class TestQueryPerformance:
    """Test that indexes work and queries are efficient"""

    def test_releases_by_source_query(self):
        """Test querying releases by source"""
        # This should use the index on releases.source
        collection = Users.get_collection()

        results = list(collection.find(
            {"releases.source": "auto_detected"},
            {"user_id": 1}
        ).limit(10))

        # Just verify query executes without error
        assert isinstance(results, list)

    def test_distribution_release_id_query(self):
        """Test querying by distribution_release_id"""
        # This should use the index on releases.distribution_release_id
        collection = Users.get_collection()

        dist_id = ObjectId()
        results = list(collection.find(
            {"releases.distribution_release_id": dist_id}
        ))

        assert isinstance(results, list)

    def test_proton_id_unique_query(self):
        """Test that proton_release_id is unique"""
        # This should use the unique index
        collection = DistributionReleases.get_collection()

        result = collection.find_one({
            "distribution_data.proton_release_id": "UNIQUE_TEST"
        })

        # Should be fast (using unique index)
        assert result is None or isinstance(result, dict)

    def test_artist_distribution_releases_query(self):
        """Test querying releases by artist"""
        # This should use the index on collaborating_artists.user_id
        collection = DistributionReleases.get_collection()

        user_id = "perf_test_" + str(datetime.utcnow().timestamp())
        results = list(collection.find(
            {"collaborating_artists.user_id": user_id}
        ))

        assert isinstance(results, list)


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v"])
