# CI/CD Architecture & Workflow

This document explains the complete CI/CD flow from local development to production deployment on TSERVER.

## The Complete Flow: From Laptop to Production

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          YOUR DEVELOPMENT MACHINE (Windows)                 │
│                                                                              │
│  Step 1: DEVELOP LOCALLY                                                   │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ docker compose -f docker-compose.dev.yml up                   │        │
│  │                                                                │        │
│  │ ✓ MongoDB running in Docker                                  │        │
│  │ ✓ Abby bot running in Docker                                │        │
│  │ ✓ Code mounted for live editing                             │        │
│  │ ✓ Configuration from .env.dev (test secrets)                │        │
│  │ ✓ Data persists in ./dev-state/                             │        │
│  │                                                                │        │
│  │ You: Make changes, test in Discord, iterate                 │        │
│  │ Time per iteration: ~30 seconds (restart container)          │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                              ↓                                              │
│  Step 2: BUILD & PUSH                                                      │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ .\docker\docker-build-push.ps1                                │        │
│  │                                                                │        │
│  │ Build Process:                                                │        │
│  │ - Reads local Dockerfile                                     │        │
│  │ - Stage 1: Build dependencies (gcc, g++, etc.)              │        │
│  │ - Stage 2: Runtime image (clean, just Python + app)         │        │
│  │ - Tag as: 100.86.240.84:5000/abby:latest                   │        │
│  │ - Uses local caching (incremental builds ~30s)              │        │
│  │                                                                │        │
│  │ Push Process:                                                 │        │
│  │ - Upload to TSERVER registry (direct IP connection)          │        │
│  │ - Image now available at registry.tdos.internal:5000         │        │
│  │                                                                │        │
│  │ Time: ~2-3 minutes first build, ~30s for code changes        │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                              ↓                                              │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               │
                    NETWORK (Tailscale VPN)
                               │
                               ↓
┌──────────────────────────────┬───────────────────────────────────────────────┐
│                          TSERVER (Ubuntu Linux)                             │
│                                                                              │
│  Step 3: PULL IMAGE FROM REGISTRY                                          │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ docker compose pull abby                                       │        │
│  │                                                                │        │
│  │ Registry lookup: registry.tdos.internal:5000 (CoreDNS)        │        │
│  │ → Resolves to: 100.86.240.84                                 │        │
│  │ → Registry returns: abby image layers                         │        │
│  │                                                                │        │
│  │ Image checked against cache:                                  │        │
│  │ - If already cached: Skip (0 seconds)                         │        │
│  │ - If new: Download layers (5-10 seconds)                      │        │
│  │                                                                │        │
│  │ Docker Registry stores ALL versions:                          │        │
│  │ - abby:latest (current)                                       │        │
│  │ - abby:1.2.3 (previous versions, available for rollback)      │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                              ↓                                              │
│  Step 4: DEPLOY & RESTART                                                  │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ docker compose up -d abby                                     │        │
│  │                                                                │        │
│  │ Docker Compose orchestration:                                 │        │
│  │ 1. Check dependencies (mongo service must be healthy)         │        │
│  │ 2. Stop old abby container                                   │        │
│  │ 3. Start new abby container from pulled image                │        │
│  │ 4. Mount config from: /srv/tserver/compose/abby.env          │        │
│  │ 5. Mount data from: /srv/tserver/state/abby                  │        │
│  │ 6. Connect to tserver_net (MongoDB at mongo:27017)           │        │
│  │                                                                │        │
│  │ Abby startup (25 seconds typically):                          │        │
│  │ 1. Load environment (2s) → Reads /srv/tserver/compose/abby.env        │
│  │ 2. Connect MongoDB (3s) → URI: mongodb://mongo:27017/abby    │        │
│  │ 3. Initialize collections (18s) → Create tables/indexes      │        │
│  │ 4. Load cogs (1s) → 33 Discord command handlers              │        │
│  │ 5. Connect Discord (1s) → Login to Discord API               │        │
│  │ 6. System healthy → [✓] System operational                   │        │
│  │                                                                │        │
│  │ Log output:                                                    │        │
│  │ [✓] MongoDB connected                                         │        │
│  │ [✓] All 37 collection(s) initialized                         │        │
│  │ [✓] 33 cogs loaded successfully                              │        │
│  │ [✓] System operational - ready to serve 4 guild(s)           │        │
│  │                                                                │        │
│  │ Time: ~25 seconds for full startup                            │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                              ↓                                              │
│  Step 5: VERIFY & MONITOR                                                  │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ docker compose ps                                              │        │
│  │ docker compose logs abby --tail 50                            │        │
│  │                                                                │        │
│  │ Expected Status: Up X seconds (healthy)                       │        │
│  │ Discord:        Bot online in 4 guilds                        │        │
│  │ All Systems:    MongoDB:OK, Storage:OK, Image Gen:OK          │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ✅ PRODUCTION DEPLOYMENT COMPLETE                                         │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Architectural Components

### 1. **Local Docker Registry (Private)**

```
Location: TSERVER /srv/tserver/state/registry
URL: registry.tdos.internal:5000 (from TSERVER)
    100.86.240.84:5000 (from dev machine)

Purpose:
  - Private image storage (not Docker Hub)
  - Fast local network transfers (~10x faster)
  - Version history (all images kept for rollback)
  - No rate limits
  - No external dependencies

How it Works:
  Dev builds: docker build -t 100.86.240.84:5000/abby:latest .
  Dev pushes: docker push 100.86.240.84:5000/abby:latest
  TSERVER accesses: registry.tdos.internal:5000/abby:latest
    └─ Resolved by CoreDNS: registry.tdos.internal → 100.86.240.84
```

### 2. **Docker Compose Orchestration**

```
Dev Machine: docker-compose.dev.yml
  - Runs MongoDB + Abby locally
  - Each service isolated in containers
  - Network: abby_dev_net (bridge, internal)
  - Data: ./dev-state/ (on Windows disk)

TSERVER: docker-compose.yml
  - Runs all TDOS services (mongo, registry, coredns, caddy, abby, docs)
  - All services on tserver_net (bridge, isolated)
  - Data: /srv/tserver/state/ (on TSERVER disk)
  - Services reach each other by name (mongo, registry, etc.)
```

### 3. **Image Build Strategy**

```
Multi-Stage Dockerfile:

  Stage 1: Builder
  ├─ python:3.12-slim
  ├─ apt install build-essential g++ (C++ compiler)
  ├─ pip install requirements.txt (compiles native extensions)
  └─ Result: Big image with build tools (~2.5GB)

  Stage 2: Runtime
  ├─ python:3.12-slim (fresh start)
  ├─ COPY --from=builder /usr/local/lib (just the compiled packages)
  ├─ COPY . /app (application code only)
  └─ Result: Small image (~1.2GB)

Benefits:
  - Builder layer cached between builds
  - Code changes: ~30 seconds (just copy new code)
  - Dependency changes: ~5 minutes (rebuild builder)
  - First build: ~10-15 minutes (compile everything)

Cache behavior:
  docker build . (from scratch)
  └─ No cache hits: ~10-15 minutes

  docker build . (with cached builder)
  └─ Code only: ~30 seconds
  └─ Dependency change: ~5 minutes
```

## Complete Deployment Checklist

```powershell
# ─────────────────────────────────────────────────────────
# DEVELOPMENT PHASE (On Your Windows Machine)
# ─────────────────────────────────────────────────────────

Step 1: Start local environment
  .\docker\dev-compose-helper.ps1 up
  # Wait for: [✓] System operational

Step 2: Make changes and test
  # Edit code, test in Discord, iterate

Step 3: Run all tests (if applicable)
  # docker compose -f docker-compose.dev.yml exec abby pytest

Step 4: Check logs for no errors
  .\docker\dev-compose-helper.ps1 logs -Service abby

# ─────────────────────────────────────────────────────────
# BUILD & DEPLOYMENT PHASE
# ─────────────────────────────────────────────────────────

Step 5: Build and push to registry
  .\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"
  # Output: [✓] Build completed in X seconds
  # Output: [✓] Push completed in Y seconds

Step 6: Verify registry has image
  curl http://100.86.240.84:5000/v2/abby/tags/list
  # Shows: {"name":"abby","tags":["latest"]}

Step 7: SSH to TSERVER
  ssh tserver

Step 8: Navigate to compose directory
  cd /srv/tserver/compose

Step 9: Pull latest image
  docker compose pull abby
  # Should show it's up to date or download new layers

Step 10: Deploy
  docker compose up -d abby

Step 11: Verify deployment
  docker compose ps abby
  # Status should be: Up X seconds (healthy)

Step 12: Check logs
  docker compose logs abby --tail 50
  # Look for: [✓] System operational

Step 13: Verify in Discord
  # Check bot is online in test guild
  # Run a test command to verify functionality

# ─────────────────────────────────────────────────────────
# VERIFICATION & MONITORING
# ─────────────────────────────────────────────────────────

Step 14: Monitor for errors (30 seconds)
  docker compose logs -f abby
  # Watch for any error messages

Step 15: All services healthy
  docker compose ps
  # All should show: Up X seconds (healthy)

✅ DEPLOYMENT COMPLETE
```

## Rollback Procedure (If Something Breaks)

```
Scenario: New version breaks something, need to revert

Option 1: Quick rollback to previous image (if it was recent)
  ssh tserver
  cd /srv/tserver/compose

  # Check available images
  docker image ls | grep abby
  # Shows: registry.tdos.internal:5000/abby  latest  ...
  # Shows: registry.tdos.internal:5000/abby  1.2.2   ...

  # Edit docker-compose.yml
  nano docker-compose.yml
  # Change: image: registry.tdos.internal:5000/abby:1.2.2

  # Deploy
  docker compose up -d abby

  ✅ Back to previous version in ~30 seconds

Option 2: If rollback needed but image deleted

  # Go back to dev machine
  # Find last known good commit
  git checkout <commit-hash>

  # Rebuild and push
  .\docker\docker-build-push.ps1

  # Deploy on TSERVER
  docker compose pull abby && docker compose up -d abby
```

## Monitoring & Health Checks

```
Continuous Monitoring:
  ssh tserver 'cd /srv/tserver/compose && watch docker compose ps'
  # Refreshes every 2 seconds, shows health status

Health Indicators (watch these):

✅ HEALTHY:
  STATUS: Up X minutes (healthy)
  Logs: [💚] Health: MongoDB: OK | Storage: OK | Image Gen: OK
  Discord: Bot shows as online, responds to commands

⚠️  WARNING SIGNS:
  STATUS: Up X minutes (unhealthy)
  Logs: [Connection refused]
  Logs: [Authentication failed]
  Logs: Error messages appearing repeatedly

❌ DOWN:
  STATUS: Exited (error code)
  Logs: Final log message shows crash
  Discord: Bot offline

Response to Issues:
  1. Check logs: docker compose logs abby --tail 100
  2. Restart: docker compose restart abby
  3. If still failing: docker compose pull abby && docker compose up -d abby
  4. If still failing: Rollback to previous version
```

## Environment Variable Flow

```
┌─ Build Time ────────────────────────────────────┐
│                                                 │
│ Dockerfile specifies: ENV LOG_LEVEL=INFO       │
│ (Can be overridden at runtime)                 │
│                                                 │
└─────────────────────────────────────────────────┘

┌─ Runtime on Dev Machine ────────────────────────┐
│                                                 │
│ .env.dev has: LOG_LEVEL=DEBUG                  │
│ docker-compose.dev.yml env_file: ./.env.dev    │
│ Container gets: LOG_LEVEL=DEBUG (overrides)    │
│                                                 │
└─────────────────────────────────────────────────┘

┌─ Runtime on TSERVER ────────────────────────────┐
│                                                 │
│ abby.env has: LOG_LEVEL=INFO                   │
│ docker-compose.yml env_file: /srv/tserver/compose/abby.env
│ Container gets: LOG_LEVEL=INFO (overrides)     │
│                                                 │
└─────────────────────────────────────────────────┘

Key Point:
  Image is identical (built same way)
  But behavior changes based on mounted .env
  = Confidence in deployment
```

## Performance Metrics

```
Local Build (Development):
  Cold build (no cache):     10-15 minutes
  Warm build (with cache):   3-5 minutes
  Code-only change:          ~30 seconds

Push to Registry:
  First time:                8-12 seconds (network speed)
  Subsequent (cache):        3-5 seconds

Registry Pull (TSERVER):
  Cached layer:              0 seconds
  New layer:                 5-10 seconds (size dependent)

Container Startup (Abby):
  Database init:             18-20 seconds
  Bot connect:               3-5 seconds
  Total:                     25-30 seconds

Deployment Time (Dev → Prod):
  Code to Prod:
    Build:           30 seconds (with cache)
    Push:            5 seconds
    Pull on TSERVER: 0 seconds (cached)
    Restart bot:     30 seconds (startup time)
    Total:           ~2 minutes

Rollback Time:
  Edit config:       1 minute
  Restart services:  30 seconds
  Total:             ~2 minutes
```

## Disaster Scenarios

```
Scenario 1: Registry Corruption
  Problem: Images deleted from registry
  Solution: Rebuild from source
    Dev machine: .\docker\docker-build-push.ps1
    Result: Image restored to registry
    Time: 10-15 minutes

Scenario 2: MongoDB Crash During Deployment
  Problem: Bot fails to connect
  Solution: MongoDB depends_on should prevent this
    1. Check MongoDB: docker compose ps mongo
    2. If unhealthy: docker compose restart mongo
    3. Wait for health check: ~10 seconds
    4. Bot should reconnect automatically
    Time: ~15 seconds

Scenario 3: TSERVER Disk Full
  Problem: Can't pull new images
  Solution: Clean up old images
    docker system prune -a  # Remove unused images
    Time: 2-5 minutes

Scenario 4: New Code Breaks Production
  Problem: Deployment went wrong
  Solution: Rollback
    1. Edit docker-compose.yml (point to previous tag)
    2. docker compose up -d abby
    3. Done
    Time: ~2 minutes
```

## Security Considerations in CI/CD

```
Image Security:
  ✅ Images built fresh each time (no stale base images)
  ✅ Multi-stage builds reduce attack surface
  ✅ No secrets baked into images (.env files mounted instead)

Registry Security:
  ⚠️  Using HTTP (not HTTPS) - but isolated to internal network
  ⚠️  No authentication on registry - but Tailscale VPN protects access

Secrets Management:
  ✓ Dev secrets: In .env.dev (git-ignored, local only)
  ✓ Prod secrets: In /srv/tserver/compose/abby.env (not in git, on disk)
  ✗ NEVER: Commit secrets to git or bake into images

Best Practices:
  - .env files never in git
  - Secrets in separate encrypted storage (Vault, AWS Secrets Manager)
  - Registry auth would be good for multi-team setups
  - Image signing for verified deployments (advanced)
```

---

**Last Updated:** February 9, 2026  
**For Questions:** See DOCKER_MIGRATION_GUIDE.md or LOCAL_DEV_QUICKSTART.md
