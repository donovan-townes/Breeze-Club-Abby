## Architecture Diagrams & Visual References

### 1. Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│         USER INTERFACE LAYER (Discord)                      │
│                                                              │
│  Slash Commands, Embeds, Buttons, Modals                    │
│  (abby_adapters/discord/cogs/)                              │
│                                                              │
│  @app_commands.command()                                    │
│  async def imagine(...):                                    │
│      # Discord-specific UI only                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           ↓ imports
                    (only direction allowed)
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│              APPLICATION CORE LAYER                         │
│                                                              │
│  Pure business logic, reusable by any adapter              │
│  (abby_core/*)                                              │
│                                                              │
│  ImageGenerator                  StorageManager             │
│  - text_to_image()              - save_image()             │
│  - image_to_image()             - get_quota_status()       │
│  - upscale_image()              - cleanup_old_files()      │
│                                                              │
│  Returns: bytes, Path, Dict      Returns: bool, str, Path  │
│  ✅ No Discord imports           ✅ No Discord imports      │
│                                                              │
│  + Other modules (LLM, RAG, Database, Economy, etc.)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. Storage System Architecture

```
┌─────────────────────────────────────────────────┐
│         StorageManager (Entry Point)            │
│  ────────────────────────────────────────────  │
│  save_image()                                   │
│  get_image_path()                               │
│  delete_image()                                 │
│  get_user_images()                              │
│  get_quota_status()  ←───┐                     │
│  cleanup_old_files() ←──┐│                     │
└─────────────────────────┼┼─────────────────────┘
                          ││
                          ││ delegates to
                          ││
         ┌────────────────┘│
         │                 │
    ┌────▼──────────────────▼────────────────────┐
    │      QuotaManager                          │
    │  ─────────────────────────────────────────  │
    │  get_global_usage()                         │
    │  get_user_usage()                           │
    │  check_global_quota()                       │
    │  check_user_quota()                         │
    │  check_daily_limit()                        │
    │  increment_generation_count()               │
    │  get_quota_status()                         │
    └────────────────────────────────────────────┘
```

---

### 3. Image Generation Pipeline

```
                    Discord Slash Command
                            │
                            ↓
                  ┌─────────────────────┐
                  │ Check Quota Status  │
                  └─────────────────────┘
                            │
                    ┌───────┴────────┐
                    │                │
              (OK)  │                │  (LIMIT EXCEEDED)
                    ↓                ↓
          ┌─────────────────┐   Send error
          │ Call Generator  │   to user
          │ text_to_image() │   (return)
          └─────────────────┘
                    │
                    ↓
          ┌──────────────────────┐
          │ Check API Response   │
          └──────────────────────┘
                    │
            ┌───────┴────────┐
            │                │
        (OK)│                │(ERROR)
            ↓                ↓
   ┌─────────────────┐   Send error
   │ Save to Storage │   to user
   │ save_image()    │   (return)
   └─────────────────┘
            │
            ↓
   ┌──────────────────────┐
   │ Check Storage Result │
   └──────────────────────┘
            │
    ┌───────┴────────┐
    │                │
(OK)│                │(QUOTA EXCEEDED)
    ↓                ↓
Send file      Send error
to user        to user
```

---

### 4. Storage Directory Tree

```
shared/
│
├── images/                          (all saved images)
│   ├── users/                       (organized by user)
│   │   ├── 123456789/              (user ID as directory name)
│   │   │   ├── generated.png        (user's images)
│   │   │   ├── transformed.png
│   │   │   ├── upscaled.png
│   │   │   └── ...
│   │   ├── 987654321/              (another user)
│   │   │   ├── generated.png
│   │   │   └── ...
│   │   └── [more users]
│   │
│   └── [legacy/other images]
│
├── temp/                            (auto-cleaned after 7 days)
│   ├── temp_request_001.png
│   ├── temp_request_002.png
│   ├── temp_processing_001.tmp
│   └── ...
│
└── logs/                            (existing)
    └── events.jsonl
```

---

### 5. Quota System Model

```
USER REQUEST TO GENERATE IMAGE
    │
    ├─ Check 1: Daily Limit
    │   ├─ Counter per user
    │   ├─ Resets at 00:00 UTC
    │   ├─ Default: 5 gens/day
    │   └─ REJECT if: count >= limit
    │
    ├─ Check 2: User Storage Quota
    │   ├─ Sum of all user's files
    │   ├─ Default limit: 500MB
    │   ├─ Estimated gen size: 1.5MB
    │   └─ REJECT if: used + estimated > limit
    │
    ├─ Check 3: Global Storage Quota
    │   ├─ Sum of all files globally
    │   ├─ Default limit: 5000MB (5GB)
    │   └─ REJECT if: used + estimated > limit
    │
    └─ PROCEED TO IMAGE GENERATION
        │
        ├─ Call Stability AI API
        ├─ Get actual image bytes
        │
        ├─ Re-check quotas with actual size
        │
        └─ SAVE TO DISK
            ├─ Increment daily counter
            ├─ Update storage tracking
            └─ Return path to caller
```

---

### 6. Code Separation Pattern

```
WRONG ❌
┌─────────────────────────────────────────┐
│ abby_core/generation.py                 │
│                                         │
│ import discord  ←─ WRONG!               │
│ import aiohttp                          │
│                                         │
│ async def text_to_image(...):           │
│     ...                                 │
│     embed = discord.Embed(...)  ←─ NOPE!│
│                                         │
│ Can't reuse: tightly coupled to Discord │
└─────────────────────────────────────────┘


RIGHT ✅
┌─────────────────────────────────────────┐
│ abby_core/generation/image_generator.py │
│                                         │
│ # NO discord imports                    │
│ import aiohttp                          │
│                                         │
│ async def text_to_image(...) -> ...:    │
│     # Return bytes, not Discord objects │
│     return success, image_bytes, msg    │
│                                         │
│ Can reuse: Web API, CLI, Desktop app   │
└─────────────────────────────────────────┘
        ↓ used by ↓
┌─────────────────────────────────────────┐
│ abby_adapters/discord/cogs/...          │
│                                         │
│ from abby_core.generation import ...    │
│ import discord  ✅ Only here             │
│                                         │
│ @app_commands.command()                 │
│ async def imagine(...):                 │
│     bytes = await generator.img2text()  │
│     file = discord.File(bytes)  ← UI   │
│     await interaction.send(file=file)   │
└─────────────────────────────────────────┘
```

---

### 7. Configuration Hierarchy

```
Project Root
│
├── .env                         (Environment Variables)
│   ├── STORAGE_ROOT=shared
│   ├── MAX_GLOBAL_STORAGE_MB=5000
│   ├── MAX_USER_STORAGE_MB=500
│   ├── MAX_USER_DAILY_GENS=5
│   ├── STORAGE_CLEANUP_DAYS=7
│   ├── STABILITY_API_KEY=sk_xxx
│   └── [other vars]
│
└── abby_adapters/discord/config.py    (Config Objects)
    │
    ├── @dataclass StorageConfig
    │   └── Reads from env via os.getenv()
    │
    ├── @dataclass APIKeys
    │   └── api.stability_key
    │       api.stability_api_host
    │
    └── @dataclass BotConfig
        └── storage: StorageConfig
            api: APIKeys
            [other configs]

Usage in Code:
from abby_adapters.discord.config import config
limit = config.storage.max_user_storage_mb  # 500
```

---

### 8. Module Dependency Graph

```
                        abby_adapters/discord
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
            cogs/*          config.py       main.py
                 │              │              │
                 └──────────────┬──────────────┘
                                │
                    imports from abby_core
                                │
         ┌──────────┬─────────┬─┴─┬──────────┬──────────┐
         │          │         │   │          │          │
     storage/   generation/ llm/ rag/  database/  economy/
         │          │         │   │          │          │
         └──────────┴─────────┴───┴──────────┴──────────┘
                                │
                        ⚠️ MUST NEVER
                    import from adapter
```

---

### 9. Quota Status at a Glance

```
┌─────────────────────────────────────────────────────┐
│  QUOTA STATUS                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  💾 SERVER STORAGE                                  │
│  ████████████░░░░░░░░░░ 24.7%                      │
│  1234.56 MB / 5000 MB                              │
│  Status: ✅ OK                                      │
│                                                     │
│  👤 YOUR STORAGE                                    │
│  ███░░░░░░░░░░░░░░░░░░░ 9.0%                       │
│  45.23 MB / 500 MB                                  │
│  Status: ✅ OK                                      │
│                                                     │
│  📅 TODAY'S GENERATIONS                             │
│  ████████░░░░░░░░░ 40% (2 / 5 used)                │
│  3 remaining today                                  │
│  Status: ✅ OK                                      │
│                                                     │
└─────────────────────────────────────────────────────┘

If any show ⚠️ WARNING: Consider cleanup or waiting
If any show 🔴 CRITICAL: Action required immediately
```

---

### 10. Quota Enforcement Decision Tree

```
         User requests image generation
                    │
                    ↓
         ┌──────────────────────┐
         │ Get quota status     │
         │ for this user        │
         └──────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    PASS │                     │ FAIL
         │                     │
         ↓                     ↓
    Generate            Return error:
    image            "Daily/Storage
         │            quota exceeded"
         │                     │
         ↓                     ↓
    Get actual            User sees
    image size         message & can't
         │               generate
         ├─ Estimated 1.5 MB
         └─ Actual: varies
                    │
         ┌──────────┴──────────┐
         │                     │
    Size │                     │ Size
    OK?  │                     │ Too big?
         │                     │
    YES  ↓                     ↓ NO
         │                Return error
    Save to disk       "File too large"
         │
         ↓
    Update quota
    tracking
         │
         ↓
    Increment
    daily counter
         │
         ↓
    Return to user
    ✅ Success!
```

---

### 11. Before & After Comparison

```
BEFORE: 3 Duplicate Implementations
┌───────────────────┬───────────────────┬─────────────────┐
│ cogs/creative/    │ cogs/Fun/         │ commands/Image/ │
│ images.py (227)   │ image_gen.py (303)│ generate.py (295)
├───────────────────┼───────────────────┼─────────────────┤
│ /home/Discord/    │ /home/Discord/    │ os.getenv()     │
│ Images/[file]     │ Images/[file]     │ "Images"        │
├───────────────────┼───────────────────┼─────────────────┤
│ Direct API calls  │ Direct API calls  │ Direct API      │
│ [code dup]        │ [code dup]        │ [code dup]      │
├───────────────────┼───────────────────┼─────────────────┤
│ No quotas         │ No quotas         │ No quotas       │
│ No cleanup        │ No cleanup        │ No cleanup      │
└───────────────────┴───────────────────┴─────────────────┘
         ❌ Bad:  Paths wrong on TSERVER (Windows)
         ❌ Bad:  Can't reuse for Web/API/CLI
         ❌ Bad:  No quota enforcement


AFTER: Single Source of Truth
┌──────────────────────────────────────────────────────────┐
│            abby_core/generation/                         │
│            image_generator.py                            │
├──────────────────────────────────────────────────────────┤
│ text_to_image()                                          │
│ image_to_image()                                         │
│ upscale_image()                                          │
│ [Single implementation, reusable]                        │
└──────────────────────────────────────────────────────────┘
         ↓ AND ↓
┌──────────────────────────────────────────────────────────┐
│            abby_core/storage/                            │
│            storage_manager.py                            │
├──────────────────────────────────────────────────────────┤
│ save_image() [with quota checks]                        │
│ get_quota_status()                                      │
│ cleanup_old_files()                                     │
│ [Single implementation, reusable]                        │
└──────────────────────────────────────────────────────────┘
         ↓ USED BY ↓
┌──────────────────────────────────────────────────────────┐
│       abby_adapters/discord/cogs/creative/               │
│       images.py [ONLY Discord slash command UI]         │
└──────────────────────────────────────────────────────────┘

✅ Good:  Single source of truth
✅ Good:  Config-driven paths (works Windows/Linux/Mac)
✅ Good:  Can reuse for Web/API/CLI
✅ Good:  Quota enforcement
✅ Good:  Auto-cleanup policy
```

---

### 12. Success Metrics

```
┌─────────────────────────────────────────────────────┐
│  BEFORE → AFTER METRICS                             │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Code Duplication:    3 copies → 1 source of truth │
│ Hard-coded Paths:    3 versions → Config-driven   │
│ Quota System:        None → Full implementation   │
│ Storage Limits:      Unlimited → 5GB global limit │
│ Per-user Limits:     Unlimited → 500MB per user   │
│ Rate Limiting:       None → 5 gens/day            │
│ Cleanup Policy:      None → Auto-delete 7+ days  │
│ Config-driven:       Partial → 100%               │
│ Reusable:            No → Yes                     │
│ Cross-platform:      No → Yes (Linux/Windows/Mac) │
│                                                     │
│ Total Lines:         825 scattered → 630 organized │
│ New Modules:         0 → 2 (storage, generation)  │
│ New Classes:         0 → 3 (Storage, Quota, Image)│
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Print-Friendly Summary

### Core Principles

1. **Core has NO Discord imports** - reusable by any adapter
2. **Adapter imports Core** - not the other way around
3. **Config is external** - everything in .env or config.py
4. **One implementation** - no duplication of logic
5. **Quotas enforced** - before API calls and after saves

### Quick Check

```
Is it Discord-specific?
├─ YES → abby_adapters/discord/
└─ NO  → abby_core/

Can another adapter reuse it?
├─ YES → abby_core/
└─ NO  → abby_adapters/discord/

Does it return Discord types?
├─ YES → abby_adapters/discord/
└─ NO  → abby_core/
```

### Directory Structure

```
✅ Right place:
  - Slash commands → abby_adapters/discord/cogs/
  - Image API logic → abby_core/generation/
  - Storage ops → abby_core/storage/
  - Config → abby_adapters/discord/config.py

❌ Wrong place:
  - Discord imports in core
  - Hard-coded values in code
  - Duplicated logic
  - Config in multiple places
```
