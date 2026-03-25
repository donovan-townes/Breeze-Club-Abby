# Distribution & Label Releases Architecture

## Overview

The platform now supports **three independent release pathways**:

1. **User-Detected Releases** - Bot detects user shares link (Spotify, YouTube, etc.)
2. **User-Curated Releases** - User manually adds via Discord interactive View
3. **Distribution System Releases** - Scheduled via Proton distribution system, linked to artists

Each has different ownership, lifecycle, and query patterns. A **hybrid architecture** handles all three seamlessly **without breaking changes**.

---

## Architecture Decision

### Release Storage Strategy

### RECOMMENDATION: Hybrid with Two Focused Collections

```python
users.releases[]
  ├─ User-detected (auto_detected source)
  └─ User-curated (user_curated source)
     └─ Optional link to distribution_release_id

distribution_releases (separate collection)
  ├─ Proton system managed
  ├─ Single source of truth
  └─ Can link to multiple artists
```python

### Why Hybrid?

| Concern | Embedded Only | Separate Only | Hybrid ✅ |
| ------------------------- | ------------- | ---------------- | ---------------- |
| User-specific queries | ✅ Fast | ⚠️ Slow | ✅ Fast |
| "All releases from label" | ❌ Slow scan | ✅ Fast | ✅ Fast |
| Multi-artist releases | ⚠️ Duplicated | ✅ Single source | ✅ Single source |
| Breaking changes | ✅ None | ✅ None | ✅ None |
| Proton system updates | ⚠️ Complex | ✅ Simple | ✅ Simple |
| Promotion query speed | ✅ Fast | ✅ Fast | ✅✅ Fastest |

**Bottom line**: Keep user releases embedded (fast, simple), create separate collection for label (scalable, independent). Link them with `distribution_release_id`.

---

## Collection Structure

### users.releases[] (Embedded - In users collection)

**No structural change needed** for existing releases. Add optional fields:

```json
{
  "releases": [
    {
      "_id": ObjectId,
      "domain": "music",
      "type": "song",
      "title": "Midnight Echo",
      "url": "https://open.spotify.com/track/...",
      "platform": "spotify",
      "platform_id": "spotify_track_id",
      "user_url": "https://open.spotify.com/artist/...",
      "shared_at": ISODate(),
      "discovered_at": ISODate,

      // NEW: Identifies which pathway created this
      "source": "auto_detected" | "user_curated" | "distribution",

      // NEW: Reference to distribution_releases collection (if from Proton)
      "distribution_release_id": ObjectId,  // Optional - only if linked

      "metadata": {
        "streams": 1250,
        "image_url": "spotify_album_art.jpg"
      },
      "verified": true,
      "verification_method": "profile_owner",
      "promoted": false
    }
  ]
}
```python

**New fields**:

- `source`: Identifies origin (user-detected, user-curated, or distribution system)
- `distribution_release_id`: Links to corresponding record in `distribution_releases` collection

### distribution_releases Collection (NEW - Separate)

**When you're ready to launch Proton integration**, create this collection:

```json
{
  "_id": ObjectId,
  "label_id": "proton",                    // Your distribution label ID
  "release_title": String,
  "release_type": "single" | "ep" | "album",
  "featured_artist": String,               // Main artist name
  "collaborating_artists": [
    {
      "user_id": String,                   // Reference to users collection
      "name": String,
      "role": "producer" | "vocalist" | "feature" | "collaborator"
    }
  ],
  "distribution_data": {
    "proton_release_id": String,           // Unique ID in your system
    "status": "scheduled" | "released" | "archived",
    "scheduled_date": ISODate,
    "release_date": ISODate,
    "platforms_pending": Array,            // ["spotify", "apple_music", "youtube_music"]
    "platforms_live": Array,               // Platforms already live
    "cover_art_url": String,
    "duration": Number
  },
  "promotion_data": {
    "promoted_users": Array,               // Which users has this been featured to?
    "feature_count": Number,
    "last_featured": ISODate
  },
  "metadata": {
    "genres": Array,
    "credits": Object,
    "description": String
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```python

### Database Indexes

```python
## Add to users collection:
db.users.create_index([("releases.source", 1)])
db.users.create_index([("releases.distribution_release_id", 1)])

## New collection: distribution_releases
db.distribution_releases.create_index([("proton_release_id", 1)])  # Unique lookup
db.distribution_releases.create_index([("label_id", 1)])           # Filter by label
db.distribution_releases.create_index([("collaborating_artists.user_id", 1)])  # Find artist's releases
db.distribution_releases.create_index([("release_date", -1)])      # Chronological queries
db.distribution_releases.create_index([("status", 1)])             # Filter by status
```python

---

## Three Release Pathways Explained

### Pathway 1: Auto-Detected (User Shares Link)

### Flow:

```python
User: "Check out my new track!"
Link: https://open.spotify.com/track/abc123
  ↓
Bot extracts URL & verifies user owns artist profile
  ↓
Query Spotify API for metadata
  ↓
Add to users.releases[]
```python

### Data stored:

```python
{
    "source": "auto_detected",
    "distribution_release_id": None,  # Not from label system
    "title": "Midnight Echo",
    "platform": "spotify",
    "verified": True
}
```python

**Ownership**: User's portfolio (user already has artist profile verified)
**Updates**: Manual only (user can delete/edit)
**Used for**: Portfolio tracking, random promotion

---

### Pathway 2: User-Curated (Discord Interactive View)

### Flow:

```python
User opens /release_manager View
  ↓
User fills form:

  - Title
  - URL
  - Genre
  - Release date
  - Other credits
  ↓
Optional: Verify URL ownership (like auto-detected)
  ↓
Add to users.releases[]
```python

### Data stored:

```python
{
    "source": "user_curated",
    "distribution_release_id": None,  # Manual entry, not linked
    "title": "Neon Dreams",
    "platform": "bandcamp",
    "verified": True  # Depends on verification method
}
```python

**Ownership**: User's portfolio (they manually added it)
**Updates**: User can edit/delete anytime
**Used for**: Portfolio building, curated discography

---

### Pathway 3: Distribution System (Proton Label)

### Flow:

```python
You schedule release in Proton admin panel:

  - Set featured artist
  - Add collaborators (by user_id)
  - Schedule date
  - Upload artwork
  ↓
Create record in distribution_releases collection
  ↓
Platforms process (Spotify pending → live)
  ↓
When released → Sync adds to collaborators' users.releases[]
  ↓
Each artist sees it in their release history
```python

### Example:

### Step 1: You create in Proton (→ distribution_releases)

```json
{
  "proton_release_id": "PRO_2026_001",
  "release_title": "Synthetic Dreams",
  "featured_artist": "Z8phyr",
  "collaborating_artists": [
    {
      "user_id": "246030816692404234",
      "name": "Z8phyr",
      "role": "producer"
    },
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "VocalArtist",
      "role": "vocalist"
    }
  ],
  "release_date": "2026-01-31",
  "status": "scheduled"
}
```python

### Step 2: When release goes live (you update status → "released")

For Z8phyr (user_id: "246030816692404234"):

```json
// Added to their users.releases[]
{
  "source": "distribution",
  "distribution_release_id": ObjectId,  // Reference back to distribution_releases
  "title": "Synthetic Dreams",
  "featured_artist": "Z8phyr",
  "platform": "multi",  // Multiple platforms
  "verified": True
}
```python

For VocalArtist (user_id: "550e8400..."):

```json
// Added to their users.releases[]
{
  "source": "distribution",
  "distribution_release_id": ObjectId,  // Same reference
  "title": "Synthetic Dreams",
  "featured_artist": "Z8phyr",
  "role": "vocalist",
  "verified": True
}
```python

**Result**:

- Single source of truth in `distribution_releases`
- Both artists see it in their history
- No data duplication
- Proton system controls state independently

**Ownership**: Label system (you manage it)
**Updates**: Proton admin panel controls (artists can't delete/edit)
**Used for**: Label portfolio, automated promotion, reach tracking

---

## Query Patterns

### Find User's All Releases

```python
user_doc = Users.get_collection().find_one({"user_id": user_id})
all_releases = user_doc.get("releases", [])
## Returns: auto-detected + user-curated + distribution
```python

### Find User's Releases by Source

```python
## Only user-managed releases
Users.get_collection().find({
    "user_id": user_id,
    "releases.source": {"$in": ["auto_detected", "user_curated"]}
})

## Only distribution/label releases
Users.get_collection().find({
    "user_id": user_id,
    "releases.source": "distribution"
})
```python

### Get Distribution Release & All Collaborators

```python
## Get the release from distribution_releases
dist_release = DistributionReleases.get_collection().find_one({
    "proton_release_id": "PRO_2026_001"
})

## Get all collaborator user profiles
user_ids = [artist["user_id"] for artist in dist_release["collaborating_artists"]]
collaborators = Users.get_collection().find({
    "user_id": {"$in": user_ids}
})

## Now you have everyone's full profiles for promotion/sharing
```python

### Find All Label Releases

```python
## All releases from your label
all_releases = DistributionReleases.get_collection().find({
    "label_id": "proton",
    "status": "released"
})

## This week's releases
from datetime import datetime, timedelta
week_ago = datetime.utcnow() - timedelta(days=7)

recent_releases = DistributionReleases.get_collection().find({
    "label_id": "proton",
    "status": "released",
    "release_date": {"$gte": week_ago}
})
```python

### Find Unverified User Releases

```python
## User might have added releases manually without verification
Users.get_collection().find({
    "releases": {
        "$elemMatch": {
            "source": "user_curated",
            "verified": False
        }
    }
})
```python

### Promotion: Get Artists with Recent Distribution Releases

```python
## Find all users who have distribution releases this week
week_ago = datetime.utcnow() - timedelta(days=7)

Users.get_collection().find({
    "releases": {
        "$elemMatch": {
            "source": "distribution",
            "shared_at": {"$gte": week_ago}
        }
    }
})
```python

---

## Why No Breaking Changes

### What Stays the Same

| Component | Current Behavior | After Distribution | Breaking? |
| ------------------------- | ---------------- | ------------------ | --------- |
| `users.releases[]` exists | ✅ Embedded | Still embedded | ✅ No |
| Query user's releases | ✅ Fast queries | Still fast | ✅ No |
| Add release to user | ✅ Simple write | Still simple | ✅ No |
| Auto-detect releases | ✅ Works | Still works | ✅ No |
| User profile structure | ✅ Works | Unchanged | ✅ No |

### What's New (Additive)

- `source` field on releases (optional, identifies origin)
- `distribution_release_id` field (optional, only for linked releases)
- `distribution_releases` collection (completely separate, independent)
- Linking logic (new code path, doesn't touch existing)

### Migration Path

### Phase 0 (Current)

```python
## Users add releases via Discord View
users.releases[] = [{
    # No "source" field yet (can add retroactively)
    # No "distribution_release_id" field yet
}]
```python

### Phase 1 (When Proton Ready)

```python
## Add "source" field to existing releases (retroactively)
## Values: "auto_detected" or "user_curated"

## Create new distribution_releases collection
## New releases from Proton get "source": "distribution"
## Get "distribution_release_id" pointing back
```python

**No breaking changes** - just additive fields and new collection.

---

## Implementation Roadmap

### Phase 0 (Current - Now)

- ✅ Users can manually add releases via `/release_manager` View
- ✅ Stored in `users.releases[]`
- 📝 **Action**: Add `source: "user_curated"` field to new releases (or retroactively to all)
- **Breaking changes**: None

### Phase 1 (When Proton Ready - 2-4 weeks)

- 🎬 Create `distribution_releases` collection
- 🎬 Set up MongoDB indexes
- 🎬 Build Proton → Abby sync (when you schedule a release)
- 🎬 When Proton marks release as "live", sync adds to collaborators' `users.releases[]`
- 📝 **Action**: Implement sync webhook from Proton
- **Breaking changes**: None (only additions)

### Phase 2 (Future - 1-2 months later)

- 📊 Build label analytics dashboard
- 📊 Automated promo messages when distributions go live
- 📊 Reach tracking per release
- 📊 Cross-promote collaborators
- **Breaking changes**: None

---

## Scaling: Label Grows from 5-10 → 100+ Artists

Your hybrid approach scales beautifully:

### 5-10 artists (current)

- Distribution releases per month: 1-2
- Users' combined release arrays: ~20-50 items
- Query speed: Instant
- Storage: Minimal

### 50-100 artists

- Distribution releases per month: 5-20
- Users' combined release arrays: ~100-500 items per user
- Query speed: Still instant (embedded queries are fastest)
- Storage: Still minimal (embedded is efficient)

### 500+ artists (future)

- Distribution releases per month: 50-200
- Query speed: Still instant (no joins between users and distribution_releases)
- Could add:
  - Caching layer for popular queries
  - Analytics rollup collection
  - But schema stays identical

### Why it scales:

- User releases queries don't need label data (embedded)
- Label analytics queries don't scan user documents (separate collection)
- No joins between collections needed
- Indexes on label_id and collaborating_artists.user_id are efficient

---

## Proton Integration Checklist

```python
## Phase 1 Checklist

## Database Setup

- [ ] Add "source" field to existing releases (migration)
- [ ] Create distribution_releases collection
- [ ] Create indexes on distribution_releases
- [ ] Add index on users.releases[].source
- [ ] Add index on users.releases[].distribution_release_id

## Proton Integration

- [ ] Build Proton auth/API client
- [ ] Create endpoint: /proton/webhook/release-scheduled (creates distribution_release doc)
- [ ] Create endpoint: /proton/webhook/release-live (syncs to artists' releases arrays)
- [ ] Build admin panel to trigger manual sync (if needed)

## Testing

- [ ] Test schedule release → creates distribution_releases doc
- [ ] Test release goes live → creates release entries for collaborators
- [ ] Test collaborator sees release in their profile
- [ ] Test queries work: "get all label releases", "get artist's distribution releases"

## Monitoring

- [ ] Alert if Proton sync fails
- [ ] Monitor database growth of distribution_releases
- [ ] Track promo engagement of distribution releases
```python

---

## Real World Example

### Scenario: You release a collaborative single

### Time: Jan 30, 2026 11:00 AM

You schedule in Proton:

- Title: "Neon Visions"
- Artist: Z8phyr (user_id: `246030816692404234`)
- Features: VocalArtist (user_id: `550e8400-e29b-41d4-a716-446655440000`)
- Release: Feb 1, 2026
- Platforms: Spotify, Apple Music, YouTube Music

**Proton creates**: `distribution_releases` document

```json
{
  "proton_release_id": "PRO_2026_013",
  "release_title": "Neon Visions",
  "featured_artist": "Z8phyr",
  "collaborating_artists": [
    { "user_id": "246030816692404234", "role": "producer" },
    { "user_id": "550e8400-e29b-41d4-a716-446655440000", "role": "vocalist" }
  ],
  "status": "scheduled",
  "release_date": "2026-02-01"
}
```python

### Time: Feb 1, 2026 12:00 AM (Release goes live)

Proton webhook fires: `POST /api/proton/webhook/release-live`

Bot updates:

- Sets `distribution_releases` status → "released"
- For each collaborating_artist, adds to their `users.releases[]`:

### Z8phyr sees new release:

```json
{
  "source": "distribution",
  "distribution_release_id": ObjectId("..."),
  "title": "Neon Visions",
  "featured_artist": "Z8phyr",
  "platforms_live": ["spotify", "apple_music", "youtube_music"]
}
```python

### VocalArtist sees same release:

```json
{
  "source": "distribution",
  "distribution_release_id": ObjectId("..."),  // Same reference
  "title": "Neon Visions",
  "featured_artist": "Z8phyr",
  "role": "vocalist",
  "platforms_live": ["spotify", "apple_music", "youtube_music"]
}
```python

### Time: Feb 1, 2026 12:30 PM (Abby promo cycle)

Bot runs promotion job:

```python
## Get this week's distribution releases
recent_releases = DistributionReleases.find({
    "status": "released",
    "release_date": {"$gte": week_ago}
})

## For each release, get collaborators' discord usernames
for release in recent_releases:
    for artist in release["collaborating_artists"]:
        user_doc = Users.find_one({"user_id": artist["user_id"]})
        discord_username = user_doc["discord"]["username"]

        # Send promo message
        send_promo_message(f"🎵 {release['release_title']} by {discord_username}!")
```python

**Result**:

- Two artists get featured in Abby's promo messages
- Each has release in their portfolio
- Single source of truth (distribution_releases doc)
- No data duplication
- Easy to track reach/engagement

---

## One Last Thing: source Field Matters

The `source` field lets you distinguish handling:

```python
def handle_release_promotion(release):
    if release["source"] == "user_curated":
        # User manually added - trust their taste
        # Can promote immediately or let user opt-in
        if user_opts_for_promos:
            promote_release(release)

    elif release["source"] == "auto_detected":
        # Bot verified via API - safe to promote
        promote_release(release)

    elif release["source"] == "distribution":
        # Label system - automatic
        # Already scheduled in Proton
        promote_release(release)
```python

This gives you control and flexibility.

---

## Summary

✅ **Keeps releases embedded** for users (fast, simple)
✅ **Adds distribution_releases collection** for label (scalable, independent)
✅ **No breaking changes** - all additive
✅ **Hybrid approach** gives you best of both worlds
✅ **Scales** from 5 to 500+ artists without schema changes
✅ **Ready for Proton** whenever you're ready to integrate
