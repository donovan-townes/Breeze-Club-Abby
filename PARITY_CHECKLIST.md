# Local Dev ↔ Production Parity Checklist

**Goal:** Keep local development environment perfectly mirrored to production so what works locally works on TSERVER.

## Weekly Parity Verification

**What this does:** Ensures your local dev environment matches production configuration, preventing surprise failures when deploying.

### File Structure Parity

- [ ] Local Dockerfile unchanged from production

  ```bash
  diff c:\TDOS\apps\abby_bot\Dockerfile c:\TDOS\apps\abby_bot\Dockerfile.prod
  # Should have no significant differences
  ```

- [ ] requirements.txt unchanged

  ```bash
  diff c:\TDOS\apps\abby_bot\requirements.txt /srv/tserver/compose/requirements.txt
  # Should be identical
  ```

- [ ] docker-compose.dev.yml mirrors docker-compose.yml structure
  ```
  Compare:
  - abby service definition (should be same except for image/volumes)
  - MongoDB service definition (should be same except for ports)
  - Network configuration (should be same)
  ```

### Dependencies Parity

- [ ] Python version matches

  ```
  Dockerfile: FROM python:3.12-slim
  Should match in both dev and prod
  ```

- [ ] MongoDB version matches

  ```
  Dev: mongo:7.0 in docker-compose.dev.yml
  Prod: mongo:7.0 in docker-compose.yml on TSERVER
  docker-compose.dev.yml: image: mongo:7.0
  /srv/tserver/compose/docker-compose.yml: image: mongo:7.0
  ```

- [ ] Base image status
  ```bash
  # Check if newer versions available
  docker pull python:3.12-slim
  docker pull mongo:7.0
  # If new versions exist, plan upgrade together for both envs
  ```

### Configuration Parity

- [ ] `.env.dev` structure mirrors `/srv/tserver/compose/abby.env`

  ```
  Both should have:
  ✓ MONGODB_URI=mongodb://mongo:27017/abby
  ✓ STORAGE_PATH=/data/storage
  ✓ LOG_PATH=/data/logs
  ✓ All the same environment variables

  Differences OK:
  ✗ .env.dev has test tokens
  ✗ abby.env has production tokens
  ✗ .env.dev has LOG_LEVEL=DEBUG
  ✗ abby.env has LOG_LEVEL=INFO
  ```

- [ ] Storage paths are consistent

  ```
  Dev: ./dev-state/abby/storage → /data/storage in container
  Prod: /srv/tserver/state/abby/storage → /data/storage in container

  Both mount to same /data/ path in container ✓
  ```

- [ ] MongoDB connection strings identical

  ```
  Dev: mongodb://mongo:27017/abby
  Prod: mongodb://mongo:27017/abby

  Should be identical (same hostname "mongo" works in both networks)
  ```

### Health Check Parity

- [ ] MongoDB health check identical

  ```
  Dev: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
  Prod: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet

  Should be identical
  ```

- [ ] Test health check locally
  ```bash
  docker compose -f docker-compose.dev.yml ps
  # mongo should show: (healthy)
  ```

### Network Parity

- [ ] Service discovery works the same

  ```
  Dev: mongo:27017 (on abby_dev_net)
  Prod: mongo:27017 (on tserver_net)

  Both containers can reach "mongo" by hostname ✓
  ```

- [ ] Port mapping consistency

  ```
  Dev: 27017:27017 (MongoDB exposed locally for debugging)
  Prod: No MongoDB port exposure (internal only)

  This difference is OK and intentional
  ```

### Testing Parity

- [ ] Test same scenario locally and on prod

  ```
  1. Local: Start fresh environment
     docker compose -f docker-compose.dev.yml down
     rm -r docker/dev-state
     docker compose -f docker-compose.dev.yml up

  2. Wait for: [✓] System operational

  3. Test: Discord command in test guild

  4. On TSERVER:
     docker compose logs abby | grep "System operational"

  5. Verify: Same version running
  ```

## Before Any Deployment

**Do this checklist EVERY time before pushing to production:**

- [ ] Local environment starts cleanly

  ```powershell
  docker compose -f docker-compose.dev.yml down
  rm -r docker/dev-state
  docker compose -f docker-compose.dev.yml up
  # Wait for: [✓] System operational
  ```

- [ ] No errors in local logs

  ```powershell
  docker compose -f docker-compose.dev.yml logs abby | Select-String "Error|error|FAIL|fail"
  # Should return nothing (no errors)
  ```

- [ ] Database initialized successfully

  ```bash
  docker compose -f docker-compose.dev.yml exec mongo mongosh localhost:27017/abby --quiet --eval "db.collections.countDocuments()"
  # Should return: 37 (or current number of collections)
  ```

- [ ] Discord connection successful (check logs)

  ```powershell
  docker compose -f docker-compose.dev.yml logs abby | Select-String "Discord|Connected"
  # Should see connection messages
  ```

- [ ] Test a Discord command locally

  ```
  In test Discord guild:
  /help or !dev help
  # Bot should respond
  ```

- [ ] All cogs loaded

  ```powershell
  docker compose -f docker-compose.dev.yml logs abby | Select-String "cogs loaded"
  # Should show: "33 cogs loaded successfully"
  ```

- [ ] No warnings in startup

  ```powershell
  docker compose -f docker-compose.dev.yml logs abby --tail 100 | Select-String "warn|Warning"
  # Should return nothing (or only expected warnings)
  ```

- [ ] Image ready to push

  ```powershell
  # Verify image exists and is recent
  docker image ls | Select-String "abby.*dev"
  # Should show recent timestamp
  ```

- [ ] .env.dev NOT committed to git
  ```bash
  git status | grep ".env.dev"
  # Should show nothing (or "nothing to commit")
  ```

## During Deployment

**Do this when pushing to production:**

- [ ] Registry reachable from dev machine

  ```powershell
  curl http://100.86.240.84:5000/v2/_catalog
  # Should return JSON catalog
  ```

- [ ] Build and push script runs without errors

  ```powershell
  .\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"
  # Should output: [✓] Build completed
  # Should output: [✓] Push completed
  ```

- [ ] Image in registry

  ```powershell
  curl http://100.86.240.84:5000/v2/abby/tags/list
  # Should show: {"name":"abby","tags":["latest"]}
  ```

- [ ] SSH to TSERVER works

  ```powershell
  ssh tserver 'echo "Connection OK"'
  # Should output: Connection OK
  ```

- [ ] Pull succeeds on TSERVER

  ```bash
  cd /srv/tserver/compose
  docker compose pull abby
  # Should succeed (image might be "up to date")
  ```

- [ ] Deployment succeeds
  ```bash
  docker compose up -d abby
  # Should start container successfully
  ```

## After Deployment

**Verify production matches dev behavior:**

- [ ] Production bot comes online

  ```bash
  docker compose logs abby --tail 50 | grep "System operational"
  # Should see: [✓] System operational
  ```

- [ ] No errors in production logs

  ```bash
  docker compose logs abby | grep -i error
  # Should return nothing
  ```

- [ ] Test production bot in Discord

  ```
  In production Discord guild:
  /help or command
  # Bot should respond
  ```

- [ ] Production database working

  ```bash
  docker exec mongo mongosh localhost:27017/abby --quiet --eval "db.stats().collections"
  # Should return number of collections
  ```

- [ ] Memory/CPU reasonable

  ```bash
  docker stats abby
  # CPU: < 10%
  # Memory: < 1GB (reasonable for Python bot)
  ```

- [ ] Local and prod health match

  ```
  Dev: docker compose -f docker-compose.dev.yml logs abby | grep "Health"
  Prod: docker compose logs abby | grep "Health"

  Both should show: [💚] Health: MongoDB: OK | Storage: OK | Image Gen: OK
  ```

## Sync Checklist

**When updating production files:**

Make these changes to BOTH dev and production:

- [ ] **Dockerfile change**

  ```
  File: c:\TDOS\apps\abby_bot\Dockerfile
  Then sync to TSERVER? NO (baked into image, no need to update separately)
  ```

- [ ] **requirements.txt change**

  ```
  File: c:\TDOS\apps\abby_bot\requirements.txt
  Action: Rebuild Docker image (automatic in build process)
  ```

- [ ] **MongoDB version upgrade**

  ```
  Update dev:
    c:\TDOS\apps\abby_bot\docker\docker-compose.dev.yml
    Change: image: mongo:8.0

  Update prod:
    /srv/tserver/compose/docker-compose.yml
    Change: image: mongo:8.0

  Test locally first, then deploy to prod
  ```

- [ ] **New environment variable**

  ```
  Add to:
    c:\TDOS\apps\abby_bot\docker\.env.dev.example (dev)
    /srv/tserver/compose/abby.env (prod)

  Both should have same variable name
  ```

- [ ] **Base image update** (e.g., python:3.12-slim → python:3.13-slim)
  ```
  1. Update Dockerfile
  2. Test locally for compatibility
  3. If successful:
     - Rebuild and push: .\docker\docker-build-push.ps1
     - Deploy on TSERVER: docker compose pull && docker compose up
  4. Monitor logs for compatibility issues
  ```

## Emergency: Fix Production Mismatch

**If production behaves differently than dev:**

### Step 1: Identify the difference

```bash
# Compare local and remote
Local:
  docker compose -f docker-compose.dev.yml logs abby --tail 50

Production:
  ssh tserver 'cd /srv/tserver/compose && docker compose logs abby --tail 50'

# Look for differences in startup messages
```

### Step 2: Reproduce locally

```powershell
# If prod failing, reproduce issue locally
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up --build

# Try to trigger same error
```

### Step 3: Root cause analysis

- [ ] Is it an environment variable mismatch?

  ```bash
  docker compose -f docker-compose.dev.yml exec abby printenv | grep -i mongo
  ssh tserver 'docker exec abby printenv | grep -i mongo'
  # Compare output
  ```

- [ ] Is it a dependency version mismatch?

  ```bash
  docker compose -f docker-compose.dev.yml exec abby pip list | grep -i package-name
  ssh tserver 'docker exec abby pip list | grep -i package-name'
  # Compare versions
  ```

- [ ] Is it a file/permission issue?
  ```bash
  docker compose -f docker-compose.dev.yml exec abby ls -la /data/storage
  ssh tserver 'docker exec abby ls -la /data/storage'
  # Compare permissions
  ```

### Step 4: Fix and re-test

```
1. Identify problem
2. Fix in local environment
3. Verify fix works locally
4. Rebuild and push: .\docker\docker-build-push.ps1
5. Deploy on TSERVER
6. Verify production matches dev
7. Document what was wrong
```

## Documentation Sync

**Update these docs when making changes:**

- [ ] Local Development Quick Start - If workflow changes
- [ ] CI/CD Architecture - If deployment process changes
- [ ] DOCKER_MIGRATION_GUIDE - If infrastructure changes
- [ ] Dockerfile - Code comments explain rationale
- [ ] docker-compose files - Comments explain each service

---

**Last Checked:** [Your Date Here]  
**Next Check:** [One Week from Today]  
**Owner:** [Your Name]

---

## Tips for Maintaining Parity

**1. Source of Truth: Production**

```
When in doubt, check what's on TSERVER first
Then make dev match production
Not the other way around
```

**2. Document Intentional Differences**

```
✓ Intentional:
  - .env.dev has test tokens, abby.env has prod tokens
  - dev exposes MongoDB port, prod doesn't
  - dev has LOG_LEVEL=DEBUG, prod has INFO

✗ Unintentional (fix immediately):
  - Different base image versions
  - Different Python versions
  - Different requirements.txt
  - Different Dockerfile structure
```

**3. Use Diff Tools**

```powershell
# Compare local vs production structure
Compare-Object (docker compose -f docker-compose.dev.yml config) `
              (ssh tserver "docker compose config")

# Look for service definition differences
```

**4. Automate Testing**

```bash
# Create a test script that runs same tests locally and on prod
# Compare results

Test scenarios:
- Bot startup time
- Database response time
- Discord connection success
- Memory usage
- Error rates
```

**5. Keep Git History Clean**

```
Only commit meaningful changes:
- Code changes
- Dockerfile updates
- requirements.txt updates
- Docs updates

Never commit:
- .env.dev files
- dev-state directory
- personal notes in code
```

---

**For Questions:** See DOCKER_MIGRATION_GUIDE.md or CI_CD_ARCHITECTURE.md
