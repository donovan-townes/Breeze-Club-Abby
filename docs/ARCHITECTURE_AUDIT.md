## Architectural Audit Report

### Executive Summary

The architecture is **well-separated overall**, with clear boundaries between `abby_core` (general application logic) and `abby_adapters/discord` (Discord-specific implementation). However, there are critical gaps in the storage system that need addressing, and a few edge cases need clarification.

---

## Current State Analysis

### 1. ✅ GOOD SEPARATION - Core Modules

#### abby_core/database/

- **Purpose**: MongoDB connection and schema management
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Files**: mongodb.py, schemas.py, indexes.py
- **Assessment**: Generic adapter-agnostic design. Could be used by any adapter.

#### abby_core/llm/

- **Purpose**: LLM integration (Ollama, OpenAI, etc.)
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Files**: client.py, conversation.py, persona.py
- **Assessment**: Provider-agnostic implementation. Could serve web, CLI, or any adapter.

#### abby_core/rag/

- **Purpose**: Retrieval Augmented Generation (Qdrant, Chroma)
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Files**: qdrant_client.py, chroma_client.py, embeddings.py, handler.py
- **Assessment**: Generic vector DB integration. Could be used by any adapter.

#### abby_core/economy/

- **Purpose**: XP, leveling, and bank system
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Files**: xp.py, bank.py
- **Assessment**: Generic economy logic. Discord cogs properly use this layer (good pattern).

#### abby_core/security/

- **Purpose**: Encryption, salt management, security utilities
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Assessment**: Generic security utilities suitable for any adapter.

#### abby_core/observability/

- **Purpose**: Logging and telemetry
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Files**: logging.py, telemetry.py
- **Assessment**: Generic logging. TDOS integration is appropriate for core telemetry.

#### abby_core/personality/

- **Purpose**: Bot personality, response patterns, personas (Bunny, Kiki)
- **Status**: ✅ **PROPERLY ISOLATED** - No Discord-specific code
- **Files**: config.py (loads JSON files), JSON persona configs
- **Assessment**: Configuration-driven, generic system. Works for any adapter.

#### abby_core/moderation/

- **Status**: ⚠️ **EMPTY** - No implementation yet
- **Recommendation**: When implemented, keep generic (rules, policies). Let Discord adapter define UI/enforcement.

---

### 2. ⚠️ CRITICAL GAP - No Storage Module

#### abby_core/storage/ (MISSING)

- **Problem**: Image generation code is in `abby_adapters/discord/cogs/creative/images.py`
- **Impact**:
  - No centralized file management
  - No per-user storage quotas
  - No global capacity limits
  - No cleanup policy
  - Hard-coded file paths (`/home/Discord/Images/generate_image.png`)
  - Path inconsistencies between old and new code
  - Config error: Paths don't exist on deployment target

#### Current Image Storage Issues

1. **Hard-coded Paths** (Multiple Locations):

   - `abby_adapters/discord/cogs/creative/images.py`: `/home/Discord/Images/generate_image.png`
   - `abby_adapters/discord/cogs/Fun/image_gen.py`: `/home/Discord/Images/generate_image.png`, `/home/Discord/Images/upscaled_image.png`, `/home/Discord/Images/edited_image.png`
   - `abby_adapters/discord/commands/Image/image_generate.py`: `Path(os.getenv("IMAGES_DIR", "Images"))` (better!)

2. **No Quota System**:

   - Users can generate unlimited images
   - No per-user daily/monthly caps
   - No global server storage limits
   - Risk of HD bloat

3. **No Cleanup Policy**:

   - No image retention/deletion
   - No temp image cleanup
   - Files accumulate indefinitely

4. **Architecture Mismatch**:
   - Image generation is a **general capability** (could be used by web UI, API, CLI)
   - Currently trapped in `abby_adapters/discord/cogs/`
   - Should belong in `abby_core/` with Discord adapter just handling commands

---

### 3. ✅ GOOD - Discord Adapter Structure

#### abby_adapters/discord/config.py

- **Status**: ✅ **PROPERLY LOCATED** - Discord-specific configuration
- **Contains**: Channels, roles, tokens, timing, Discord-specific paths
- **Assessment**: Well-designed centralized config for Discord layer.
- **Gap**: Missing `StorageConfig` for image/file storage quotas and paths.

#### abby_adapters/discord/cogs/

- **Status**: ✅ **PROPERLY LOCATED** - Discord command implementations
- **Pattern**: Properly separates command UI (slash commands, embeds) from business logic
- **Good Examples**:
  - Economy cogs import from `abby_core.economy` ✅
  - Personality cogs import from `abby_core.personality` ✅

#### abby_adapters/discord/core/loader.py

- **Status**: ✅ **PROPERLY LOCATED** - Discord infrastructure
- **Purpose**: Dynamic cog/command loading system

---

## Issues Found & Recommendations

### CRITICAL Issues (Must Fix)

#### 1. Image Storage System (Config Error Root Cause)

**Issue**: Hard-coded paths don't exist on TSERVER

- `cogs/creative/images.py` uses `/home/Discord/Images/` (Linux path)
- TSERVER is Windows: `C:\opt\tdos\apps\abby\`
- Path should be relative or use config: `shared/images/`

**Recommendation**:

1. ✅ Create `abby_core/storage/` module with centralized management
2. ✅ Add `StorageConfig` to Discord config with proper paths
3. ✅ Move image storage logic to core (it's a general capability)
4. ✅ Implement per-user and global quotas
5. ✅ Use `shared/images/` directory on server

#### 2. Image Generation Code Organization

**Issue**: Image generation is generic capability but trapped in Discord adapter

- Could be used by web UI, API, or other adapters
- Currently mixed with Discord-specific UI (slash commands, interactions)

**Recommendation**:

1. Create `abby_core/generation/` module for image generation logic
2. Move Stability API integration to core
3. Keep Discord-specific UI in `cogs/creative/images.py`
4. Pattern: `core` does generation, `discord` adapter handles slash commands

#### 3. Config Path Inconsistencies

**Issue**: Multiple ways to reference image paths:

- Hard-coded: `/home/Discord/Images/generate_image.png`
- Env-based: `os.getenv("IMAGES_DIR", "Images")`
- Missing from config: Not in `BotConfig`

**Recommendation**: Centralize in `StorageConfig`:

```python
@dataclass
class StorageConfig:
    images_dir: str = "shared/images"  # Global image storage
    temp_dir: str = "shared/temp"      # Temp files
    max_total_storage_mb: int = 5000   # Server limit
    max_user_storage_mb: int = 500     # Per-user limit
    max_user_daily_gens: int = 5       # Rate limit
    cleanup_days: int = 7              # Delete images older than 7 days
```

---

## Proper Architecture (What It Should Be)

### Layer Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│                  abby_adapters/discord                       │
│  Discord-specific: Slash commands, embeds, interactions    │
│  ├─ cogs/creative/images.py (slash command UI)            │
│  ├─ cogs/economy/ (Discord-specific economy UI)           │
│  ├─ config.py (Discord channels, tokens, timing)          │
│  └─ core/loader.py (Discord infrastructure)               │
└─────────────────────────────────────────────────────────────┘
                              ↓ imports
┌─────────────────────────────────────────────────────────────┐
│                     abby_core                                │
│  General application logic (could be used by any adapter)  │
│                                                              │
│  ✅ Existing & Properly Separated:                         │
│  ├─ database/ (MongoDB, schemas)                          │
│  ├─ llm/ (LLM clients: OpenAI, Ollama)                    │
│  ├─ rag/ (Vector DB: Qdrant, Chroma)                      │
│  ├─ economy/ (XP, bank, leveling)                         │
│  ├─ personality/ (Bot personality, personas)              │
│  ├─ security/ (Encryption, auth)                          │
│  └─ observability/ (Logging, telemetry)                   │
│                                                              │
│  ⚠️ Missing (Needs Implementation):                        │
│  ├─ storage/ (File management, quotas, cleanup)           │
│  └─ generation/ (Image generation, content creation)      │
└─────────────────────────────────────────────────────────────┘
```

### Code Should Move

#### FROM discord TO core:

1. **Image generation logic** (core/generation/)

   - Stability API integration
   - Image manipulation logic
   - Style preset management
   - Model parameters

2. **File storage management** (core/storage/)
   - File operations
   - Quota tracking
   - Cleanup policies
   - Directory management

#### STAYS IN discord:

1. **Slash command handlers** (cogs/creative/images.py)
   - Discord interaction handling
   - Embed formatting
   - Button/modal UI
   - User messaging

---

## Verification Checklist

### ✅ What's Correct

- [x] Core modules have no Discord-specific code
- [x] Database layer is generic
- [x] LLM layer is provider-agnostic
- [x] RAG layer is generic
- [x] Economy layer is generic
- [x] Personality layer is configuration-driven
- [x] Security layer is generic
- [x] Discord config in correct location
- [x] Cogs properly structured

### ⚠️ What Needs Fixing

- [ ] Add `abby_core/storage/` module
- [ ] Add `abby_core/generation/` module (or merge into existing)
- [ ] Add `StorageConfig` to Discord config
- [ ] Fix hard-coded image paths
- [ ] Implement per-user quotas
- [ ] Implement cleanup policy
- [ ] Update all image generation imports
- [ ] Fix TSERVER path issues

---

## Migration Path

### Phase 1: Storage System (Next)

1. Create `abby_core/storage/storage_manager.py` with:

   - `StorageManager` class
   - Per-user quota tracking
   - Cleanup policy
   - Path management

2. Add `StorageConfig` to Discord config

3. Update all image code to use `StorageManager`

### Phase 2: Image Generation (After Phase 1)

1. Create `abby_core/generation/image_generator.py`
2. Move API integration logic
3. Update Discord cogs to use new system

### Phase 3: Documentation

1. Create `ARCHITECTURE.md` with diagrams
2. Create storage system guide
3. Update deployment docs

---

## Summary

**Overall Assessment**: Architecture is **fundamentally sound** with proper separation of concerns.

**Critical Gap**: No centralized storage system leads to:

- Config errors (hard-coded paths)
- No quota enforcement (bloat risk)
- Code duplication (multiple image gen copies)
- Deployment friction (path assumptions)

**Recommendation**: Implement Phase 1 (Storage System) immediately to fix config errors and enable proper quota management.
