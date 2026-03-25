# Database Configuration Diagnosis & Fixes

**Date:** February 10, 2026  
**Issue:** Abby on TSERVER was querying the dev database (`Abby_Database_Dev`) instead of production database (`Abby_Database`)

---

## 🔍 Root Causes Found & Fixed

### ❌ **Bug #1: Hardcoded Database Name in guild_assistant.py**

**File:** `abby_core/discord/cogs/admin/guild_assistant.py:114`

**Problem:**

```python
stats = run_maintenance(
    storage_client=db.client,
    db_name="Abby_Database",  # ← Hardcoded! Ignores env config
    ...
)
```

**Impact:** Guild maintenance functions always use production database name, even when running in dev.

**Fix Applied:**

```python
stats = run_maintenance(
    storage_client=db.client,
    db_name=db.name,  # ← Use configured database
    ...
)
```

**Status:** ✅ FIXED

---

### ❌ **Bug #2: Production Mode Uses Dev Database (CRITICAL)**

**File:** `launch.py:57-60`

**Problem:**

```python
else:
    # Production mode
    dev_db_override = os.getenv("MONGODB_DB_DEV")
    if dev_db_override:
        os.environ["MONGODB_DB"] = dev_db_override  # ← BUG!
```

**Impact:** In production, if `MONGODB_DB_DEV` env var exists, it OVERWRITES `MONGODB_DB`, forcing use of dev database!

**Fix Applied:**

```python
# Automatically use dev database when --dev mode is enabled
if mode == "dev":
    # Use dev database unless explicitly overridden by MONGODB_DB_DEV env var
    dev_db = os.getenv("MONGODB_DB_DEV", "Abby_Database_Dev")
    os.environ["MONGODB_DB"] = dev_db
# In production mode, NEVER override MONGODB_DB with MONGODB_DB_DEV
# The production environment should have MONGODB_DB set correctly
```

**Status:** ✅ FIXED

---

## ✅ Environment Configuration (Verified Correct)

### Development: `.env`

```
MONGODB_DB=Abby_Database_Dev      ✓ Correct
MONGODB_DB_DEV=Abby_Database_Dev  ✓ Correct (for local dev)
MONGODB_URI=mongodb://...         ✓ Correct (points to local dev mongo)
```

### Production: `.env.prod`

```
MONGODB_DB=Abby_Database          ✓ Correct
MONGODB_DB_DEV=<not set>          ✓ Correct (not needed in prod)
MONGODB_URI=mongodb://localhost:27017  ✓ Correct (TSERVER local mongo)
```

---

## 🔗 Database Selection Logic (After Fixes)

### When `launch.py` launches Abby:

**Development Mode (`--dev`):**

1. Sets `MONGODB_DB` to `MONGODB_DB_DEV` (default: `Abby_Database_Dev`)
2. Uses dev database for all operations ✓

**Production Mode (no `--dev`):**

1. Never touches `MONGODB_DB` environment variable
2. Uses whatever `MONGODB_DB` is set to in environment (default: `Abby_Database`) ✓

### When `mongodb.py` connects:

1. Checks if `MONGODB_DB_DEV` env var exists
   - If yes, uses that (only if set by launch.py in dev mode)
   - If no, uses `MONGODB_DB` (production database name)
2. All database operations use `get_database()` which respects this config ✓

---

## 🧪 How to Verify the Fix

### On TSERVER (Production):

```bash
ssh townes@tserver
cd /srv/tserver/compose
docker compose logs abby | grep -i "using.*database"
# Should show: "Using database: Abby_Database"
```

### Run a test query:

```bash
# SSH tunnel to MongoDB (from dev machine)
ssh -L 27018:localhost:27017 townes@tserver

# In MongoDB Compass (localhost:27018)
# Verify collections are in "abby" database, not "Abby_Database_Dev"
```

---

## 📋 Deployment Checklist

After deploying the fixes:

- [ ] Push fixed code to git
- [ ] Rebuild Docker image: `docker-build-push.ps1`
- [ ] Verify image built with fixes: `docker images`
- [ ] Redeploy to TSERVER:
  ```bash
  ssh townes@tserver
  cd /srv/tserver/compose
  docker compose up -d abby  # Pulls new image and restarts
  ```
- [ ] Check logs: `docker compose logs abby | head -50`
- [ ] Verify in MongoDB Compass that data is in `abby` database
- [ ] Test a maintenance function (guild assistant report)

---

## 🛡️ Prevention for Future

1. **Never use hardcoded database names** - Always use:
   - `os.getenv("MONGODB_DB", "Abby_Database")`
   - `db.name` (from already-fetched database object)
2. **Environment variable hierarchy:**
   - Dev mode: `MONGODB_DB_DEV` → `MONGODB_DB` (set by launch.py)
   - Prod mode: Use `MONGODB_DB` directly (never override with `MONGODB_DB_DEV`)

3. **Code review checklist:**
   - [ ] Search for hardcoded database names (`Abby_Database`, `Abby_Database_Dev`)
   - [ ] Verify all DB operations use configured names via `get_database()`
   - [ ] Confirm launch.py properly sets environment based on mode

---

## 📝 Summary

| Issue                                   | Severity | Status             |
| --------------------------------------- | -------- | ------------------ |
| Hardcoded DB name in guild_assistant.py | HIGH     | ✅ Fixed           |
| Production mode using dev DB override   | CRITICAL | ✅ Fixed           |
| Environment files misconfigured         | LOW      | ✓ Verified Correct |

**Next Step:** Rebuild Docker image and redeploy to TSERVER with the fixed code.
