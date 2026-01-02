## ✅ Implementation Checklist - Phase 2

### Current Status

✅ **Phase 1 Complete**: Infrastructure built (storage, generation, config)
⏳ **Phase 2 Ready**: Update image code to use new system

---

## Pre-Implementation Checklist

- [ ] Read [ARCHITECTURE.md](ARCHITECTURE.md) completely
- [ ] Read [STORAGE_SYSTEM.md](STORAGE_SYSTEM.md) completely
- [ ] Have [STORAGE_API_REFERENCE.md](STORAGE_API_REFERENCE.md) open for reference
- [ ] Understand quota system (daily, per-user, global)
- [ ] Know where StorageManager and ImageGenerator are located
- [ ] Understand config structure and env vars

---

## Environment Setup

### .env Variables to Add

```env
# Add these to .env file
STORAGE_ROOT=shared
MAX_GLOBAL_STORAGE_MB=5000
MAX_USER_STORAGE_MB=500
MAX_USER_DAILY_GENS=5
STORAGE_CLEANUP_DAYS=7
IMAGE_GEN_SIZE_MB=1.5
```

- [ ] Add STORAGE_ROOT=shared
- [ ] Add MAX_GLOBAL_STORAGE_MB=5000
- [ ] Add MAX_USER_STORAGE_MB=500
- [ ] Add MAX_USER_DAILY_GENS=5
- [ ] Add STORAGE_CLEANUP_DAYS=7
- [ ] Add IMAGE_GEN_SIZE_MB=1.5
- [ ] Verify .env is loaded in main.py
- [ ] Test that config.storage is accessible

### Directory Setup

- [ ] Verify `shared/` directory exists (or create it)
- [ ] Verify `shared/images/` is writable
- [ ] Verify `shared/temp/` is writable
- [ ] Verify `shared/logs/` exists

---

## Phase 2: Update Image Generation Code

### Task 1: Update cogs/creative/images.py

**File**: `abby_adapters/discord/cogs/creative/images.py`

**Steps**:

- [ ] Add imports:

  ```python
  from abby_core.generation import ImageGenerator
  from abby_core.storage import StorageManager
  from abby_adapters.discord.config import config
  ```

- [ ] In `__init__`, initialize services:

  ```python
  self.storage = bot.storage  # From bot instance
  self.generator = bot.generator  # From bot instance
  ```

- [ ] For each command (imagine, imgimg, upscale):

  - [ ] Add quota check at the start
  - [ ] Replace direct API calls with `self.generator.*`
  - [ ] Replace hard-coded paths with `self.storage.save_image()`
  - [ ] Add error handling for quota exceeded
  - [ ] Display quota status in response

- [ ] Update error handlers to reference quota errors

**Test After**:

- [ ] /imagine command works
- [ ] Images save to shared/images/users/{user_id}/
- [ ] Quota status shown in response
- [ ] Error messages are clear

---

### Task 2: Update cogs/Fun/image_gen.py

**File**: `abby_adapters/discord/cogs/Fun/image_gen.py`

**Repeat same steps as Task 1**:

- [ ] Add imports for ImageGenerator, StorageManager, config
- [ ] Initialize services in **init**
- [ ] For each method (generate_image, imgimg, upscale):
  - [ ] Add quota check
  - [ ] Use self.generator.\*
  - [ ] Use self.storage.save_image()
  - [ ] Show quota status
  - [ ] Handle quota errors

**Test After**:

- [ ] All methods work
- [ ] Images save to correct location
- [ ] Quotas enforced

---

### Task 3: Update commands/Image/image_generate.py

**File**: `abby_adapters/discord/commands/Image/image_generate.py`

**Option A: Migrate to new cogs structure** (recommended)

- [ ] Move functionality to cogs/creative/ or similar
- [ ] Remove old commands/Image/image_generate.py
- [ ] Update main.py loader

**Option B: Update in place** (if keeping legacy structure)

- [ ] Add imports
- [ ] Initialize services
- [ ] Replace API calls and path handling
- [ ] Add quota checks

**Test After**:

- [ ] Commands work (or are migrated)
- [ ] No duplication with cogs/creative/images.py

---

### Task 4: Update main.py Bot Initialization

**File**: `abby_adapters/discord/main.py`

**Changes**:

- [ ] Add imports for StorageManager and ImageGenerator:

  ```python
  from abby_core.storage import StorageManager
  from abby_core.generation import ImageGenerator
  ```

- [ ] In `__init__`, add:

  ```python
  # Initialize shared services
  self.storage = StorageManager(
      storage_root=config.storage.storage_root,
      max_global_storage_mb=config.storage.max_global_storage_mb,
      max_user_storage_mb=config.storage.max_user_storage_mb,
      max_user_daily_gens=config.storage.max_user_daily_gens,
  )

  self.generator = ImageGenerator(
      api_key=config.api.stability_key,
      api_host=config.api.stability_api_host,
  )
  ```

**Test**:

- [ ] Bot starts without errors
- [ ] Storage service initialized
- [ ] Generator service initialized
- [ ] Services accessible from cogs

---

## Testing Checklist

### Unit Tests (Local)

**Test Storage System**:

- [ ] save_image() saves to correct path
- [ ] Quota tracking works correctly
- [ ] Daily counter resets properly
- [ ] cleanup_old_files() works
- [ ] get_quota_status() returns correct values

**Test Image Generation**:

- [ ] text_to_image() returns bytes
- [ ] image_to_image() transforms image
- [ ] upscale_image() upscales image
- [ ] Error handling works
- [ ] Proper messages returned

**Test Configuration**:

- [ ] Config reads from .env
- [ ] All limits are accessible
- [ ] Paths are correctly formatted
- [ ] Fallback values work

### Integration Tests (Discord)

**Test Commands**:

- [ ] /imagine generates image
- [ ] Image saves to shared/images/
- [ ] Quota status shows in response
- [ ] Daily limit enforced
- [ ] User storage limit enforced
- [ ] Global limit enforced

**Test Error Cases**:

- [ ] Daily limit exceeded → clear error message
- [ ] Storage quota full → clear error message
- [ ] Invalid prompt → API error handled
- [ ] API timeout → user gets error

**Test Quotas**:

- [ ] Generate 5 images → 6th rejected
- [ ] User 1 and User 2 quotas independent
- [ ] Global limit enforcement
- [ ] Quota resets at midnight UTC

### Manual Testing

**Test locally**:

- [ ] Delete .env STABILITY_API_KEY, bot starts anyway (graceful fail)
- [ ] Invalid path in STORAGE_ROOT, bot starts but errors on save
- [ ] Modify quota limits in .env, limits respected
- [ ] Run storage.cleanup_old_files(), old files removed
- [ ] User can see quota status in Discord embed
- [ ] Images visible at shared/images/users/{id}/

**Test on TSERVER**:

- [ ] Bot connects
- [ ] /imagine command works
- [ ] Images save to C:\opt\tdos\apps\abby\shared\
- [ ] Windows paths work correctly
- [ ] Storage quota enforced

---

## Code Review Checklist

### Before Committing, Verify:

**Architecture**:

- [ ] No Discord imports in abby_core/
- [ ] Adapter only imports from core
- [ ] No circular dependencies
- [ ] Proper error handling

**Configuration**:

- [ ] All hard-coded paths removed
- [ ] All limits from config.storage
- [ ] No os.getenv() calls scattered
- [ ] Env vars documented in .env.example

**Code Quality**:

- [ ] Proper error messages
- [ ] Quota checks before API calls
- [ ] Quota checks after saves
- [ ] Cleanup implemented
- [ ] No commented-out code
- [ ] Proper logging (setup_logging)

**Tests**:

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual tests pass
- [ ] Error cases handled
- [ ] Edge cases covered

---

## Deployment Checklist

### Before Deploying to TSERVER

**Code**:

- [ ] All changes committed
- [ ] Code reviewed
- [ ] Tests passing
- [ ] No warnings/errors
- [ ] Documentation updated

**Configuration**:

- [ ] .env updated with new vars
- [ ] STABILITY_API_KEY present
- [ ] STORAGE_ROOT set to shared
- [ ] All quota limits reviewed

**Infrastructure**:

- [ ] shared/ directory exists
- [ ] shared/images/ writable
- [ ] shared/temp/ writable
- [ ] Enough disk space (5GB available)
- [ ] Permissions correct

**Testing**:

- [ ] Test /imagine command
- [ ] Verify images save
- [ ] Check quota enforcement
- [ ] Monitor logs for errors
- [ ] Verify cleanup runs

---

## Post-Deployment Checklist

### After Deploying to TSERVER

**Monitoring**:

- [ ] No errors in logs
- [ ] Images generating successfully
- [ ] Storage quota working
- [ ] Cleanup running (if scheduled)
- [ ] Users can see quota status

**Validation**:

- [ ] 5+ users generated images
- [ ] Each user's images in separate folder
- [ ] Quota enforcement working
- [ ] Daily limit resetting
- [ ] No duplicate images

**Cleanup**:

- [ ] Delete old test images
- [ ] Run manual cleanup if needed
- [ ] Verify cleanup schedule

---

## Rollback Plan (If Issues Found)

**Quick Rollback** (if critical issues):

```bash
1. Revert main.py to previous version
2. Comment out storage/generation initialization
3. Keep old image generation code (if not deleted)
4. Restart bot
5. Manual investigation
```

**Testing Issues**:

- [ ] Check .env values
- [ ] Check shared/ permissions
- [ ] Check API key validity
- [ ] Check logs for specific errors

**Deployment Issues**:

- [ ] Check path assumptions (Windows vs Linux)
- [ ] Check drive space
- [ ] Check permissions
- [ ] Check env var loading

---

## Documentation Updates

After implementation, update:

- [ ] README.md - Add storage system section
- [ ] DEPLOYMENT_NSSM.md - Note env vars needed
- [ ] Add example .env.example with storage vars
- [ ] Update any architecture diagrams if structure changed

---

## Success Criteria

Implementation is complete when:

- [ ] ✅ All image generation uses new system
- [ ] ✅ No hard-coded paths in code
- [ ] ✅ Quota system enforced
- [ ] ✅ Images save to shared/images/users/{id}/
- [ ] ✅ Users can see quota status
- [ ] ✅ Tests pass locally and on TSERVER
- [ ] ✅ No duplication of API logic
- [ ] ✅ Clean error messages
- [ ] ✅ Documentation updated
- [ ] ✅ TSERVER deployment successful

---

## Timeline Estimate

| Task                           | Time          | Notes                       |
| ------------------------------ | ------------- | --------------------------- |
| Setup env/dirs                 | 30 min        | Quick                       |
| Update cogs/creative/images.py | 1-2 hrs       | Most complex                |
| Update cogs/Fun/image_gen.py   | 30 min        | Similar to above            |
| Update commands/Image/...      | 30 min        | Or migrate to new structure |
| Update main.py                 | 30 min        | Just init code              |
| Local testing                  | 1-2 hrs       | Test all quotas & errors    |
| Deployment                     | 30 min        | Set env, start service      |
| Post-deployment validation     | 30 min        | Verify working              |
| **Total**                      | **5-7 hours** | **One developer**           |

---

## Questions During Implementation?

Reference these sections:

| Question                        | Document                 | Section         |
| ------------------------------- | ------------------------ | --------------- |
| "How do I use StorageManager?"  | STORAGE_API_REFERENCE.md | API Docs        |
| "How do I check quotas?"        | STORAGE_API_REFERENCE.md | Common Patterns |
| "Where should this code go?"    | ARCHITECTURE.md          | Decision Matrix |
| "How do I handle errors?"       | STORAGE_API_REFERENCE.md | Error Messages  |
| "What's the migration pattern?" | STORAGE_SYSTEM.md        | Migration Steps |
| "What config do I need?"        | STORAGE_API_REFERENCE.md | Configuration   |

---

## Sign-Off Template

When complete, fill this out:

```
PHASE 2 IMPLEMENTATION COMPLETE

Developer: ___________________
Date: ____________________
Commit Hash: ___________________

Tests Passed:
- [ ] Local unit tests
- [ ] Local integration tests
- [ ] TSERVER smoke test

Code Review:
- [ ] Code reviewed by: ___________________
- [ ] No blocking issues

Deployment Status:
- [ ] Code deployed to TSERVER
- [ ] Env vars configured
- [ ] Service restarted
- [ ] Monitoring active

Known Issues:
(List any known issues or follow-ups)

Follow-ups:
(Any future improvements needed)
```

---

## Next Phases (Future)

After Phase 2 is complete:

**Phase 3: Optimization**

- Database-backed quota tracking
- Quota tiers by user role
- Image compression
- Archive old images
- Usage analytics

**Phase 4: Enhancement**

- Quota marketplace (buy quota)
- User analytics dashboard
- Admin quota override
- Quota-based features
- Performance improvements

---

## Good Luck! 🚀

You have everything you need:

- ✅ Infrastructure built
- ✅ Clear migration path
- ✅ Comprehensive documentation
- ✅ Testing checklist
- ✅ Deployment plan

Start with the first task and work through systematically. Reference the docs as needed. Good luck!
