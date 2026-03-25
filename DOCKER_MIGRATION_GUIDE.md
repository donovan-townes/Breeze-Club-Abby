# Abby Discord Bot - Docker Migration & Deployment Guide

**Document Version:** 1.0  
**Migration Date:** February 8, 2026  
**Target Platform:** TSERVER (Ubuntu 24.04.3 LTS)  
**Status:** ✅ Production Operational

**Related Documentation:**

- [Local Development Quick Start](LOCAL_DEV_QUICKSTART.md) - Get started developing locally in 5 minutes
- [CI/CD Architecture Guide](CI_CD_ARCHITECTURE.md) - Complete flow from dev to production
- [Docker Compose Dev Helper](dev-compose-helper.ps1) - PowerShell script for managing local environment

---

## Executive Summary

This document captures the complete migration of Abby Discord bot from Windows NSSM service to Docker Compose on Linux TSERVER. It includes all infrastructure changes, application modifications, problems encountered, solutions implemented, and critical operational knowledge.

**Migration Scope:**

- Containerized Python application from Windows to Linux
- Established shared infrastructure layer (DNS, Registry, MongoDB)
- Implemented production-grade Docker Compose orchestration
- Resolved environment loading and database authentication issues
- Deployed to production with full operational validation

**Key Outcomes:**

- Abby now runs as a containerized service on TSERVER
- Shared MongoDB service available for all TDOS applications
- Internal Docker Registry for efficient deployments
- CoreDNS for internal service discovery
- Multi-stage Docker builds for fast development iterations

---

## Table of Contents

1. [Infrastructure Changes (TSERVER)](#infrastructure-changes-tserver)
2. [Application Changes (Abby)](#application-changes-abby)
3. [Before vs After: Why Docker Migration Was Needed](#before-vs-after-why-docker-migration-was-needed)
4. [Problems Encountered & Solutions](#problems-encountered--solutions)
5. [Local Development Workflow](#local-development-workflow)
6. [Operational Guide](#operational-guide)
7. [SOP Updates Required](#sop-updates-required)
8. [Critical Knowledge Base](#critical-knowledge-base)
9. [Maintenance Procedures](#maintenance-procedures)

---

## Infrastructure Changes (TSERVER)

### New Services Deployed

#### 1. CoreDNS (Internal DNS Server)

**Purpose:** Enable internal service discovery for `*.tdos.internal` domain

**Configuration:**

- **Location:** `/srv/tserver/compose/coredns/`
- **Port:** 53 (TCP/UDP) on 0.0.0.0
- **Zone:** `tdos.internal`
- **Upstream DNS:** Cloudflare (1.1.1.1) + Google (8.8.8.8)

**DNS Records:**

```
registry.tdos.internal   → 100.86.240.84
tserver.tdos.internal    → 100.86.240.84
caddy.tdos.internal      → 100.86.240.84
ns1.tdos.internal        → 100.86.240.84
```

**Why Needed:** Tailscale MagicDNS only provides base hostname (`tserver`), not subdomains. CoreDNS enables internal service discovery while forwarding external queries to public DNS.

**Files:**

- [Corefile](c:\TDOS\apps\abby_bot\docker\coredns\Corefile) - CoreDNS configuration
- [tdos.internal.db](c:\TDOS\apps\abby_bot\docker\coredns\tdos.internal.db) - DNS zone file

**Health Check:** `dig @localhost registry.tdos.internal` should return `100.86.240.84`

---

#### 2. Docker Registry (Private Image Registry)

**Purpose:** Local container image storage for fast deployments without Docker Hub rate limits

**Configuration:**

- **Location:** `/srv/tserver/state/registry`
- **Hostname:** `registry.tdos.internal`
- **Port:** 5000 (HTTP only, insecure registry)
- **Storage:** `/srv/tserver/state/registry` persistent volume

**Why Needed:**

- Faster deployments (no internet upload/download)
- No Docker Hub rate limits
- Private image storage for internal services
- Enables CI/CD workflows on TSERVER

**Insecure Registry Configuration Required:**
Both dev machine AND TSERVER need Docker daemon configured:

```json
{
  "insecure-registries": ["registry.tdos.internal:5000", "100.86.240.84:5000"]
}
```

**File Location:**

- Windows: `C:\ProgramData\docker\config\daemon.json` (restart Docker Desktop)
- Linux: `/etc/docker/daemon.json` (restart: `sudo systemctl restart docker`)

**Usage:**

- Push: `docker push 100.86.240.84:5000/image:tag` (use IP from dev machine)
- Pull: `docker pull registry.tdos.internal:5000/image:tag` (use hostname from TSERVER)

**Health Check:** `curl http://100.86.240.84:5000/v2/_catalog`

---

#### 3. MongoDB (Shared Database Service)

**Purpose:** Centralized database for all TDOS applications

**Configuration:**

- **Location:** `/srv/tserver/state/mongo/`
- **Version:** MongoDB 7.0
- **Port:** 27017 (internal network only)
- **Authentication:** **DISABLED** (security via network isolation)
- **Persistence:** `/srv/tserver/state/mongo/data`, `/srv/tserver/state/mongo/configdb`

**Why No Authentication:**

- MongoDB only accessible from `tserver_net` Docker bridge network
- No external exposure (not published to host)
- Authentication adds deployment complexity without security benefit
- All containers on same network are trusted TDOS services

**Connection String:**

```
mongodb://mongo:27017/database_name
```

**Why This Changed:**
Originally attempted to use authentication with `root` user and per-database users. This created deployment issues:

- Init scripts only run on first container creation with empty data
- Manual user creation via mongosh failed due to command execution issues
- Authentication blocking all database operations

**Final Decision:** Disable auth entirely. Container network isolation provides sufficient security.

**Health Check:** `docker exec mongo mongosh localhost:27017/test --quiet --eval "db.runCommand('ping')"`

**Databases in Use:**

- `abby` - Abby Discord bot
- (Future TDOS applications can add more databases)

---

#### 4. Caddy (Reverse Proxy)

**Purpose:** Public-facing reverse proxy for web services

**Configuration:**

- **Ports:** 80, 443 (public)
- **Caddyfile Location:** `/srv/tserver/compose/caddy/Caddyfile`
- **Auto HTTPS:** Enabled for public domains

**New Host Blocks Added:**

```
registry.tdos.internal:443 {
    reverse_proxy registry:5000
}
```

**Why Updated:** Enable HTTPS access to Docker Registry (though currently using insecure HTTP:5000 directly)

---

### Infrastructure Summary

**New Docker Network:**

- **Name:** `tserver_net`
- **Type:** Bridge network (isolated)
- **Services:** coredns, mongo, registry, caddy, abby, tdos-docs

**Persistent Volumes:**

```
/srv/tserver/state/
├── mongo/
│   ├── data/          # MongoDB database files
│   └── configdb/      # MongoDB configuration
├── registry/          # Docker Registry storage
└── abby/              # Abby bot data (storage, logs, chroma, events)
```

**Port Mappings (Host → Container):**

- `53:53` - CoreDNS
- `5000:5000` - Docker Registry
- `80:80`, `443:443` - Caddy
- (MongoDB, Abby, docs are internal only)

---

## Application Changes (Abby)

### File Structure Changes

**New Files Created:**

```
apps/abby_bot/
├── Dockerfile                          # Multi-stage container build
├── docker/
│   ├── docker-compose.yml              # Service orchestration
│   ├── docker-build-push.ps1           # Automated build/deploy script
│   ├── abby.env.tserver                # Production environment template
│   ├── coredns/
│   │   ├── Corefile                    # DNS server config
│   │   └── tdos.internal.db            # DNS zone
│   └── caddy/
│       └── Caddyfile                   # Reverse proxy config
└── DOCKER_MIGRATION_GUIDE.md           # This document
```

**Modified Files:**

- [launch.py](c:\TDOS\apps\abby_bot\launch.py) - Added explicit env file loading
- [mongodb.py](c:\TDOS\apps\abby_bot\abby_core\database\mongodb.py) - Added fallback env loading
- [requirements.txt](c:\TDOS\apps\abby_bot\requirements.txt) - Removed `audioop-lts` (Python 3.13+ only)

---

### Critical Code Changes

#### 1. Environment Variable Loading (launch.py)

**Problem:** Docker builds bake `.env` file into image at build time. When container runs, it was loading old baked environment instead of mounted production config.

**Solution:** Explicit env file loading with priority order:

```python
# launch.py (lines 1-21)
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ABBY_ROOT = Path(__file__).parent
sys.path.insert(0, str(ABBY_ROOT))

# Load environment variables from .env file
# Priority: /srv/tserver/compose/abby.env (production mount) -> .env in current dir (dev)
env_file_prod = "/srv/tserver/compose/abby.env"
env_file_dev = ABBY_ROOT / ".env"
if os.path.exists(env_file_prod):
    load_dotenv(env_file_prod)
elif os.path.exists(env_file_dev):
    load_dotenv(env_file_dev)
```

**Why Critical:** Without this, production settings never loaded. Bot connected to wrong MongoDB, used wrong API keys, etc.

**Dev/Prod Behavior:**

- **Development (Windows):** Loads `.env` from `c:\TDOS\apps\abby_bot\.env`
- **Production (Docker):** Loads `/srv/tserver/compose/abby.env` mounted from host

---

#### 2. Multi-Stage Dockerfile

**Problem:** Python dependencies like `hnswlib` require C++ compilation. Full builds took 10-15 minutes. Code changes shouldn't require rebuilding dependencies.

**Solution:** Multi-stage build with separate builder and runtime stages:

```dockerfile
# Stage 1: Builder (installs dependencies with compilation tools)
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential g++ ca-certificates
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime (copies built dependencies, adds code)
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . ./
CMD ["python", "launch.py"]
```

**Benefits:**

- **First build:** ~10-15 minutes (compiles all dependencies)
- **Code-only changes:** ~30 seconds (just copies new code)
- **Dependency cache:** Docker caches builder stage, only rebuilds on requirements.txt change
- **Image size:** Runtime image is smaller (no gcc/g++)

---

#### 3. Production Environment Configuration

**File:** `/srv/tserver/compose/abby.env` (on TSERVER)

**Critical Settings:**

```bash
# ========== Database Configuration ==========
# Shared MongoDB service on TSERVER (no auth - isolated container network)
MONGODB_URI=mongodb://mongo:27017/abby
MONGODB_DB=abby

# ========== Storage Configuration ==========
STORAGE_PATH=/data/storage
LOG_PATH=/data/logs
CHROMA_PERSIST_DIR=/data/chroma
EVENT_LOG_DIR=/data/events

# ========== LLM Configuration ==========
OLLAMA_HOST=http://ollama-host:11434  # Currently unavailable, using OpenAI fallback
OLLAMA_MODEL=llama2
USE_OPENAI_FALLBACK=true
OPENAI_API_KEY=<your-key>
```

**Key Differences from Dev:**

- MongoDB hostname: `mongo` (Docker service name) vs `localhost` (Windows)
- Storage paths: `/data/*` (container mount) vs `c:\path\to\abby\*` (Windows)
- Ollama: Internal Docker hostname vs localhost

---

#### 4. Docker Compose Service Definition

**File:** `/srv/tserver/compose/docker-compose.yml`

**Abby Service:**

```yaml
abby:
  image: registry.tdos.internal:5000/abby:latest
  container_name: abby
  restart: unless-stopped
  env_file: /srv/tserver/compose/abby.env
  volumes:
    - /srv/tserver/state/abby:/data
  networks:
    - tserver_net
  depends_on:
    mongo:
      condition: service_healthy
```

**Key Configuration:**

- **Image:** Pulled from internal registry (not Docker Hub)
- **env_file:** Mounts production config from host
- **volumes:** Persists data on host at `/srv/tserver/state/abby`
- **depends_on:** Waits for MongoDB to be healthy before starting
- **restart:** Automatically restarts on failure or host reboot

---

## Before vs After: Why Docker Migration Was Needed

### Before: Windows NSSM Service

**Architecture:**

```
Windows PC
├── Abby running as NSSM service
├── MongoDB on localhost:27017
├── Storage on C:\path\to\abby\storage
└── Environment from C:\path\to\abby\.env
```

**Problems:**

1. **Single Point of Failure:** Abby only runs on one Windows machine
2. **No Service Isolation:** All services share same environment
3. **Manual Deployment:** Copy files, restart service, hope it works
4. **Path Hardcoding:** Windows paths (`C:\`, backslashes) not portable
5. **No Version Control:** Can't roll back to previous working version
6. **Resource Conflicts:** MongoDB port conflicts with other apps
7. **Dependency Hell:** System-wide Python packages can conflict
8. **No Health Checks:** Service might be "running" but not functional
9. **Hard to Scale:** Can't easily add more instances or services
10. **Environment Confusion:** `.env` might be stale or wrong version

**Deployment Process:**

```
1. RDP to Windows machine
2. Stop NSSM service
3. Copy new code files
4. Update .env if needed
5. Restart NSSM service
6. Check logs manually
7. Hope it works
```

---

### After: Docker Compose on Linux

**Architecture:**

```
TSERVER (Ubuntu Linux)
├── Docker Compose orchestrating:
│   ├── Abby container (isolated environment)
│   ├── MongoDB container (shared database service)
│   ├── Docker Registry (private image storage)
│   ├── CoreDNS (internal service discovery)
│   └── Caddy (reverse proxy)
├── Persistent volumes on host
└── Environment from mounted config file
```

**Benefits:**

1. **Portable:** Runs anywhere Docker runs (Linux, Windows, Mac, cloud)
2. **Isolated:** Each service in own container with own dependencies
3. **Reproducible:** Same image produces same behavior everywhere
4. **Version Control:** Tag images, roll back to any previous version
5. **Health Checks:** Docker monitors service health, auto-restarts failures
6. **Service Discovery:** Services find each other by name (mongo, registry, etc.)
7. **Resource Management:** Set CPU/memory limits per container
8. **Easy Scaling:** Add more instances with one command
9. **Clean Environment:** No system pollution, fresh environment each build
10. **Infrastructure as Code:** `docker-compose.yml` defines entire stack

**Deployment Process:**

```
1. From dev machine (Windows):
   .\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"

2. SSH to TSERVER:
   cd /srv/tserver/compose
   docker compose pull abby
   docker compose up -d abby

3. Verify:
   docker compose logs abby --tail 50

Total time: ~2 minutes (with cached builds)
```

---

### Why Docker Makes Abby Better

#### 1. **Path Portability**

**Before:** `C:\Users\user\abby\storage\file.txt`  
**After:** `/data/storage/file.txt` (mapped to host via volume)

Code no longer needs to know OS-specific paths. Container always sees `/data/`, host manages actual location.

#### 2. **Dependency Isolation**

**Before:** System-wide Python packages, conflicts with other projects  
**After:** Each container has own Python environment, no conflicts possible

#### 3. **Environment Management**

**Before:** `.env` file might be stale, forgotten to update, lost during copy  
**After:** Mounted from host, hot-reloadable, version controlled separately

#### 4. **Database Connection**

**Before:** `localhost:27017` (assumes MongoDB on same machine)  
**After:** `mongo:27017` (Docker service name, works in any environment)

#### 5. **Fast Iterations**

**Before:** 5-10 minutes to deploy code change (copy files, restart service)  
**After:** ~30 seconds (rebuild with cache, push to registry, pull and restart)

#### 6. **Disaster Recovery**

**Before:** Machine dies → reinstall Windows, reinstall MongoDB, reinstall Python, reconfigure everything  
**After:** Machine dies → new machine, `docker compose up -d`, done in 5 minutes

---

## Problems Encountered & Solutions

### Problem 1: Environment Variables Not Loading from Mounted File

**Symptom:**

```
pymongo.errors.OperationFailure: Authentication failed
```

**Root Cause:**

- Docker build copied `.env` into image at build time
- Container was loading baked `.env` from build context (old MongoDB credentials)
- Mounted `/srv/tserver/compose/abby.env` was never read
- `load_dotenv()` in `mongodb.py` had no arguments, defaulted to current directory `.env`

**Investigation:**

```bash
# Checked what env file was being loaded
docker exec abby ls -la /app/.env            # Found baked .env from build
docker exec abby cat /srv/tserver/compose/abby.env  # Confirmed mount existed
docker exec abby printenv MONGODB_URI        # Showed old value from baked .env
```

**Solution:**
Updated [launch.py](c:\TDOS\apps\abby_bot\launch.py#L1-L21) to explicitly load production env file first:

```python
env_file_prod = "/srv/tserver/compose/abby.env"
env_file_dev = ABBY_ROOT / ".env"
if os.path.exists(env_file_prod):
    load_dotenv(env_file_prod)
elif os.path.exists(env_file_dev):
    load_dotenv(env_file_dev)
```

**Lesson Learned:**

- Never rely on default `load_dotenv()` behavior in containers
- Always specify explicit paths for production environments
- Baked `.env` files in Docker images are a footgun
- Use `.dockerignore` to exclude `.env` from build context (optional)

**Time to Resolve:** ~2 hours (identifying that env was the issue, not MongoDB config)

---

### Problem 2: MongoDB Authentication Blocking Deployment

**Symptom:**

```
pymongo.errors.OperationFailure: Authentication failed.
{'ok': 0.0, 'errmsg': 'Authentication failed.', 'code': 18, 'codeName': 'AuthenticationFailed'}
```

**Root Cause:**

- Attempted to use MongoDB with authentication enabled
- Init script (`mongo-init-users.js`) to create `abby` user never executed
- Init scripts only run on **first container startup with empty data directory**
- MongoDB already had data from previous runs → init script skipped
- Manual user creation via `mongosh` failed due to:
  - Heredoc output truncation in SSH command chains
  - Quoting/escaping issues in bash→mongosh pipeline
  - No Python available in mongo container for scripting alternative

**Attempted Solutions (ALL FAILED):**

1. **Heredoc mongosh commands:**

```bash
ssh tserver 'docker exec -i mongo mongosh <<EOF
use admin
db.createUser({user:"abby", pwd:"password", roles:[{role:"readWrite",db:"abby"}]})
EOF'
# Result: Output truncated, command never actually executed
```

2. **Python script in container:**

```bash
docker exec mongo python3 /tmp/create_user.py
# Result: Python not installed in mongo:7.0 image
```

3. **Direct mongosh with escaped quotes:**

```bash
docker exec mongo mongosh --eval "db.createUser({...})"
# Result: Syntax errors, quote escaping hell
```

4. **Trying to re-run init script:**

```bash
docker exec mongo mongosh /docker-entrypoint-initdb.d/mongo-init-users.js
# Result: Script ran but database already existed, no effect
```

**Final Solution:**
**Disable MongoDB authentication entirely.**

**Rationale:**

- MongoDB only accessible from `tserver_net` Docker bridge network
- No external exposure (port 27017 not published to host)
- All containers on network are trusted TDOS services
- Authentication adds deployment complexity without security benefit
- Network isolation provides sufficient security

**Changes Made:**

1. **docker-compose.yml** - Removed auth environment variables:

```yaml
mongo:
  image: mongo:7.0
  environment:
    TZ: UTC
    # REMOVED: MONGO_INITDB_ROOT_USERNAME
    # REMOVED: MONGO_INITDB_ROOT_PASSWORD
  volumes:
    - /srv/tserver/state/mongo/data:/data/db
    - /srv/tserver/state/mongo/configdb:/data/configdb
    # REMOVED: ./mongo-init-users.js mount
```

2. **abby.env** - Simplified MongoDB URI:

```bash
# Before:
MONGODB_URI=mongodb://abby:abby_password@mongo:27017/abby?authSource=admin

# After:
MONGODB_URI=mongodb://mongo:27017/abby
```

3. **Restart MongoDB fresh:**

```bash
cd /srv/tserver/compose
docker compose down mongo
docker compose up -d mongo
```

**Result:** ✅ Abby connected immediately, no authentication errors

**Lesson Learned:**

- MongoDB init scripts are one-time only (first startup with empty data)
- Can't add users to existing authenticated MongoDB via init scripts
- Complex command chains through SSH are fragile (heredoc truncation, quoting issues)
- **Container network isolation is sufficient security for internal services**
- Simpler solutions (no auth) are often better than complex solutions (auth with manual setup)

**Time to Resolve:** ~4 hours (multiple failed mongosh attempts, debugging init scripts)

---

### Problem 3: Docker Registry Not Reachable

**Symptom:**

```powershell
docker push 100.86.240.84:5000/abby:latest
# Error: connection refused
```

**Root Cause:**

- Registry container running but port 5000 not exposed to host
- Docker daemon configured for HTTPS, but registry using HTTP
- Windows dev machine didn't have `insecure-registries` configured

**Solution:**

1. **Expose registry port in docker-compose.yml:**

```yaml
registry:
  image: registry:2
  ports:
    - "5000:5000" # Added this line
```

2. **Configure insecure registry on BOTH machines:**

**Windows (dev machine):** `C:\ProgramData\docker\config\daemon.json`

```json
{
  "insecure-registries": ["registry.tdos.internal:5000", "100.86.240.84:5000"]
}
```

Restart Docker Desktop.

**Linux (TSERVER):** `/etc/docker/daemon.json`

```json
{
  "insecure-registries": ["registry.tdos.internal:5000", "100.86.240.84:5000"]
}
```

```bash
sudo systemctl restart docker
```

3. **Use IP address for push, hostname for pull:**

```powershell
# From dev machine (Windows)
docker build -t 100.86.240.84:5000/abby:latest .
docker push 100.86.240.84:5000/abby:latest

# On TSERVER (in docker-compose.yml)
image: registry.tdos.internal:5000/abby:latest
```

**Why This Works:**

- Direct IP bypass DNS resolution issues during push
- Hostname works on TSERVER because CoreDNS resolves it locally
- Insecure registry allows HTTP instead of requiring HTTPS/TLS

**Lesson Learned:**

- Registry needs port exposed to be accessible from other machines
- Both client and server need `insecure-registries` configuration
- Use IP for pushing (from external), hostname for pulling (internal)

**Time to Resolve:** ~1 hour (testing connectivity, updating configs)

---

### Problem 4: Compilation Failures in Docker Build

**Symptom:**

```
Building wheel for hnswlib (pyproject.toml): finished with status 'error'
error: subprocess-exited-with-error
× Building wheel for hnswlib (pyproject.toml) did not run successfully.
```

**Root Cause:**

- `python:3.12-slim` base image doesn't include C++ compiler
- Dependencies like `hnswlib`, `torch` require compilation
- `requirements.txt` included `audioop-lts==0.2.1` (Python 3.13+ only)

**Solution:**

1. **Remove incompatible package from requirements.txt:**

```bash
# Removed:
audioop-lts==0.2.1
```

2. **Add build tools to Dockerfile builder stage:**

```dockerfile
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y \
    build-essential \   # C compiler
    g++ \               # C++ compiler
    ca-certificates     # SSL certificates
```

**Result:** ✅ All dependencies compiled successfully

**Lesson Learned:**

- Always include `build-essential` and `g++` in builder stage for Python projects with native extensions
- Check package compatibility with Python version
- Multi-stage builds keep final image small despite build tools

**Time to Resolve:** ~30 minutes (identifying missing packages, updating Dockerfile)

---

### Problem 5: CoreDNS Health Check Failing

**Symptom:**

```
coredns    | [ERROR] plugin/loop: Loop (127.0.0.1:37872 -> :53) detected for zone ".", see https://coredns.io/plugins/loop#troubleshooting. Query: "HINFO 4547991504243258144.3688648895315093531."
```

**Root Cause:**

- CoreDNS initially configured to forward to Tailscale virtual interface (`100.100.100.100`)
- Tailscale interface not accessible from container
- Created infinite loop trying to resolve DNS queries

**Solution:**
Updated [Corefile](c:\TDOS\apps\abby_bot\docker\coredns\Corefile) to use public DNS:

```
.:53 {
    forward . 1.1.1.1 8.8.8.8  # Cloudflare + Google
    log
    errors
}
```

**Lesson Learned:**

- Container networking has different routing than host
- Always use public DNS servers for forwarding in containers
- Test DNS resolution from within container: `docker exec coredns nslookup google.com`

**Time to Resolve:** ~30 minutes (researching loop error, updating Corefile)

---

## Local Development Workflow

This section covers how to develop Abby locally on Windows while respecting the Docker architecture. The key principle is: **develop locally with Docker Compose that mirrors production, test fully before pushing to registry.**

### Why Local Docker Development Matters

**The Problem with Direct TSERVER Deployment:**

```
Old workflow:
1. Make code change
2. .\docker\docker-build-push.ps1
3. SSH to TSERVER and restart
4. Logs show error → repeat

Issues:
- 5-10 minutes per iteration
- Production breakage affects users
- Can't test infrastructure changes locally
- Hard to debug without seeing build process
```

**Better Workflow:**

```
New workflow:
1. Make code change
2. docker compose up (local dev environment)
3. Test locally in container
4. All working? Run build-push script
5. Deploy to TSERVER with confidence

Benefits:
- 30 seconds per iteration locally
- Test infrastructure changes before production
- See real build output and errors
- Deploy only tested, working code
```

### Setting Up Local Dev Environment

#### Step 1: Create Local Docker Compose File

Create `c:\TDOS\apps\abby_bot\docker\docker-compose.dev.yml`:

```yaml
version: "3.8"

services:
  # MongoDB for local development
  mongo:
    image: mongo:7.0
    container_name: abby-dev-mongo
    restart: unless-stopped
    environment:
      TZ: UTC
    volumes:
      # Store data in local directory (survives container restart)
      - ./dev-state/mongo/data:/data/db
      - ./dev-state/mongo/configdb:/data/configdb
    ports:
      - "27017:27017" # Expose to Windows host for direct debugging
    networks:
      - abby_dev_net
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
      interval: 10s
      timeout: 5s
      retries: 5

  # Abby Discord bot (local build, local config)
  abby:
    build:
      context: ../../ # Path to c:\TDOS\apps\abby_bot
      dockerfile: Dockerfile
    container_name: abby-dev
    restart: unless-stopped
    environment:
      # DEV MODE - Load from local .env
      - MONGODB_URI=mongodb://mongo:27017/abby
      - MONGODB_DB=abby
      - STORAGE_PATH=/data/storage
      - LOG_PATH=/data/logs
      - CHROMA_PERSIST_DIR=/data/chroma
      - EVENT_LOG_DIR=/data/events
      # DEV specific settings
      - DEV_MODE=true
      - LOG_LEVEL=DEBUG # More verbose logging for development
    volumes:
      # Mount code for hot reload (if applicable)
      - ../../:/app
      - ./dev-state/abby/storage:/data/storage
      - ./dev-state/abby/logs:/data/logs
      - ./dev-state/abby/chroma:/data/chroma
      - ./dev-state/abby/events:/data/events
      # Mount .env from current directory
      - ./.env.dev:/app/.env
    ports:
      - "5000:5000" # If Abby exposes any web ports
    networks:
      - abby_dev_net
    depends_on:
      mongo:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import discord; print('ok')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  abby_dev_net:
    driver: bridge
```

#### Step 2: Create Development Environment File

Create `c:\TDOS\apps\abby_bot\docker\.env.dev`:

```bash
# ========== Development Environment Configuration ==========
# This file is for LOCAL development only
# For production, use /srv/tserver/compose/abby.env on TSERVER

# ========== Database Configuration ==========
MONGODB_URI=mongodb://mongo:27017/abby
MONGODB_DB=abby

# ========== Storage Configuration ==========
STORAGE_PATH=/data/storage
LOG_PATH=/data/logs
CHROMA_PERSIST_DIR=/data/chroma
EVENT_LOG_DIR=/data/events

# ========== Development Settings ==========
DEV_MODE=true
LOG_LEVEL=DEBUG

# ========== Discord Configuration ==========
DISCORD_TOKEN=<your-test-bot-token>
# Use a TEST Discord server for development, not production
GUILD_IDS=123456789,987654321  # Dev guild IDs

# ========== LLM Configuration ==========
OPENAI_API_KEY=<your-dev-key>
OLLAMA_HOST=http://ollama-host:11434
OLLAMA_MODEL=llama2
USE_OPENAI_FALLBACK=true

# ========== Optional Services ==========
# Point to dev/test versions during development
# STABILITY_API_KEY=<dev-key>
# IMAGE_GEN_ENABLED=false  # Disable if testing
```

**Important:** Add `.env.dev` to `.gitignore` (don't commit secrets):

```
# In c:\TDOS\apps\abby_bot\.gitignore
docker/.env.dev
docker/dev-state/
```

#### Step 3: Create Dev State Directory Structure

```powershell
cd c:\TDOS\apps\abby_bot\docker

# Create local state directories (these persist between restarts)
mkdir -p dev-state/mongo/data
mkdir -p dev-state/mongo/configdb
mkdir -p dev-state/abby/storage
mkdir -p dev-state/abby/logs
mkdir -p dev-state/abby/chroma
mkdir -p dev-state/abby/events
```

**Why This Structure:**

- `/dev-state/` mirrors `/srv/tserver/state/` on TSERVER
- Data persists on Windows disk (not in Docker volumes)
- Easy to backup/clean: just delete `dev-state/` folder
- Logs visible at `c:\TDOS\apps\abby_bot\docker\dev-state\abby\logs\`

### Local Development Workflow

#### Daily Development Loop

**1. Start local environment:**

```powershell
cd c:\TDOS\apps\abby_bot\docker
docker compose -f docker-compose.dev.yml up
```

**What This Does:**

```
1. Builds Abby image from local Dockerfile
2. Starts MongoDB container
3. Waits for MongoDB health check
4. Starts Abby container
5. Streams logs to console
```

**Output Should Show:**

```
mongo-dev     | [OK] Listening on 0.0.0.0:27017
abby-dev      | [→] Loading environment from /app/.env
abby-dev      | [→] Connecting to MongoDB...
abby-dev      | [✓] MongoDB connected (local dev mode)
abby-dev      | [→] Initializing collections...
abby-dev      | [✓] All 37 collections initialized
abby-dev      | [→] Loading cogs...
abby-dev      | [✓] 33 cogs loaded successfully
abby-dev      | [→] Connecting to Discord...
abby-dev      | [✓] Connected to Discord Gateway
```

**2. Test your changes:**

- Make code edits locally
- If using hot reload (code mounted in container), changes take effect immediately
- Check logs: `docker compose -f docker-compose.dev.yml logs -f abby`
- Test Discord commands in your test server

**3. Iterating on Code:**

**For Python code changes (with hot reload):**

```
1. Edit c:\TDOS\apps\abby_bot\abby_core\...
2. Container sees changes immediately (via volume mount)
3. If cog needs reload: `/reload <cog_name>` in Discord
4. If app needs restart: Ctrl+C and `docker compose up` again
```

**For Dockerfile or requirements.txt changes:**

```
1. Edit Dockerfile or requirements.txt
2. Stop containers: docker compose -f docker-compose.dev.yml down
3. Rebuild: docker compose -f docker-compose.dev.yml up --build
4. Takes 30 seconds with cache, or 5-10 minutes for new dependencies
```

**For Environment Changes:**

```
1. Edit docker/.env.dev
2. Stop containers: docker compose -f docker-compose.dev.yml down
3. Start fresh: docker compose -f docker-compose.dev.yml up
```

**4. Verify Everything Works:**

```powershell
# Check all services are healthy
docker compose -f docker-compose.dev.yml ps
# Should show STATUS: Up X minutes (healthy)

# Check MongoDB
docker compose -f docker-compose.dev.yml exec mongo mongosh localhost:27017/abby --quiet --eval "db.stats()"

# Check logs for errors
docker compose -f docker-compose.dev.yml logs abby --tail 100

# Test in Discord (make a command call, check response)
```

**5. When Ready to Deploy to TSERVER:**

```powershell
# Stop local environment (don't delete volumes yet)
docker compose -f docker-compose.dev.yml down

# Build and push to TSERVER registry
.\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"

# Deploy on TSERVER
ssh tserver 'cd /srv/tserver/compose && docker compose pull abby && docker compose up -d abby'

# Verify on TSERVER
ssh tserver 'cd /srv/tserver/compose && docker compose logs abby --tail 50'
```

### Advanced Local Development Scenarios

#### Scenario: Testing Infrastructure Changes

**You want to test MongoDB upgrade before production:**

```yaml
# In docker-compose.dev.yml
mongo:
  image: mongo:8.0 # Try new version locally first
  # ... rest of config
```

**Steps:**

```powershell
# 1. Delete old data to test fresh upgrade
rm -r docker/dev-state/mongo/data/*

# 2. Start with new MongoDB version
docker compose -f docker-compose.dev.yml up --build

# 3. Verify Abby connects without errors
docker compose -f docker-compose.dev.yml logs abby | Select-String "MongoDB connected"

# 4. Test for 30 minutes (data integrity, query performance)

# 5. If all good, update production docker-compose.yml:
# Change TSERVER: mongo: image: mongo:8.0

# 6. Deploy to TSERVER with backup first
```

#### Scenario: Testing New Service (Redis Cache)

**Add Redis to local compose first:**

```yaml
# In docker-compose.dev.yml
redis:
  image: redis:7-alpine
  container_name: abby-dev-redis
  ports:
    - "6379:6379"
  networks:
    - abby_dev_net

# Update abby service:
abby:
  environment:
    - REDIS_URL=redis://redis:6379/0
  depends_on:
    mongo:
      condition: service_healthy
    redis: # Add this
      condition: service_started
```

**Steps:**

```powershell
# 1. Test locally
docker compose -f docker-compose.dev.yml up --build

# 2. Update Abby code to use Redis
# Edit abby_core/cache.py to connect to REDIS_URL

# 3. Test functionality
docker compose -f docker-compose.dev.yml logs abby

# 4. Once working, add Redis to production docker-compose.yml:
# Copy redis service definition to /srv/tserver/compose/docker-compose.yml

# 5. Deploy
.\docker-build-push.ps1
ssh tserver 'cd /srv/tserver/compose && docker compose up -d redis && docker compose pull abby && docker compose up -d abby'
```

#### Scenario: Debugging Database Issues

**Direct access to local MongoDB:**

```powershell
# 1. Open MongoDB shell directly from Windows (if mongosh installed)
mongosh mongodb://localhost:27017/abby

# 2. Or from inside container
docker compose -f docker-compose.dev.yml exec mongo mongosh localhost:27017/abby

# 3. Run queries to debug
db.users.find()
db.users.countDocuments()
db.collections.getCollectionNames()

# 4. See what's actually in local database
db.guilds.findOne()
```

**Persistent Data:**

- Data in `docker/dev-state/mongo/data/` survives container restart
- To start fresh: `rm -r docker/dev-state/mongo/data/*`
- To backup before experimenting: `Copy-Item -Recurse docker/dev-state/mongo/data docker/dev-state/mongo/data.backup`

### Bridging Local Dev to TSERVER Registry

**The Key Insight: Same Image, Different Contexts**

```
┌─ Development ────────────────┬─ Production on TSERVER ──────────────┐
│                              │                                      │
│ docker-compose.dev.yml:      │ docker-compose.yml:                 │
│ - build: Dockerfile          │ - image: registry:5000/abby:latest  │
│ - local code mount           │ - pull from registry                │
│ - .env.dev                   │ - /srv/tserver/compose/abby.env    │
│ - dev-state/ volumes         │ - /srv/tserver/state/ volumes      │
│                              │                                      │
│ ITERATION: 30 seconds        │ DEPLOYMENT: pull + restart          │
│ SCOPE: Just Abby             │ SCOPE: All services (mongo, etc)    │
└──────────────────────────────┴──────────────────────────────────────┘

Flow: Local Docker Compose → Test → Build & Push → Production Docker Compose
```

**The Build/Push Process:**

```powershell
# .\docker\docker-build-push.ps1 does:

1. Build Abby image from Dockerfile
   - Uses same Dockerfile as local dev
   - Result: one consistent image

2. Tag with registry hostname
   - 100.86.240.84:5000/abby:latest  (for push)
   - registry.tdos.internal:5000/abby:latest  (for pull)

3. Push to TSERVER registry
   - Image now available to all TSERVER services

4. TSERVER docker-compose.yml pulls the same image
   - Identical application behavior (same build)
   - Different configuration (production env file)
```

**Why This Architecture:**

- ✅ **Consistency:** Dev and prod use same image build
- ✅ **Confidence:** What works locally works in production
- ✅ **Speed:** Registry caches layers, push/pull fast
- ✅ **Control:** You control when code ships to production
- ✅ **Rollback:** Old images stay in registry, easy to rollback

### Tips & Tricks for Local Development

**1. Fast Iteration with Code Mounts:**

```yaml
# In docker-compose.dev.yml
volumes:
  - ../../:/app # Mount entire source directory
```

**Pro:** Python changes take effect immediately (if no bytecode cache)  
**Con:** Requires container has file watching enabled, only works for interpreted code

**2. Conditional Debug Logging:**

```python
# In launch.py
import logging
import os

DEBUG_MODE = os.getenv("LOG_LEVEL") == "DEBUG"
logger = logging.getLogger(__name__)

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.debug(f"Loading env from: {env_file}")
```

**Benefit:** Turn on verbose logs locally, off in production

**3. Using Compose Override Files:**

Instead of separate files, use override pattern:

```yaml
# docker-compose.yml (production, committed to git)
services:
  abby:
    image: registry.tdos.internal:5000/abby:latest

# docker-compose.override.yml (local, .gitignored)
services:
  abby:
    build: .
    image: abby:dev
    environment:
      - LOG_LEVEL=DEBUG
    volumes:
      - .:/app
```

**Then just run:**

```powershell
docker compose up  # Automatically uses override
```

**4. Health Check Wait Optimization:**

```yaml
# Add to Abby service in dev compose
environment:
  - WAIT_FOR_MONGO=true
  - MONGO_CONNECTION_RETRY=5
  - MONGO_CONNECTION_DELAY=2
```

This lets app retry connection to MongoDB if it's still starting.

**5. View Real-Time Resource Usage:**

```powershell
docker stats --no-stream

# Output shows CPU%, memory, network I/O for each container
```

### Local vs Production Environment Variables

**Key Differences:**

| Setting          | Local Dev                                         | Production                                          |
| ---------------- | ------------------------------------------------- | --------------------------------------------------- |
| `MONGODB_URI`    | `mongodb://mongo:27017`                           | `mongodb://mongo:27017` (same, Docker network)      |
| `STORAGE_PATH`   | `/data/storage` → `docker/dev-state/abby/storage` | `/data/storage` → `/srv/tserver/state/abby/storage` |
| `LOG_LEVEL`      | `DEBUG`                                           | `INFO`                                              |
| `DISCORD_TOKEN`  | Test bot token                                    | Production bot token                                |
| `GUILD_IDS`      | Test guilds only                                  | Production guilds                                   |
| `OPENAI_API_KEY` | Dev key (limited quota)                           | Prod key (full quota)                               |
| `DEV_MODE`       | `true`                                            | `false` or unset                                    |

**Never Copy Dev .env to Production:**

```bash
# WRONG - will break production:
cp docker/.env.dev /srv/tserver/compose/abby.env

# RIGHT - use separate production config:
# /srv/tserver/compose/abby.env (maintained separately, with secrets)
```

---

### Starting Services

**Start all services:**

```bash
ssh tserver
cd /srv/tserver/compose
docker compose up -d
```

**Start specific service:**

```bash
docker compose up -d abby      # Just Abby
docker compose up -d mongo     # Just MongoDB
```

**View service status:**

```bash
docker compose ps
```

**Expected output:**

```
NAME       IMAGE                                      STATUS
abby       registry.tdos.internal:5000/abby:latest   Up 2 minutes (healthy)
mongo      mongo:7.0                                  Up 2 minutes (healthy)
coredns    coredns/coredns:1.11.1                    Up 2 minutes (healthy)
registry   registry:2                                 Up 2 minutes (healthy)
caddy      caddy:2.8.4-alpine                        Up 2 minutes (healthy)
tdos-docs  registry.tdos.internal:5000/docs:latest   Up 2 minutes (healthy)
```

---

### Stopping Services

**Stop all services:**

```bash
docker compose down
```

**Stop specific service (keep others running):**

```bash
docker compose stop abby
```

**Stop and remove volumes (DESTRUCTIVE - deletes data):**

```bash
docker compose down -v  # ⚠️ WARNING: Deletes all database and storage data
```

---

### Viewing Logs

**View logs for all services:**

```bash
docker compose logs
```

**Follow logs in real-time:**

```bash
docker compose logs -f abby
```

**View last 50 lines:**

```bash
docker compose logs abby --tail 50
```

**View logs for specific time range:**

```bash
docker compose logs --since 1h abby    # Last hour
docker compose logs --since 2024-02-08T10:00:00 abby
```

---

### Deploying Code Updates

#### From Dev Machine (Windows)

**1. Build and push new image:**

```powershell
cd C:\TDOS\apps\abby_bot
.\docker\docker-build-push.ps1 -RegistryHost "registry.tdos.internal"
```

Script will:

- Test registry connectivity
- Build Docker image with multi-stage caching
- Tag image as `100.86.240.84:5000/abby:latest`
- Push to internal registry
- Report success/failure

**Expected output:**

```
[✓] Registry connectivity test passed
[→] Building Docker image...
[✓] Build completed in 32.45 seconds
[→] Pushing to registry...
[✓] Push completed in 8.12 seconds
[✓] Deployment package ready on TSERVER
```

**2. Deploy on TSERVER:**

```bash
ssh tserver 'cd /srv/tserver/compose && docker compose pull abby && docker compose up -d abby'
```

**3. Verify deployment:**

```bash
ssh tserver 'cd /srv/tserver/compose && docker compose logs abby --tail 50'
```

Look for:

```
[✓] System operational - 33 cogs, 27 commands
[💚] Health: MongoDB: OK | Storage: OK | Image Gen: OK | Scheduler: OK
[🔗] Ready to serve 4 guild(s)
```

**Total time:** ~2-3 minutes (with cached builds)

---

### Updating Environment Configuration

**1. Edit production env file:**

```bash
ssh tserver
nano /srv/tserver/compose/abby.env
```

**2. Restart Abby to load new config:**

```bash
cd /srv/tserver/compose
docker compose restart abby
```

**3. Verify new settings loaded:**

```bash
docker compose logs abby --tail 20
```

**Note:** No need to rebuild image for env changes, just restart container.

---

### Health Checks

**Check all service health:**

```bash
docker compose ps
```

**Individual health checks:**

```bash
# MongoDB
docker exec mongo mongosh localhost:27017/test --quiet --eval "db.runCommand('ping')"

# Registry
curl http://100.86.240.84:5000/v2/_catalog

# CoreDNS
dig @100.86.240.84 registry.tdos.internal

# Abby (check bot status in Discord)
# Or check logs for "[💚] Health: MongoDB: OK | Storage: OK"
```

---

### Monitoring

**Resource usage:**

```bash
docker stats  # Live resource monitoring (CPU, memory, network, disk I/O)
```

**Disk usage:**

```bash
# Total Docker disk usage
docker system df

# Per-service disk usage
du -sh /srv/tserver/state/abby/*
du -sh /srv/tserver/state/mongo/*
```

**MongoDB database size:**

```bash
docker exec mongo mongosh localhost:27017/abby --quiet --eval "db.stats()"
```

---

### Backup Procedures

**MongoDB Backup:**

```bash
# Dump database to file
docker exec mongo mongosh localhost:27017/abby --quiet --eval "db.fsyncLock()"
sudo tar -czf /srv/tserver/backups/mongo-$(date +%Y%m%d-%H%M%S).tar.gz /srv/tserver/state/mongo/data
docker exec mongo mongosh localhost:27017/abby --quiet --eval "db.fsyncUnlock()"
```

**Abby Data Backup:**

```bash
sudo tar -czf /srv/tserver/backups/abby-$(date +%Y%m%d-%H%M%S).tar.gz /srv/tserver/state/abby
```

**Full System Backup:**

```bash
cd /srv/tserver
sudo tar -czf /srv/tserver/backups/full-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  compose/ \
  state/
```

**Registry Backup (all images):**

```bash
sudo tar -czf /srv/tserver/backups/registry-$(date +%Y%m%d-%H%M%S).tar.gz /srv/tserver/state/registry
```

---

## SOP Updates Required

### 1. Service Onboarding SOP

**Add to `service_onboarding.md`:**

**New Section: "Deploying Containerized Services"**

Prerequisites:

- Docker and Docker Compose installed on TSERVER
- Internal Docker Registry operational (`registry.tdos.internal:5000`)
- CoreDNS operational for service discovery
- Shared MongoDB available (if application needs database)

Service Requirements:

1. Dockerfile with multi-stage build (builder + runtime)
2. docker-compose.yml service definition
3. Environment file template (`.env.example` or similar)
4. Health check endpoint or command
5. Build/deploy automation script

Deployment Checklist:

- [ ] Create Dockerfile with proper base image
- [ ] Add service to `/srv/tserver/compose/docker-compose.yml`
- [ ] Create environment file in `/srv/tserver/compose/<service>.env`
- [ ] Create persistent volume directory: `/srv/tserver/state/<service>`
- [ ] Configure health check (HTTP endpoint or command)
- [ ] Add to `tserver_net` Docker network
- [ ] Configure `depends_on` for service dependencies
- [ ] Test build locally before pushing to registry
- [ ] Tag and push image to `registry.tdos.internal:5000/<service>:latest`
- [ ] Deploy with `docker compose up -d <service>`
- [ ] Verify health check passes
- [ ] Check logs for errors: `docker compose logs <service>`
- [ ] Add monitoring/alerting (if applicable)

---

### 2. TSERVER Infrastructure SOP

**Add new section: "Infrastructure Services"**

**CoreDNS (Internal DNS):**

- Location: `/srv/tserver/compose/coredns/`
- Port: 53 (TCP/UDP)
- Configuration: `Corefile`, `tdos.internal.db`
- Restart: `docker compose restart coredns`
- Testing: `dig @100.86.240.84 registry.tdos.internal`
- Logs: `docker compose logs coredns`

**Docker Registry:**

- Location: `/srv/tserver/state/registry`
- URL: `registry.tdos.internal:5000` (HTTP only, insecure)
- Configuration: `docker-compose.yml` registry service
- List images: `curl http://100.86.240.84:5000/v2/_catalog`
- Delete image: `curl -X DELETE http://100.86.240.84:5000/v2/<name>/manifests/<tag>`
- Restart: `docker compose restart registry`

**MongoDB (Shared Database):**

- Location: `/srv/tserver/state/mongo/`
- Port: 27017 (internal only)
- Authentication: DISABLED (network isolation provides security)
- Connection: `mongodb://mongo:27017/<database_name>`
- Shell Access: `docker exec -it mongo mongosh`
- Restart: `docker compose restart mongo`
- Backup: See [Backup Procedures](#backup-procedures)

**Important:** All services use `tserver_net` Docker bridge network for internal communication. Only Caddy exposes public ports (80, 443).

---

### 3. Abby Bot Operations SOP

**Add new section: "Abby Discord Bot (Docker Deployment)"**

**Service Location:**

- Image: `registry.tdos.internal:5000/abby:latest`
- Container: `abby` on TSERVER
- Config: `/srv/tserver/compose/abby.env`
- Data: `/srv/tserver/state/abby/` (storage, logs, chroma, events)

**Starting/Stopping:**

```bash
ssh tserver
cd /srv/tserver/compose

# Start
docker compose up -d abby

# Stop
docker compose stop abby

# Restart
docker compose restart abby

# View logs
docker compose logs -f abby
```

**Deploying Updates:**

1. From dev machine: `.\docker\docker-build-push.ps1`
2. On TSERVER: `docker compose pull abby && docker compose up -d abby`
3. Verify: `docker compose logs abby --tail 50`

**Environment Configuration:**

- File: `/srv/tserver/compose/abby.env`
- After changes: `docker compose restart abby`
- No image rebuild needed for env changes

**Health Check Indicators:**

```
[✓] System operational - 33 cogs, 27 commands
[💚] Health: MongoDB: OK | Storage: OK | Image Gen: OK | Scheduler: OK
```

**Common Issues:**

- Bot not connecting: Check Discord token in `abby.env`
- Database errors: Verify MongoDB is healthy (`docker compose ps mongo`)
- Missing data: Check `/srv/tserver/state/abby/` permissions
- Slow startup: Normal, DB initialization takes ~20 seconds

**Logs Location:**

- Container logs: `docker compose logs abby`
- Application logs: `/srv/tserver/state/abby/logs/`

---

### 4. Disaster Recovery SOP

**Add section: "Docker Infrastructure Recovery"**

**Scenario 1: TSERVER Complete Failure**

Recovery Steps:

1. Provision new Ubuntu 24.04 LTS server
2. Install Docker and Docker Compose
3. Configure Tailscale and join tailnet
4. Restore `/srv/tserver/` from backup:
   ```bash
   sudo tar -xzf full-backup-YYYYMMDD-HHMMSS.tar.gz -C /
   ```
5. Start all services:
   ```bash
   cd /srv/tserver/compose
   docker compose up -d
   ```
6. Verify health checks:
   ```bash
   docker compose ps
   ```

**Scenario 2: Abby Container Failure**

Recovery Steps:

1. Check logs: `docker compose logs abby --tail 100`
2. Restart container: `docker compose restart abby`
3. If restart fails, pull fresh image:
   ```bash
   docker compose pull abby
   docker compose up -d abby
   ```
4. If still failing, restore from backup:
   ```bash
   sudo tar -xzf abby-YYYYMMDD-HHMMSS.tar.gz -C /
   docker compose restart abby
   ```

**Scenario 3: MongoDB Data Corruption**

Recovery Steps:

1. Stop all services using MongoDB:
   ```bash
   docker compose stop abby
   ```
2. Stop MongoDB:
   ```bash
   docker compose stop mongo
   ```
3. Restore from backup:
   ```bash
   sudo rm -rf /srv/tserver/state/mongo/data/*
   sudo tar -xzf mongo-YYYYMMDD-HHMMSS.tar.gz -C /
   ```
4. Start MongoDB:
   ```bash
   docker compose up -d mongo
   ```
5. Verify health:
   ```bash
   docker exec mongo mongosh localhost:27017/test --quiet --eval "db.runCommand('ping')"
   ```
6. Start dependent services:
   ```bash
   docker compose up -d abby
   ```

**Scenario 4: Docker Registry Failure**

Recovery Steps:

1. Registry data is in `/srv/tserver/state/registry`
2. If corrupted, restore from backup:
   ```bash
   sudo rm -rf /srv/tserver/state/registry/*
   sudo tar -xzf registry-YYYYMMDD-HHMMSS.tar.gz -C /
   ```
3. Restart registry:
   ```bash
   docker compose restart registry
   ```
4. If backup not available, rebuild all images from dev machine:

   ```powershell
   cd C:\TDOS\apps\abby_bot
   .\docker\docker-build-push.ps1

   cd C:\TDOS\apps\other_service
   .\docker\docker-build-push.ps1
   ```

**Recovery Time Estimates:**

- Abby restart: ~30 seconds
- MongoDB restore: ~5-10 minutes (depending on data size)
- Full TSERVER rebuild: ~30-60 minutes (including backups restore)
- Registry rebuild: ~10-20 minutes (rebuild all images)

---

## Critical Knowledge Base

### Architecture Decisions & Rationale

#### 1. Why No MongoDB Authentication?

**Decision:** Disable MongoDB authentication entirely.

**Reasoning:**

- MongoDB only accessible from `tserver_net` Docker bridge network
- No external exposure (port 27017 not published to host)
- All containers on network are trusted TDOS services
- Authentication adds significant deployment complexity:
  - Init scripts only run on first startup with empty data
  - Manual user creation is fragile (SSH command chains, quoting issues)
  - Creates operational burden (password management, rotation)
- Network isolation provides equivalent security to authentication
- Simplifies connection strings and troubleshooting

**Trade-offs:**

- ✅ Pro: Simpler deployment, no credential management
- ✅ Pro: Easier troubleshooting (no auth errors)
- ✅ Pro: Faster connections (no auth handshake)
- ❌ Con: If container escapes happen, MongoDB is accessible
- ❌ Con: All containers on network have full database access

**When to Reconsider:**

- If untrusted containers join `tserver_net`
- If multi-tenant applications need database-level isolation
- If compliance requires authentication logs

**How to Re-enable:**

1. Stop all services using MongoDB
2. Wipe MongoDB data: `sudo rm -rf /srv/tserver/state/mongo/data/*`
3. Add to docker-compose.yml:
   ```yaml
   environment:
     MONGO_INITDB_ROOT_USERNAME: root
     MONGO_INITDB_ROOT_PASSWORD: <secure-password>
   volumes:
     - ./mongo-init-users.js:/docker-entrypoint-initdb.d/init.js:ro
   ```
4. Update connection strings in all services
5. Start MongoDB (init script will run on first startup)

---

#### 2. Why Multi-Stage Docker Builds?

**Decision:** Use multi-stage Dockerfile with builder + runtime stages.

**Reasoning:**

- Python dependencies like `hnswlib`, `torch` require C++ compilation
- Compilation tools (gcc, g++) not needed in runtime image
- Code changes shouldn't trigger full dependency rebuild
- Smaller runtime images improve pull times and security

**Benefits:**

- **First build:** ~10-15 minutes (compiles all dependencies)
- **Code-only changes:** ~30 seconds (just copies new code)
- **Runtime image size:** ~1.2GB vs ~2.5GB with build tools
- **Security:** Fewer packages in runtime = smaller attack surface

**Dockerfile Structure:**

```dockerfile
# Stage 1: Builder (has gcc/g++, builds wheels)
FROM python:3.12-slim AS builder
RUN apt-get install build-essential g++
RUN pip install -r requirements.txt

# Stage 2: Runtime (copies built packages, adds code)
FROM python:3.12-slim
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . ./
```

**When to Rebuild Builder Stage:**

- `requirements.txt` changes (new dependencies)
- Python version upgrade
- Security updates to base image

**When to Rebuild Runtime Only:**

- Code changes in `apps/abby_bot/` (most common)
- Environment variable changes (actually don't need rebuild, just restart)

---

#### 3. Why Internal Docker Registry?

**Decision:** Deploy private Docker Registry at `registry.tdos.internal:5000`.

**Reasoning:**

- **Speed:** No internet upload/download (local network only)
- **Cost:** Avoid Docker Hub rate limits (100 pulls per 6 hours for free)
- **Privacy:** TDOS images stay internal, not public on Docker Hub
- **Reliability:** Not dependent on Docker Hub uptime
- **CI/CD:** Enables automated builds and deployments on TSERVER

**Trade-offs:**

- ✅ Pro: Fast deployments (~5-10 seconds to pull)
- ✅ Pro: No external dependencies
- ✅ Pro: Full control over retention policies
- ❌ Con: Requires disk space on TSERVER (currently ~2GB for all images)
- ❌ Con: No automatic backup (need manual backup strategy)

**Insecure Registry Configuration:**
Using HTTP (not HTTPS) because:

- Internal network only (Tailscale VPN)
- No sensitive data in images (secrets in env files, not baked)
- Simpler setup (no TLS certificate management)

If external access needed, add Caddy reverse proxy with auto-HTTPS.

---

#### 4. Why CoreDNS Instead of Hosts File?

**Decision:** Deploy CoreDNS for internal DNS resolution.

**Reasoning:**

- Tailscale MagicDNS only provides base hostname (`tserver`), not subdomains
- `/etc/hosts` requires manual updates on every machine
- CoreDNS provides dynamic service discovery
- Enables future services to auto-register (via service discovery)
- Handles both internal (`*.tdos.internal`) and external (forwarded) queries

**Configuration:**

```
tdos.internal:53 {
    file /etc/coredns/tdos.internal.db
}

.:53 {
    forward . 1.1.1.1 8.8.8.8  # External queries
}
```

**Why Not Tailscale MagicDNS:**

- MagicDNS doesn't support custom domains or subdomains
- Can't create `registry.tserver` or `mongo.tserver` (only `tserver`)
- Need full control over DNS zone for service discovery

**Why Not /etc/hosts:**

- Requires manual updates on every machine (dev + TSERVER)
- No dynamic updates (if services move, need manual updates)
- Can't use from containers easily (requires host file mount)

---

### Docker Compose Dependency Management

**Understanding `depends_on`:**

```yaml
abby:
  depends_on:
    mongo:
      condition: service_healthy
```

**What This Does:**

- Waits for `mongo` container to report healthy before starting `abby`
- Uses health check defined in `mongo` service
- Prevents startup failures due to "connection refused" errors

**What This Does NOT Do:**

- Doesn't guarantee MongoDB is fully initialized (collections created, etc.)
- Doesn't retry connections if MongoDB restarts during Abby runtime

**Application-Level Retry Logic Still Needed:**
Abby has connection retry logic in `mongodb.py`:

```python
for attempt in range(max_retries):
    try:
        client = MongoClient(uri)
        client.admin.command('ping')
        break
    except Exception as e:
        time.sleep(retry_delay)
```

**Why Both Needed:**

- `depends_on` prevents early startup failures
- Application retry handles restarts and transient failures

---

### Environment Variable Precedence

**Loading Order in Abby:**

1. **Command-line arguments** (highest priority)

   ```bash
   docker run abby python launch.py --mode production
   ```

2. **Mounted env file** (production)

   ```python
   load_dotenv("/srv/tserver/compose/abby.env")  # Loaded first in launch.py
   ```

3. **Local .env file** (development)

   ```python
   load_dotenv(".env")  # Fallback if production file not found
   ```

4. **Environment variables set in docker-compose.yml**

   ```yaml
   environment:
     MONGODB_URI: mongodb://mongo:27017/abby
   ```

5. **Hardcoded defaults** (lowest priority)
   ```python
   MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/abby")
   ```

**Best Practice:**

- Use mounted env file for production (allows updates without rebuild)
- Use `docker-compose.yml` environment section for infrastructure services (mongo, redis)
- Never hardcode secrets (always use env vars)
- Document all env vars with defaults in `.env.example`

---

### Docker Networking Explained

**Network: `tserver_net`** (bridge network)

**Services on Network:**

- coredns
- mongo
- registry
- caddy
- abby
- tdos-docs

**Service Discovery:**
Each container can reach others by service name:

```
From abby container:
  mongo:27017 → MongoDB
  registry:5000 → Docker Registry
  caddy:80 → Caddy reverse proxy
```

**External Access:**

```
From dev machine:
  100.86.240.84:5000 → Registry (exposed via ports)
  100.86.240.84:80 → Caddy (exposed via ports)
  100.86.240.84:27017 → NOT ACCESSIBLE (internal only)
```

**Why MongoDB Not Exposed:**

```yaml
mongo:
  # No "ports:" section → internal only
  # Only accessible from other containers on tserver_net
```

**Why Registry IS Exposed:**

```yaml
registry:
  ports:
    - "5000:5000" # Host:Container
  # Accessible from dev machine for push/pull
```

---

### Persistent Volumes Strategy

**Host Path Mapping:**

```yaml
volumes:
  - /srv/tserver/state/abby:/data
  #  ↑ Host path             ↑ Container path
```

**Why This Works:**

1. Container sees `/data/storage`, `/data/logs`, etc.
2. Actually written to `/srv/tserver/state/abby/storage`, `/srv/tserver/state/abby/logs` on host
3. Survives container restarts, rebuilds, deletions
4. Can backup/restore from host filesystem

**Directory Structure:**

```
/srv/tserver/state/
├── abby/
│   ├── storage/       # File uploads, cached data
│   ├── logs/          # Application logs
│   ├── chroma/        # ChromaDB vector store
│   └── events/        # Event logs
├── mongo/
│   ├── data/          # MongoDB database files
│   └── configdb/      # MongoDB configuration
└── registry/          # Docker Registry images
```

**Backup Strategy:**

- Tar entire `/srv/tserver/state/` for full backup
- Per-service backups: `tar -czf abby-backup.tar.gz /srv/tserver/state/abby`
- Sync to remote storage: `rclone sync /srv/tserver/state/ remote:backups/tserver/`

**Permissions:**

- All directories owned by `root:root` (Docker runs as root)
- Application writes as container user (usually root)
- If permission errors, check with: `ls -la /srv/tserver/state/abby/`

---

### Image Tagging Strategy

**Current Strategy:**

```
100.86.240.84:5000/abby:latest
registry.tdos.internal:5000/abby:latest
```

**Why `latest` Tag:**

- Simple for single-developer projects
- Always points to most recent build
- Easy to deploy: `docker compose pull abby && docker compose up -d abby`

**Why This Might Be Problem Later:**

- Can't easily roll back to previous version
- No versioning history
- If `latest` breaks, no way to know what worked before

**Recommended Strategy for Production:**

```
registry.tdos.internal:5000/abby:1.2.3       # Semantic version
registry.tdos.internal:5000/abby:1.2         # Minor version
registry.tdos.internal:5000/abby:1           # Major version
registry.tdos.internal:5000/abby:latest      # Alias to newest
```

**How to Implement:**

```powershell
# Build with version tag
docker build -t 100.86.240.84:5000/abby:1.2.3 .
docker tag 100.86.240.84:5000/abby:1.2.3 100.86.240.84:5000/abby:latest
docker push 100.86.240.84:5000/abby:1.2.3
docker push 100.86.240.84:5000/abby:latest
```

**Rollback Process:**

```bash
# In docker-compose.yml
image: registry.tdos.internal:5000/abby:1.2.2  # Previous version

docker compose up -d abby
```

---

### Security Considerations

**Current Security Posture:**

✅ **Good:**

- Tailscale VPN isolates TSERVER from public internet
- Docker bridge network isolates containers from host
- MongoDB not exposed to host (internal only)
- Caddy handles TLS for public services
- No secrets baked into Docker images

❌ **Areas for Improvement:**

- MongoDB has no authentication (mitigated by network isolation)
- Docker Registry uses HTTP (no TLS)
- No image signing or verification
- No secrets management solution (using plain text env files)
- No container resource limits (can consume all CPU/RAM)

**Recommended Improvements:**

1. **Add Resource Limits:**

```yaml
abby:
  deploy:
    resources:
      limits:
        cpus: "2.0"
        memory: 4G
      reservations:
        cpus: "0.5"
        memory: 1G
```

2. **Use Docker Secrets for Sensitive Data:**

```yaml
abby:
  secrets:
    - discord_token
    - openai_api_key

secrets:
  discord_token:
    file: /srv/tserver/secrets/discord_token.txt
  openai_api_key:
    file: /srv/tserver/secrets/openai_api_key.txt
```

3. **Enable Registry Authentication:**

```yaml
registry:
  environment:
    REGISTRY_AUTH: htpasswd
    REGISTRY_AUTH_HTPASSWD_PATH: /auth/htpasswd
    REGISTRY_AUTH_HTPASSWD_REALM: Registry Realm
```

4. **Run Containers as Non-Root:**

```dockerfile
RUN useradd -m abby
USER abby
```

5. **Enable Read-Only Root Filesystem:**

```yaml
abby:
  read_only: true
  tmpfs:
    - /tmp
```

**Priority:**

- Resource limits: HIGH (prevents resource exhaustion)
- Secrets management: MEDIUM (current env files work but not ideal)
- Registry auth: LOW (internal network only)
- Non-root containers: LOW (complex, requires permission fixes)

---

## Maintenance Procedures

### Monthly Tasks

**1. Update Docker Images:**

```bash
ssh tserver
cd /srv/tserver/compose

# Pull latest base images
docker compose pull

# Restart services with new images
docker compose up -d

# Verify health
docker compose ps
```

**2. Clean Up Unused Images:**

```bash
docker image prune -a --filter "until=720h"  # Remove images older than 30 days
```

**3. Check Disk Usage:**

```bash
df -h /srv/tserver/state
docker system df
```

**4. Review Logs for Errors:**

```bash
docker compose logs --since 30d | grep -i error > monthly-errors.log
```

**5. Backup Critical Data:**

```bash
sudo tar -czf /srv/tserver/backups/monthly-backup-$(date +%Y%m%d).tar.gz /srv/tserver/state
```

---

### Quarterly Tasks

**1. Update Docker Compose:**

```bash
sudo apt update
sudo apt upgrade docker-compose-plugin
docker compose version
```

**2. Review Resource Usage Trends:**

```bash
# Check average CPU/memory over time
docker stats --no-stream > resource-snapshot-$(date +%Y%m%d).txt
```

**3. Test Disaster Recovery:**

- Restore from backup to test environment
- Verify all services start correctly
- Document any issues found

**4. Review and Update SOPs:**

- Update this document with lessons learned
- Add new procedures discovered
- Remove outdated information

---

### Emergency Procedures

**Service Not Starting:**

```bash
# 1. Check logs
docker compose logs <service> --tail 100

# 2. Check health
docker inspect <service> | grep -A 20 Health

# 3. Try restart
docker compose restart <service>

# 4. If still failing, recreate
docker compose up -d --force-recreate <service>

# 5. If still failing, pull fresh image
docker compose pull <service>
docker compose up -d <service>
```

**Disk Full:**

```bash
# 1. Check what's using space
du -sh /srv/tserver/state/*

# 2. Clean up old logs
find /srv/tserver/state/abby/logs -name "*.log" -mtime +30 -delete

# 3. Clean up Docker
docker system prune -a --volumes

# 4. If desperate, remove old backups
rm /srv/tserver/backups/*-202401*.tar.gz
```

**Network Issues:**

```bash
# 1. Check Docker network
docker network inspect tserver_net

# 2. Restart network stack
docker compose down
docker network rm tserver_net
docker compose up -d

# 3. Check DNS resolution
docker exec abby nslookup mongo
docker exec abby ping -c 3 mongo
```

**Database Corruption:**

```bash
# 1. Stop all services using MongoDB
docker compose stop abby

# 2. Try MongoDB repair
docker exec mongo mongosh localhost:27017/admin --eval "db.repairDatabase()"

# 3. If repair fails, restore from backup
docker compose stop mongo
sudo rm -rf /srv/tserver/state/mongo/data/*
sudo tar -xzf /srv/tserver/backups/mongo-latest.tar.gz -C /
docker compose up -d mongo

# 4. Restart dependent services
docker compose up -d abby
```

---

## Conclusion

This migration transformed Abby from a fragile Windows service to a production-grade containerized application. The new architecture provides:

✅ **Reliability:** Health checks, auto-restarts, dependency management  
✅ **Portability:** Runs anywhere Docker runs  
✅ **Scalability:** Easy to add more instances or services  
✅ **Maintainability:** Fast deployments, easy rollbacks, clear logs  
✅ **Infrastructure:** Reusable components (DNS, Registry, MongoDB) for future services

**Key Success Factors:**

1. Multi-stage Docker builds for fast iterations
2. Explicit environment loading for production config
3. Simplified MongoDB (no auth, network isolation)
4. Internal registry for fast deployments
5. CoreDNS for service discovery

**Lessons Learned:**

1. Container networking is different from host networking
2. Init scripts are one-time only (MongoDB lesson)
3. Explicit is better than implicit (env file loading)
4. Simpler solutions often better than complex (MongoDB auth)
5. Document as you go (this document!)

**Next Steps:**

- Monitor operational stability for 30 days
- Consider adding resource limits
- Implement automated backups (cron job)
- Add more TDOS services using this infrastructure
- Update SOPs with operational lessons learned

---

**Document Maintainer:** [Your Name]  
**Last Updated:** February 8, 2026  
**Next Review:** March 8, 2026
