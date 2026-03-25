# Distribution Releases - Implementation Guide

## Phase 1 & 2 Implementation Complete ✅

All database-level infrastructure is now in place for distribution releases architecture.

---

## Files Created

### 1. **distribution_releases.py** - Collection Module

Location: `abby_core/database/collections/distribution_releases.py`

**Purpose**: Manages distribution releases in their own collection
**Exports**:

- `DistributionReleases.create_release()` - Create new release
- `DistributionReleases.mark_released()` - Move from scheduled → released
- `DistributionReleases.get_by_proton_id()` - Lookup release
- `DistributionReleases.get_artist_releases()` - Get releases for artist
- `DistributionReleases.get_label_releases()` - Get all label releases
- `DistributionReleases.record_promotion()` - Track promotion

**Indexes Created**:

- `proton_release_id` (unique): Fast Proton lookups
- `label_id`: Filter by label
- `collaborating_artists.user_id`: Find artist's releases
- `release_date`: Chronological queries
- `status`: Filter by status

### 2. **distribution_service.py** - Service Layer

Location: `abby_core/services/distribution_service.py`

**Purpose**: High-level operations for syncing and linking releases

**Key Methods**:

- `sync_release_to_artists()` - **Main sync operation**
  - Called when Proton release goes live
  - Adds release to each collaborator's `users.releases[]`
  - Handles artist verification
- `validate_release_before_sync()` - Pre-flight checks
  - Verify all artists exist
  - Check release status
- `get_artist_profile_releases()` - Query by source
  - Returns releases split by: auto_detected, user_curated, distribution

### 3. **add_release_source.py** - Migration Script

Location: `abby_core/database/collections/migrations/add_release_source.py`

**Purpose**: Migrate existing releases to include `source` field

**Usage**:

```python
from abby_core.database.collections.migrations.add_release_source import run_migration, verify_migration

## Run migration
result = run_migration()
print(result)  # {"status": "success", "users_updated": X, "releases_updated": Y}

## Verify results
verification = verify_migration()
print(verification)  # Shows source breakdown
```python

### 4. **test_distribution_schema.py** - Tests

Location: `tests/test_distribution_schema.py`

**Purpose**: Validate schema and query patterns

**Run Tests**:

```bash
python -m pytest tests/test_distribution_schema.py -v
```python

---

## Schema Changes

### users.releases[] (Embedded Array)

**NEW FIELDS** - Now included with each release:

```python
{
    "source": "auto_detected" | "user_curated" | "distribution",
    "distribution_release_id": ObjectId  # Reference to distribution_releases (optional)
}
```python

**Example**:

```json
{
  "releases": [
    {
      "_id": ObjectId(),
      "title": "My Song",
      "platform": "spotify",
      "source": "auto_detected",      // NEW
      "distribution_release_id": null // NEW
    },
    {
      "_id": ObjectId(),
      "title": "Collaborative Track",
      "source": "distribution",        // NEW
      "distribution_release_id": ObjectId("507f1f77...")  // NEW - Links to distribution_releases
    }
  ]
}
```python

### distribution_releases (NEW Collection)

**Structure**:

```json
{
  "_id": ObjectId(),
  "label_id": "proton",
  "release_title": "Neon Visions",
  "release_type": "single",
  "featured_artist": "Z8phyr",
  "collaborating_artists": [
    {
      "user_id": "246030816692404234",
      "name": "Z8phyr",
      "role": "producer"
    }
  ],
  "distribution_data": {
    "proton_release_id": "PRO_2026_001",
    "status": "scheduled" | "released" | "archived",
    "release_date": ISODate(),
    "platforms_live": ["spotify", "apple_music"],
    "cover_art_url": "https://...",
    "duration": 180
  },
  "promotion_data": {
    "promoted_users": [],
    "feature_count": 0,
    "last_featured": null
  },
  "created_at": ISODate(),
  "updated_at": ISODate()
}
```python

---

## How the System Works

### Three Release Pathways

#### 1. Auto-Detected (User shares link)

```python
User: "Check my new track!"
Link: https://open.spotify.com/track/123
  ↓
Bot extracts link and verifies
  ↓
Adds to users.releases[]
{
  "source": "auto_detected",
  "distribution_release_id": null
}
```python

#### 2. User-Curated (Manual via Discord View)

```python
User opens /release_manager View
  ↓
Fills: Title, URL, Genre, etc.
  ↓
Adds to users.releases[]
{
  "source": "user_curated",
  "distribution_release_id": null
}
```python

#### 3. Distribution (Proton → Sync)

```python
You schedule in Proton admin
  ↓
Creates distribution_releases doc
  ↓
When released, calls sync_release_to_artists()
  ↓
Automatically adds to each collaborator's users.releases[]
{
  "source": "distribution",
  "distribution_release_id": ObjectId("...")
}
```python

---

## Getting Started

### Step 1: Initialize Collections & Indexes

The indexes are automatically created when you first use the modules. To explicitly create them:

```python
from abby_core.database.collections.users import ensure_indexes
from abby_core.database.collections.distribution_releases import DistributionReleases

## Ensure indexes exist
ensure_indexes()  # Creates release source/distribution_release_id indexes
DistributionReleases.ensure_indexes()  # Creates distribution_releases collection
```python

### Step 2: Run Migration on Existing Data

```python
from abby_core.database.collections.migrations.add_release_source import run_migration

## Migrate existing releases
result = run_migration()
print(f"Updated {result['users_updated']} users, {result['releases_updated']} releases")

## Verify
from abby_core.database.collections.migrations.add_release_source import verify_migration
verification = verify_migration()
print(verification)
```python

### Step 3: Create Test Distribution Release

```python
from abby_core.database.collections.distribution_releases import DistributionReleases
from datetime import datetime

release = DistributionReleases.create_release(
    proton_release_id="TEST_001",
    release_title="Test Track",
    release_type="single",
    featured_artist="TestArtist",
    collaborating_artists=[
        {"user_id": "246030816692404234", "name": "TestArtist", "role": "producer"}
    ],
    scheduled_date=datetime.utcnow(),
    genres=["electronic"],
    description="A test release"
)

print(f"Created release: {release['_id']}")
```python

### Step 4: Sync to Artists When Released

```python
from abby_core.services.distribution_service import DistributionService

## Before syncing, validate
validation = DistributionService.validate_release_before_sync("TEST_001")
if validation["valid"]:
    # Sync when release goes live
    result = DistributionService.sync_release_to_artists(
        proton_release_id="TEST_001",
        platforms_live=["spotify", "apple_music"]
    )
    print(f"Synced to {len(result['synced'])} artists")
else:
    print(f"Validation failed: {validation['errors']}")
```python

### Step 5: Query Releases in Different Ways

```python
from abby_core.services.distribution_service import DistributionService
from abby_core.database.collections.users import Users
from abby_core.database.collections.distribution_releases import DistributionReleases

## Get user's releases by source
releases_by_source = DistributionService.get_artist_profile_releases(user_id)
print(f"Auto-detected: {len(releases_by_source['auto_detected'])}")
print(f"User-curated: {len(releases_by_source['user_curated'])}")
print(f"Distribution: {len(releases_by_source['distribution'])}")

## Get all artist's distribution releases
dist_releases = DistributionReleases.get_artist_releases(user_id, status="released")

## Get all label releases
all_label_releases = DistributionReleases.get_label_releases()
```python

---

## No Breaking Changes ✅

### What Still Works

- ✅ Existing user profiles (unchanged)
- ✅ Existing releases array (just added fields)
- ✅ All current queries (indexes added, old ones still work)
- ✅ Auto-detect functionality (when implemented)
- ✅ User-curated releases (when implemented)

### What's New

- ✅ `distribution_releases` collection (independent)
- ✅ `source` field on releases (optional, defaults to user_curated)
- ✅ `distribution_release_id` field (optional reference)
- ✅ Sync service (new code path only)

---

## Next Steps When Ready

### Phase 1B: Integrate with Proton

1. Get Proton API credentials
2. Build webhook endpoint: `POST /api/proton/webhook/release-live`
3. When webhook fires:
   ```python
   result = DistributionService.sync_release_to_artists(
       proton_release_id=webhook_data["release_id"],
       platforms_live=webhook_data["platforms"]
   )
   ```

### Phase 2: Promotion Features

1. Query recent distribution releases:
   ```python
   candidates = DistributionService.get_promotion_candidates(days_recent=7)
   ```

1. Send promo messages with release info
2. Track promotion with `record_promotion()`
3. Build analytics dashboard

### Phase 3: Multi-Domain Support

When adding art, programming, writing domains:

1. Add domain-specific fields to `creative_profile.domains`
2. Update release type/platform as needed
3. Use same sync/service patterns
4. No schema changes needed

---

## Database Queries for Common Use Cases

### Find all distribution releases this week

```python
from datetime import datetime, timedelta

releases = DistributionReleases.get_released_between(
    start_date=datetime.utcnow() - timedelta(days=7),
    end_date=datetime.utcnow()
)
```python

### Find artist's distribution releases

```python
artist_releases = DistributionReleases.get_artist_releases(
    user_id="246030816692404234",
    status="released"
)
```python

### Find users with recent distribution releases

```python
users_with_recent = Users.get_collection().find({
    "releases": {
        "$elemMatch": {
            "source": "distribution",
            "shared_at": {"$gte": datetime.utcnow() - timedelta(days=7)}
        }
    }
})
```python

### Get release and all its collaborators

```python
dist_release = DistributionReleases.get_by_proton_id("PRO_2026_001")
user_ids = [a["user_id"] for a in dist_release["collaborating_artists"]]
collaborators = Users.get_collection().find({
    "user_id": {"$in": user_ids}
})
```python

---

## Architecture Ready for Scaling

| Scale | Status | Notes |
| -------------- | -------- | --------------------------- |
| 5-10 artists | ✅ Ready | Current setup |
| 50-100 artists | ✅ Ready | No schema changes needed |
| 500+ artists | ✅ Ready | Add caching layer if needed |

The hybrid approach (embedded user releases + separate distribution collection) scales because:

- User queries are fast (embedded, indexed)
- Label queries are fast (separate collection, indexed)
- No joins between collections needed
- All indexes are in place

---

## Summary

### What's deployed:

- ✅ distribution_releases collection with all indexes
- ✅ users.releases[] with source and distribution_release_id fields
- ✅ Migration script for existing releases
- ✅ DistributionService for sync/linking operations
- ✅ Test suite for validation

### What's ready:

- ✅ When you have Proton integration ready
- ✅ Can schedule releases and sync to artists immediately
- ✅ Can query all three pathways (auto, curated, distribution)
- ✅ Foundation for multi-domain expansion

### Next when you're ready:

- Proton webhook integration
- Promotion/promo message integration
- Analytics dashboard
- Domain expansion (art, programming, etc.)
