# Script Cleanup Analysis & Recommendations

**Date:** February 9, 2026

---

## 🔍 Scripts Inventory

### Found 5 PowerShell Scripts + 1 Bash + 1 Python

#### ✅ **KEEP** - Currently Used, Necessary

1. **`docker/docker-build-push.ps1`**
   - Status: **ACTIVE & NECESSARY**
   - Purpose: Build Docker image and push to registry
   - Used: Every deployment from dev → TSERVER
   - Keep: YES - Core part of CI/CD pipeline
   - Reference: DOCKER_MIGRATION_GUIDE.md, CI_CD_ARCHITECTURE.md

2. **`docker/dev-compose-helper.ps1`**
   - Status: **ACTIVE & NECESSARY**
   - Purpose: Helper for local development (up, down, logs, db, etc.)
   - Used: Daily by developers
   - Keep: YES - Simplifies local development workflow
   - Reference: LOCAL_DEV_QUICKSTART.md

#### ❌ **DELETE** - Legacy/Windows NSSM Era (Deprecated)

3. **`scripts/deploy/CHEAT_SHEET.ps1`**
   - Status: **LEGACY - FROM NSSM DAYS**
   - Purpose: Reference for old NSSM deployment commands
   - Context: References `.\scripts\deploy-to-tserver.ps1` (no longer exists)
   - References: `nssm` service manager (Windows NSSM, not Docker)
   - Last Used: Before Docker migration
   - Delete: YES - Obsolete, replaced by docker-build-push.ps1
   - Replacement: QUICK_REFERENCE.md (modern Docker commands)

4. **`scripts/deploy/abby-service.ps1`**
   - Status: **LEGACY - FROM NSSM DAYS**
   - Purpose: Manage NSSM Windows service (status, restart, logs, debug)
   - Context: Uses `nssm` commands, references `AbbyBot` NSSM service
   - Last Used: Before Docker migration to Linux
   - Delete: YES - NSSM service no longer exists on TSERVER
   - Replacement: `docker compose ps`, `docker compose logs`, `docker compose restart`

#### ❌ **DELETE** - MongoDB Auth Workaround (Deprecated)

5. **`docker/create-mongo-user.sh`**
   - Status: **LEGACY - MONGODB AUTH WORKAROUND**
   - Purpose: Create MongoDB user via shell script
   - Context: Was attempt to manually create `abby` user
   - Problem Solved: MongoDB auth blocking deployment (DOCKER_MIGRATION_GUIDE.md Problem #2)
   - Final Decision: Disable MongoDB auth (network isolation sufficient)
   - Delete: YES - No longer needed, MongoDB has NO auth
   - Reason: We decided "no auth" architecture, this script is useless now

6. **`docker/test-mongo-user.py`**
   - Status: **LEGACY - MONGODB AUTH WORKAROUND**
   - Purpose: Test MongoDB connection, attempt to create user via Python
   - Context: Python attempt to work around auth creation issues
   - Problem Solved: Same as above - MongoDB auth blocking deployment
   - Delete: YES - No longer needed, MongoDB has NO auth
   - Reason: We decided "no auth" architecture, this script is useless now

#### ⚠️ **QUESTIONABLE** - Context Files

7. **`docker/mongo-init-users.js`**
   - Status: **SEMI-LEGACY - REFERENCES DISABLED AUTH**
   - Purpose: MongoDB init script (would create users on first startup)
   - Context: References MongoDB auth setup (which we disabled)
   - Comments: "No root password for local setup", "Production: set MONGO_INITDB_ROOT_USERNAME"
   - Delete: YES - Not used in production (auth disabled, init scripts never run)
   - When Needed: Only if we re-enable MongoDB auth in future

8. **`docker/compose.mongo.yml`**
   - Status: **SEMI-LEGACY - EXAMPLE/REFERENCE**
   - Purpose: Example MongoDB docker-compose service
   - Used By: Nobody actively (real config is /srv/tserver/compose/docker-compose.yml)
   - Delete: YES - Reference/template file, not used in practice
   - Reason: Replaced by actual TSERVER docker-compose.yml

9. **`docker/abby.env.template`**
   - Status: **SEMI-LEGACY - OUTDATED TEMPLATE**
   - Purpose: Environment template for TSERVER
   - Problems:
     - References MongoDB auth: `MONGODB_URI=mongodb://abby:abby_password@mongo...`
     - We now use: `MONGODB_URI=mongodb://mongo:27017/abby` (no auth)
   - Delete: YES - Superseded by .env.dev.example (current, correct)
   - Note: .env.dev.example has correct no-auth MongoDB URI

10. **`docker/TSERVER_ARCHITECTURE.md`**
    - Status: **SEMI-LEGACY - SUPERSEDED BY BETTER DOCS**
    - Purpose: Architecture documentation
    - Replaced By: DOCKER_MIGRATION_GUIDE.md, CI_CD_ARCHITECTURE.md
    - Delete: YES - Better documentation now exists

11. **`docker/TSERVER_DEPLOYMENT_ORDER.md`**
    - Status: **SEMI-LEGACY - PROCEDURE DOCUMENTED ELSEWHERE**
    - Purpose: Deployment order documentation
    - Replaced By: CI_CD_ARCHITECTURE.md, Operational Guide
    - Delete: YES - Covered in comprehensive guides

12. **`docker/README_QUICK_START.md`**
    - Status: **SEMI-LEGACY - SUPERSEDED**
    - Purpose: Old quick start guide
    - Replaced By: LOCAL_DEV_QUICKSTART.md, QUICK_REFERENCE.md
    - Delete: YES - Better documentation now exists

13. **`docker/CaddyFile`**
    - Status: **KEEP - CONFIG FILE**
    - Purpose: Caddy reverse proxy configuration
    - Delete: NO - This is a configuration, not a workaround script

14. **`docker/Corefile`**
    - Status: **KEEP - CONFIG FILE**
    - Purpose: CoreDNS configuration
    - Delete: NO - This is a configuration, not a workaround script

15. **`docker/tdos.internal.db`**
    - Status: **KEEP - CONFIG FILE**
    - Purpose: DNS zone database for CoreDNS
    - Delete: NO - This is a configuration, not a workaround script

---

## 📊 Summary

| Category                         | Count | Action    |
| -------------------------------- | ----- | --------- |
| Keep (Active, Necessary)         | 2     | ✅ Keep   |
| Delete (Legacy NSSM)             | 2     | ❌ Delete |
| Delete (MongoDB Auth Workaround) | 2     | ❌ Delete |
| Delete (Superseded Docs)         | 3     | ❌ Delete |
| Keep (Config Files)              | 3     | ✅ Keep   |

### Files to Delete (7 Total)

1. ❌ `scripts/deploy/CHEAT_SHEET.ps1` - NSSM era reference
2. ❌ `scripts/deploy/abby-service.ps1` - NSSM service manager
3. ❌ `docker/create-mongo-user.sh` - MongoDB auth workaround
4. ❌ `docker/test-mongo-user.py` - MongoDB auth workaround
5. ❌ `docker/mongo-init-users.js` - MongoDB init (auth disabled)
6. ❌ `docker/abby.env.template` - Old template (superseded by .env.dev.example)
7. ❌ `docker/compose.mongo.yml` - Reference/example (not used)
8. ❌ `docker/TSERVER_ARCHITECTURE.md` - Superseded
9. ❌ `docker/TSERVER_DEPLOYMENT_ORDER.md` - Superseded
10. ❌ `docker/README_QUICK_START.md` - Superseded

### Files to Keep (5 Total)

1. ✅ `docker/docker-build-push.ps1` - Build & deploy
2. ✅ `docker/dev-compose-helper.ps1` - Local dev helper
3. ✅ `docker/CaddyFile` - Reverse proxy config
4. ✅ `docker/Corefile` - DNS config
5. ✅ `docker/tdos.internal.db` - DNS zone

### Files Already Updated (2 Total)

1. ✅ `docker/.env.dev.example` - Current, correct template
2. ✅ `docker/docker-compose.dev.yml` - Current, active

---

## 🎯 Cleanup Plan

### Phase 1: Delete Legacy Scripts

Remove these directories/files:

```
c:\TDOS\apps\abby_bot\scripts\deploy\
  ├── CHEAT_SHEET.ps1
  └── abby-service.ps1

c:\TDOS\apps\abby_bot\docker\
  ├── create-mongo-user.sh
  ├── test-mongo-user.py
  ├── mongo-init-users.js
  ├── compose.mongo.yml
  ├── abby.env.template
  ├── TSERVER_ARCHITECTURE.md
  ├── TSERVER_DEPLOYMENT_ORDER.md
  └── README_QUICK_START.md
```

### Phase 2: Keep Only Necessary

Core files that remain:

```
c:\TDOS\apps\abby_bot\docker\
  ├── docker-build-push.ps1 ✅
  ├── dev-compose-helper.ps1 ✅
  ├── docker-compose.dev.yml ✅
  ├── .env.dev.example ✅
  ├── CaddyFile ✅
  ├── Corefile ✅
  └── tdos.internal.db ✅
```

### Phase 3: Verify Git Status

After cleanup:

```
git status
# Should show deleted files
git add -A
git commit -m "cleanup: remove legacy NSSM scripts and MongoDB auth workarounds"
```

---

## 📋 Verification Checklist

- [ ] CHEAT_SHEET.ps1 deleted
- [ ] abby-service.ps1 deleted
- [ ] create-mongo-user.sh deleted
- [ ] test-mongo-user.py deleted
- [ ] mongo-init-users.js deleted
- [ ] compose.mongo.yml deleted
- [ ] abby.env.template deleted
- [ ] TSERVER_ARCHITECTURE.md deleted
- [ ] TSERVER_DEPLOYMENT_ORDER.md deleted
- [ ] README_QUICK_START.md deleted
- [ ] docker-build-push.ps1 still exists
- [ ] dev-compose-helper.ps1 still exists
- [ ] docker-compose.dev.yml still exists
- [ ] .env.dev.example still exists

---

## ✨ Benefits of Cleanup

1. **Clarity:** Only active, necessary files remain
2. **Reduced Confusion:** No deprecated commands to accidentally run
3. **Easier Onboarding:** New developers see only what they need
4. **Less Technical Debt:** No confusing legacy workarounds
5. **Mirrors SOP:** Documentation matches actual codebase

---

**Ready to proceed with cleanup? Answer yes to proceed with deletion.**
