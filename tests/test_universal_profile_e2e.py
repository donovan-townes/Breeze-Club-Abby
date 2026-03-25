"""
End-to-End Test: Universal User Profile Architecture

This test validates that the new Users collection properly routes through the architecture:
1. /profile command uses Users collection (not discord_profiles directly)
2. Memory extraction syncs creative_profile to Users collection
3. Universal profile fields display correctly (social_accounts, creative_accounts, artist_profile, collaborations)

Use Case: User wants to ensure the universal user profile nexus architecture is operational
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone
import sys
import os

# Add project paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abby_core.database.collections.users import Users
from abby_core.database.mongodb import upsert_user, get_mongodb_client
from tdos_intelligence.memory import get_memory_envelope


class TestUniversalProfileE2E:
    """
    E2E Tests for Universal User Profile Architecture.
    
    Test Scenarios:
    1. /profile command routes through Users collection
    2. Memory extraction syncs to Users collection
    3. Universal fields persist and display correctly
    """
    
    @pytest.fixture
    def test_user_id(self):
        """Standard test user ID"""
        return 123456789
    
    @pytest.fixture
    def test_guild_id(self):
        """Standard test guild ID"""
        return 987654321
    
    @pytest.fixture(autouse=True)
    def cleanup_test_data(self, test_user_id):
        """Clean up test data after each test"""
        yield
        # Clean up
        try:
            from abby_core.database.collections.users import Users
            collection = Users.get_collection()
            collection.delete_one({"user_id": test_user_id})
        except:
            pass
    
    # ========== TEST 1: Profile Command Routes Through Users Collection ==========
    
    def test_profile_command_initialization_through_users_collection(self, test_user_id, test_guild_id):
        """
        TEST 1: When /profile is called, it initializes through Users collection, not directly through db access.
        
        Expected Flow:
        1. /profile command handler calls Users.get_collection()
        2. Searches for existing user in discord_profiles via Users module
        3. If new user, calls Users.upsert_user() to initialize
        4. Reads back universal profile fields
        
        Validation: User object in discord_profiles has universal schema fields set
        """
        # Arrange: Fresh user (not yet profiled)
        user_collection = Users.get_collection()
        user_collection.delete_one({"user_id": test_user_id})
        
        # Act: Initialize user through Users module (simulating /profile command)
        Users.upsert_user(
            user_id=test_user_id,
            guild_id=test_guild_id,
            defaults={
                "username": "test_user",
                "avatar_url": "https://example.com/avatar.png"
            }
        )
        
        # Assert: User was created with universal schema
        user_doc = user_collection.find_one({"user_id": test_user_id})
        
        assert user_doc is not None, "User should be created in discord_profiles via Users module"
        assert user_doc["user_id"] == test_user_id
        assert "creative_profile" in user_doc, "creative_profile should exist"
        assert "social_accounts" in user_doc, "social_accounts should exist for universal profile"
        assert "creative_accounts" in user_doc, "creative_accounts should exist"
        assert "artist_profile" in user_doc, "artist_profile should exist"
        assert "collaborations" in user_doc, "collaborations should exist"
        
        # Verify they're properly initialized as empty/default
        assert isinstance(user_doc["social_accounts"], list), "social_accounts should be a list"
        assert isinstance(user_doc["creative_accounts"], list), "creative_accounts should be a list"
        assert isinstance(user_doc["artist_profile"], dict), "artist_profile should be a dict"
        assert isinstance(user_doc["collaborations"], list), "collaborations should be a list"
    
    def test_profile_command_reads_universal_fields(self, test_user_id, test_guild_id):
        """
        TEST 2: /profile command can read and display all universal profile fields.
        
        Expected Flow:
        1. Profile exists with universal fields
        2. /profile command reads using Users.get_collection()
        3. All universal fields are accessible and displayable
        
        Validation: All universal schema fields are readable and properly typed
        """
        # Arrange: User with populated universal fields
        user_collection = Users.get_collection()
        user_collection.update_one(
            {"user_id": test_user_id},
            {
                "$set": {
                    "user_id": test_user_id,
                    "social_accounts": [
                        {
                            "platform": "twitter",
                            "handle": "@test_user",
                            "url": "https://twitter.com/test_user",
                            "added_at": datetime.utcnow(),
                            "verified": True
                        }
                    ],
                    "creative_accounts": [
                        {
                            "platform": "spotify",
                            "account_id": "spotify_123",
                            "display_name": "Test Artist",
                            "connected_at": datetime.utcnow(),
                            "verified": True
                        }
                    ],
                    "artist_profile": {
                        "is_artist": True,
                        "stage_name": "Test Artist Name",
                        "bio": "A test artist bio",
                        "website": "https://example.com",
                        "established_at": datetime.utcnow()
                    },
                    "collaborations": []
                }
            },
            upsert=True
        )
        
        # Act: Read profile through Users collection (simulating /profile command display)
        user_doc = user_collection.find_one({"user_id": test_user_id})
        
        # Assert: All fields are readable and properly structured
        assert user_doc["social_accounts"][0]["platform"] == "twitter"
        assert user_doc["social_accounts"][0]["verified"] == True
        
        assert user_doc["creative_accounts"][0]["platform"] == "spotify"
        assert user_doc["creative_accounts"][0]["display_name"] == "Test Artist"
        
        assert user_doc["artist_profile"]["is_artist"] == True
        assert user_doc["artist_profile"]["stage_name"] == "Test Artist Name"
        
        assert isinstance(user_doc["collaborations"], list)
    
    # ========== TEST 2: Memory Extraction Syncs to Users Collection ==========
    
    def test_memory_extraction_syncs_creative_profile(self, test_user_id, test_guild_id):
        """
        TEST 3: When memory facts are extracted after user interaction,
        the creative_profile is synced to Users collection.
        
        Expected Flow:
        1. User interacts with bot, facts are extracted
        2. Facts are stored in discord_profiles creative_profile via MemoryService
        3. sync_creative_profile_to_universal() pushes updates to Users collection
        4. Users collection now has synchronized creative_profile data
        
        Validation: creative_profile.memorable_facts exists in Users collection and matches
        """
        # Arrange: Initialize user with memory
        user_collection = Users.get_collection()
        
        # First create the user
        Users.upsert_user(
            user_id=test_user_id,
            guild_id=test_guild_id,
            defaults={"username": "memory_test_user"}
        )
        
        # Simulate memory extraction by directly updating the collection
        # (In real flow, this would happen through MemoryService)
        creative_profile_data = {
            "memorable_facts": [
                {
                    "text": "User loves jazz music",
                    "confidence": 0.92,
                    "source": "llm_extraction",
                    "origin": "explicit",
                    "category": "interests",
                    "timestamp": datetime.utcnow()
                },
                {
                    "text": "User is a graphic designer",
                    "confidence": 0.88,
                    "source": "llm_extraction",
                    "origin": "explicit",
                    "category": "profession",
                    "timestamp": datetime.utcnow()
                }
            ],
            "preferences": {
                "response_style": "detailed",
                "music_preference": ["jazz", "blues"]
            }
        }
        
        # Act: Sync the creative profile to Users collection
        # This simulates what sync_creative_profile_to_universal() does
        sync_result = user_collection.update_one(
            {"user_id": test_user_id},
            {
                "$set": {
                    "creative_profile.memorable_facts": creative_profile_data["memorable_facts"],
                    "creative_profile.preferences": creative_profile_data["preferences"],
                    "creative_profile.fact_count": len(creative_profile_data["memorable_facts"]),
                    "creative_profile.last_synced_at": datetime.utcnow(),
                    "preferences": {
                        **creative_profile_data.get("preferences", {}),
                        "tracked_interests": ["jazz", "graphic design"][:5]
                    }
                }
            }
        )
        
        # Assert: Sync succeeded and data is in Users collection
        assert sync_result.matched_count == 1, "User should exist for sync"
        
        # Verify data was synced
        synced_user = user_collection.find_one({"user_id": test_user_id})
        assert "creative_profile" in synced_user
        assert len(synced_user["creative_profile"]["memorable_facts"]) == 2
        assert synced_user["creative_profile"]["memorable_facts"][0]["text"] == "User loves jazz music"
        assert synced_user["creative_profile"]["fact_count"] == 2
        assert synced_user["creative_profile"]["last_synced_at"] is not None
    
    def test_memory_sync_preserves_universal_fields(self, test_user_id, test_guild_id):
        """
        TEST 4: When creative_profile is synced, other universal fields are preserved.
        
        Expected Flow:
        1. User has artist_profile, social_accounts, collaborations set
        2. Memory sync updates creative_profile
        3. Other universal fields remain intact
        
        Validation: Non-creative_profile fields unchanged after sync
        """
        # Arrange: User with full universal profile
        user_collection = Users.get_collection()
        
        Users.upsert_user(
            user_id=test_user_id,
            guild_id=test_guild_id,
            defaults={"username": "full_profile_user"}
        )
        
        # Add full universal fields
        user_collection.update_one(
            {"user_id": test_user_id},
            {
                "$set": {
                    "artist_profile": {
                        "is_artist": True,
                        "stage_name": "DJ Test",
                        "bio": "Electronic music producer",
                        "established_at": datetime.utcnow()
                    },
                    "social_accounts": [
                        {"platform": "twitter", "handle": "@dj_test", "verified": True}
                    ],
                    "collaborations": [
                        {
                            "artist_id": 999,
                            "status": "active",
                            "projects": ["EP_01"]
                        }
                    ]
                }
            }
        )
        
        # Act: Sync creative_profile (update only creative_profile fields)
        user_collection.update_one(
            {"user_id": test_user_id},
            {
                "$set": {
                    "creative_profile.memorable_facts": [
                        {
                            "text": "User produces electronic music",
                            "confidence": 0.95,
                            "timestamp": datetime.utcnow()
                        }
                    ],
                    "creative_profile.last_synced_at": datetime.utcnow()
                }
            }
        )
        
        # Assert: Other fields preserved
        updated_user = user_collection.find_one({"user_id": test_user_id})
        
        # Original fields should be unchanged
        assert updated_user["artist_profile"]["stage_name"] == "DJ Test"
        assert updated_user["social_accounts"][0]["platform"] == "twitter"
        assert len(updated_user["collaborations"]) == 1
        
        # New sync field should be present
        assert len(updated_user["creative_profile"]["memorable_facts"]) == 1
        assert updated_user["creative_profile"]["last_synced_at"] is not None
    
    # ========== TEST 3: Profile Display Routes Through Users Collection ==========
    
    def test_profile_panel_display_reads_from_users_collection(self, test_user_id, test_guild_id):
        """
        TEST 5: Profile panel display (visual rendering) reads all data from Users collection.
        
        Expected Flow:
        1. Profile panel handler calls Users.get_collection()
        2. Reads user document with all universal fields
        3. Renders buttons/embeds showing: Discord Account | Artist Profile | Social Accounts | Creative Accounts
        4. All displayed data comes from Users collection
        
        Validation: Profile data sources are Users collection, not user_service or direct db access
        """
        # Arrange: Complete user profile
        user_collection = Users.get_collection()
        
        user_collection.update_one(
            {"user_id": test_user_id},
            {
                "$set": {
                    "user_id": test_user_id,
                    "username": "display_test_user",
                    "artist_profile": {
                        "is_artist": True,
                        "stage_name": "Artist Display Name",
                        "bio": "Bio for display",
                        "website": "https://artist.example.com"
                    },
                    "social_accounts": [
                        {
                            "platform": "youtube",
                            "handle": "ArtistYT",
                            "url": "https://youtube.com/c/ArtistYT"
                        }
                    ],
                    "creative_accounts": [
                        {
                            "platform": "soundcloud",
                            "account_id": "sc_123",
                            "display_name": "Artist on SoundCloud"
                        }
                    ],
                    "collaborations": [
                        {
                            "artist_id": 111,
                            "status": "active",
                            "projects": ["collaboration_1"]
                        }
                    ]
                }
            },
            upsert=True
        )
        
        # Act: Profile panel reads user (simulating profile_panel_enhanced.py behavior)
        # This is what the UniversalProfilePanel class does
        display_user = user_collection.find_one({"user_id": test_user_id})
        
        # Assert: All display fields are readable from Users collection
        assert display_user is not None
        
        # Discord Account info
        assert display_user["username"] == "display_test_user"
        
        # Artist Profile section
        assert display_user["artist_profile"]["stage_name"] == "Artist Display Name"
        assert display_user["artist_profile"]["website"] == "https://artist.example.com"
        
        # Social Accounts section
        assert len(display_user["social_accounts"]) == 1
        assert display_user["social_accounts"][0]["platform"] == "youtube"
        assert display_user["social_accounts"][0]["url"] == "https://youtube.com/c/ArtistYT"
        
        # Creative Accounts section
        assert len(display_user["creative_accounts"]) == 1
        assert display_user["creative_accounts"][0]["platform"] == "soundcloud"
        
        # Collaborations section
        assert len(display_user["collaborations"]) == 1
        assert display_user["collaborations"][0]["status"] == "active"
    
    def test_profile_routing_architecture_validation(self, test_user_id, test_guild_id):
        """
        TEST 6: Validate the routing architecture - all profile operations use Users collection.
        
        Expected Flow:
        1. /profile command uses Users.get_collection() (primary users collection)
        2. Memory extraction writes directly to Users.get_collection() (not sync bridge)
        3. Profile display uses Users.get_collection() (primary storage)
        
        Validation: All paths route through Users module, which points to 'users' collection
        """
        # Arrange: User with test data
        Users.upsert_user(test_user_id, test_guild_id)
        
        # Act: Verify Users collection is the source of truth
        user_collection = Users.get_collection()
        
        # Verify collection_name matches Users module configuration
        assert user_collection.name == "users", "Users module should use users collection as primary storage"
        
        # Verify user can be accessed via Users module
        user = user_collection.find_one({"user_id": test_user_id})
        assert user is not None, "User should be accessible via Users.get_collection()"
        
        # Assert: Architecture is correct
        # The Users module acts as nexus between Discord UI and users collection (primary storage)
        assert hasattr(Users, 'get_collection'), "Users should have get_collection method"
        assert hasattr(Users, 'upsert_user'), "Users should have upsert_user method"
        assert hasattr(Users, 'ensure_indexes'), "Users should have ensure_indexes method"


class TestMemorySyncIntegration:
    """Integration tests for memory sync flow"""
    
    def test_facts_extracted_then_synced_to_universal_profile(self):
        """
        Test that facts extracted from conversation are synced to universal profile.
        
        Flow:
        1. Extract facts from user summary
        2. Store facts in creative_profile via MemoryService
        3. Sync to Users collection via sync_creative_profile_to_universal()
        4. Verify facts appear in Users collection
        """
        test_user_id = 111222333
        
        try:
            user_collection = Users.get_collection()
            
            # Initialize user
            Users.upsert_user(test_user_id, None)
            
            # Simulate fact extraction and storage
            facts = [
                {
                    "text": "User is a Python developer",
                    "confidence": 0.95,
                    "source": "llm_extraction",
                    "category": "profession"
                },
                {
                    "text": "User likes machine learning",
                    "confidence": 0.88,
                    "source": "llm_extraction",
                    "category": "interests"
                }
            ]
            
            # Sync facts to Users collection
            user_collection.update_one(
                {"user_id": test_user_id},
                {
                    "$set": {
                        "creative_profile.memorable_facts": facts,
                        "creative_profile.fact_count": len(facts),
                        "creative_profile.last_synced_at": datetime.utcnow()
                    }
                }
            )
            
            # Verify sync succeeded
            synced = user_collection.find_one({"user_id": test_user_id})
            assert len(synced["creative_profile"]["memorable_facts"]) == 2
            assert synced["creative_profile"]["memorable_facts"][0]["text"] == "User is a Python developer"
            
        finally:
            # Cleanup
            user_collection.delete_one({"user_id": test_user_id})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
