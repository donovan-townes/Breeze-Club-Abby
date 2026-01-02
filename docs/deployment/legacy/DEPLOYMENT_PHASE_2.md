# Phase 2 Deployment Quick Guide

## Prerequisites ✅

- [x] Phase 1 Complete (Storage & Generation services built)
- [x] All code changes implemented
- [x] Python syntax validated
- [x] Services can be imported

## Pre-Deployment Checklist

### 1. Verify Code Changes

```bash
# Run the verification script
python verify_phase2.py
```

Expected output:

```
Imports................................. ✅ PASS
Configuration........................... ✅ PASS
StorageManager Init..................... ✅ PASS
ImageGenerator Init..................... ✅ PASS
Cog Code Modifications.................. ✅ PASS
```

### 2. Configure Environment Variables

Add to `.env` file on TSERVER:

```ini
# Storage Configuration
STORAGE_ROOT=C:\Abby_Storage          # Windows path
MAX_GLOBAL_STORAGE_MB=5000            # 5GB total
MAX_USER_STORAGE_MB=500               # 500MB per user
MAX_USER_DAILY_GENS=5                 # 5 generations/day per user
CLEANUP_DAYS=7                        # Auto-clean old images
IMAGE_GENERATION_SIZE_MB=20           # Max 20MB per image

# API Keys
STABILITY_API_KEY=sk_...              # Your Stability AI key
ABBY_TOKEN=...                        # Discord bot token

# Other existing vars...
```

### 3. Create Storage Directory

```bash
# On TSERVER
mkdir C:\Abby_Storage
mkdir C:\Abby_Storage\users
mkdir C:\Abby_Storage\images
mkdir C:\Abby_Storage\temp
```

### 4. Verify Database Access

StorageManager will auto-create:

- `C:\Abby_Storage\image_stats.db` - Quota tracking

This SQLite database is created automatically on first run.

## Deployment Steps

### Step 1: Stop Current Bot (if running)

```bash
# On TSERVER
cd C:\Abby_Discord_Latest
# Use NSSM or manual stop
nssm stop abby-bot  # If using NSSM service
# OR manually kill the process
```

### Step 2: Deploy Code

```bash
# Copy updated files to TSERVER:
# - main.py
# - cogs/creative/images.py
# - All Phase 1 files (already deployed)
```

### Step 3: Start Bot

```bash
cd C:\Abby_Discord_Latest
python launch.py
```

### Step 4: Watch Logs for Initialization

```
[🐰] StorageManager initialized successfully
[🐰] ImageGenerator initialized successfully
[🐰] Abby is online as Abby#9999
```

If you see these lines, Phase 2 is working! ✅

## Testing Phase 2 Features

### Test 1: Basic Image Generation

```
/imagine prompt: "a cat wearing sunglasses" style: enhance
```

Expected:

- ✅ Image generates within ~30 seconds
- ✅ Image saves to `C:\Abby_Storage\users\{user_id}\text_to_image\`
- ✅ Response shows quota: `Daily: 1/5 | Storage: X.XMB/500MB`
- ✅ User sees embed with image attached

### Test 2: Quota Enforcement

```
/imagine ... (repeat 5 times)
/imagine ... (6th attempt)
```

Expected:

- ✅ First 5 commands succeed
- ✅ 6th command shows error: "Daily Generation Limit Reached"
- ✅ Error shows reset time

### Test 3: Image-to-Image Button

```
(Generate first image)
Click [📷] button on image
Enter prompt
```

Expected:

- ✅ Modal popup for text prompt
- ✅ Image transforms based on new prompt
- ✅ Uses quota system (1 generation)
- ✅ Saves to `image_to_image/` folder

### Test 4: Upscale Button

```
(Generate first image)
Click [⬆️] button on image
```

Expected:

- ✅ Image upscales to 2x resolution
- ✅ Uses quota system (1 generation)
- ✅ Saves to `upscale/` folder
- ✅ Upscale button becomes disabled

### Test 5: Quota Reset

```
Wait 24 hours OR manually reset DB
Check quota status
```

Expected:

- ✅ After 24 hours, `Daily: 0/5` resets
- ✅ User can generate 5 more images

## Troubleshooting

### Issue: "StorageManager not initialized"

**Solution:**

- Check main.py **init** has service setup
- Verify STORAGE_ROOT in .env
- Ensure directory exists and is writable

### Issue: "ImageGenerator not initialized"

**Solution:**

- Verify STABILITY_API_KEY is set in .env
- Check API key is valid and has credits
- Review ImageGenerator import path

### Issue: "No image found in recent messages"

**Solution:**

- This is correct behavior - user must reply to bot's image message
- Only looks back 30 messages in channel history

### Issue: "Quota limit reached" on first try

**Solution:**

- Check image_stats.db isn't corrupted
- Delete and let bot recreate it on next start
- Verify MAX_USER_DAILY_GENS is set correctly

### Issue: Images not saving to disk

**Solution:**

- Verify C:\Abby_Storage has write permissions
- Check disk space available
- Review bot logs for storage errors

### Issue: Bot crashes on startup

**Solution:**

```python
# Check imports in main.py line 20-21
from abby_core.storage.storage_manager import StorageManager  # ✅ Correct
from abby_core.generation.image_generator import ImageGenerator  # ✅ Correct
```

## Monitoring & Logs

Key log messages to watch for:

```
[🐰] StorageManager initialized successfully         # ✅ Storage ready
[🐰] ImageGenerator initialized successfully         # ✅ Generator ready
[🐰] Abby is online as Abby#9999                    # ✅ Bot ready
[TDOS] Heartbeat emitted                            # ✅ Telemetry working
```

Error messages:

```
[ERROR] Failed to initialize StorageManager: ...     # ❌ Storage failed
[ERROR] Failed to initialize ImageGenerator: ...    # ❌ Generator failed
[ERROR] Command error in imagine: ...               # ❌ Command execution failed
```

## Performance Baselines

Expected performance on TSERVER:

| Operation          | Time   | Notes                                |
| ------------------ | ------ | ------------------------------------ |
| Text-to-Image      | 30-45s | Depends on Stability AI load         |
| Image-to-Image     | 20-30s | Faster than text-to-image            |
| Upscale            | 15-20s | Fastest operation                    |
| Save Image         | <1s    | Local disk write                     |
| Quota Check        | <1ms   | SQLite query                         |
| **Total for user** | 30-50s | User sees response immediately after |

## Rollback Plan

If Phase 2 causes issues:

1. **Quick Rollback** (same day):

   ```bash
   # Replace images.py with backup
   # Comment out service init in main.py
   # Restart bot
   ```

2. **Full Rollback** (need Phase 1 backup):
   ```bash
   # Restore main.py from git
   # Restore images.py to old version
   # Restart bot
   ```

## Post-Deployment Tasks

- [ ] Monitor bot performance for 24 hours
- [ ] Test quota reset after 24 hours
- [ ] Verify storage directory structure created correctly
- [ ] Check image_stats.db has quota data
- [ ] Test with multiple users simultaneously
- [ ] Monitor TSERVER disk usage
- [ ] Review error logs for any issues

## Success Criteria

Phase 2 is successful when:

✅ Bot starts without errors
✅ /imagine command works
✅ Images save to correct folder structure
✅ Quota system enforces limits
✅ Quota status displays in Discord
✅ Daily limit resets after 24 hours
✅ Image-to-Image transformations work
✅ Upscale functionality works
✅ No hard-coded paths in code
✅ All API calls go through ImageGenerator service

---

## Support

If you encounter issues not covered here:

1. Check `docs/PHASE_2_IMPLEMENTATION_SUMMARY.md` for details
2. Review logs in `logs/` directory
3. Check `ARCHITECTURE_AUDIT.md` for system design
4. Review `abby_core/generation/image_generator.py` for API methods
5. Review `abby_core/storage/storage_manager.py` for storage methods

---

**Estimated Deployment Time:** 15-20 minutes
**Risk Level:** Low (new functionality, doesn't break existing commands)
**Rollback Time:** <5 minutes if needed

Good luck with deployment! 🚀
