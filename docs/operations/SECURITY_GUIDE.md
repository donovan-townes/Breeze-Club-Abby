# Security and Secrets Handling Guide

Comprehensive security model for 50-year deployment of Abby, covering token storage, rotation, least privilege, and cryptography.

**Last Updated:** January 31, 2026  
**Scope:** All deployment environments  
**Classification:** OPERATIONAL (not classified)

---

## Executive Summary

Abby implements defense-in-depth security across three layers:

1. **Token & Secrets Storage** — Environment variables, never hardcoded
2. **Data Protection** — Encryption at rest (sessions), sanitization in transit
3. **Access Control** — Least privilege via role-based quotas and guild isolation

---

## Layer 1: Token & Secrets Storage

### Never Hardcode

❌ **NEVER DO THIS:**
```python
OPENAI_API_KEY = "sk-..."
DISCORD_TOKEN = "MzI4..."
```python

✅ **ALWAYS DO THIS:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
```python

### Environment Variables

All secrets are loaded from `.env` at startup:

```bash
## .env (version control: NEVER add to git)
ABBY_TOKEN=<discord_bot_token>
OPENAI_API_KEY=<openai_key>
STABILITY_API_KEY=<stability_key>
TWITCH_CLIENT_SECRET=<twitch_secret>
SALT=<cryptographic_salt>
```python

### `.env` Placement:
```python
project_root/
├── .env                 # ⚠️ Never commit (in .gitignore)
├── .env.example         # ✅ Template (safe to commit)
└── launch.py
```python

### Loading Mechanism

```python
from dotenv import load_dotenv
import os

## Loads .env at process startup
load_dotenv()

## Access variables
token = os.getenv("ABBY_TOKEN")
if not token:
    raise RuntimeError("ABBY_TOKEN not set in environment")
```python

### Loading Order (50-year compatibility):

1. System environment variables (highest priority)
2. `.env` file in working directory
3. Default values in code (lowest priority)

This allows both local development (via `.env`) and production (via system env vars) without code changes.

---

## Layer 2: Data Protection

### Encryption at Rest (Session Data)

Chat sessions are encrypted in MongoDB using Fernet (AES-128 with authentication):

```python
from abby_core.security.encryption import encrypt, decrypt, generate_key

## Key generation (one-time setup)
key = generate_key(password="my_secure_password")

## Encryption
encrypted_message = encrypt("sensitive data", key)
## Output: gAAAAABl9Fx5...

## Decryption
decrypted = decrypt(encrypted_message, key)
## Output: "sensitive data"
```python

### Encryption Scheme:

- Algorithm: Fernet (symmetric, AES-128)
- Key derivation: PBKDF2-HMAC-SHA256 (100,000 iterations)
- Salt: Cryptographic salt from `SALT` env var

### Session Fields Encrypted:

- User messages (never store plaintext)
- Bot responses (for privacy)
- Metadata (user IDs, guild IDs)

### Key Management:
```python
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import base64

SALT = os.getenv("SALT").encode()  # From .env (min 32 chars)

def generate_key(password: str):
    """Generate encryption key from password."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key
```python

### Sanitization in Transit

User input is sanitized to prevent prompt injection attacks:

```python
from abby_core.interfaces.prompt_security import (
    get_prompt_security_gate,
    InjectionSeverity
)

gate = get_prompt_security_gate()

## Detect injection patterns
severity, reason = gate.detect_injection_pattern(
    text="my message {{admin_password}}",
    field_name="user_message"
)

match severity:
    case InjectionSeverity.SAFE:
        # Process message normally
    case InjectionSeverity.SUSPICIOUS:
        # Log and proceed cautiously
        logger.warning(f"Suspicious: {reason}")
    case InjectionSeverity.BLOCKED:
        # Reject message
        raise ValueError(f"Injection detected: {reason}")
```python

### Protected Fields:

- `guild_name` — prevent escape of guild context
- `user_name` — prevent social engineering
- `channel_name` — prevent context leakage
- Custom fields (RAG context, memory)

### Injection Patterns Blocked:

- Template delimiters: `{{`, `}}`
- SQL-like syntax: `'; DROP`, `UNION SELECT`
- System prompts: `Ignore above`, `System override`
- Encoding attempts: `\x`, `%00`, `%27`

---

## Layer 3: Access Control

### Least Privilege: Role-Based Quotas

All users operate under quota tiers determined by Discord role and level:

```python
## User role hierarchy
PRIVILEGE_LEVELS = {
    "member": 1,          # Base quota
    "moderator": 5,       # 5x multiplier
    "admin": 10,          # 10x multiplier
    "owner": float('inf') # Unlimited
}

## Daily generation quotas
DAILY_LIMITS_BY_LEVEL = {
    1: 10,     # Level 1-4: 10 gens/day
    5: 25,     # Level 5-9: 25 gens/day
    10: 50,    # Level 10+: 50 gens/day
}

## Owner overrides (from OWNER_USER_IDS env var)
OWNER_OVERRIDE = {
    "daily_limit": int(os.getenv("OWNER_DAILY_LIMIT", "9999")),
    "storage_limit": float('inf'),
    "can_reset_xp": True,
}
```python

### Quota Enforcement:
```python
from abby_core.storage.quota_manager import QuotaManager

quota = QuotaManager(storage_dir=Path("storage"))

## Check if user can generate
daily_limit = quota.resolve_daily_limit(
    user_id="123456789",
    user_roles=["member"],  # From Discord
    level=1                 # From XP system
)

if daily_count >= daily_limit:
    raise PermissionError(f"Quota exceeded: {daily_count}/{daily_limit}")
```python

### Guild Isolation

Each guild's data is isolated and inaccessible from other guilds:

```python
## Guild-scoped queries (MongoDB)
db.users.find_one({
    "user_id": "123",
    "guild_id": "456"  # ← Critical: prevents guild crossover
})

## RAG documents scoped to guild
db.rag_documents.find({
    "guild_id": "456",  # Only this guild's documents
    "document_type": "guidelines"
})

## User profiles NOT shared across guilds
## Guild A user #123 ≠ Guild B user #123
```python

### Why Guild Isolation Matters (50-year perspective):

- Data breach in one guild doesn't expose other guilds
- Different guilds can have different policies/settings
- Scales to thousands of guilds without cross-contamination
- Enables future multi-tenant architecture

### User Privacy Controls

Users can view and delete their data via `/privacy` command:

```python
class PrivacyPanel(commands.Cog):
    """User data privacy and deletion."""
    
    async def view_stored_data(self, user_id: int, guild_id: int):
        """Show user all data we store about them."""
        return {
            "chat_sessions": [/* encrypted sessions */],
            "user_profile": {/* public profile */},
            "xp_history": [/* all XP gains */],
            "bank_account": {/* balance + transactions */},
        }
    
    async def delete_all_data(self, user_id: int, guild_id: int):
        """GDPR compliance: delete user data."""
        # Delete sessions, profile, history, account
        # But keep de-identified audit logs (legal requirement)
```python

---

## API Key Management

### Required API Keys

| Key | Provider | Scope | Rotation |
| --- | --- | --- | --- |
| `ABBY_TOKEN` | Discord Developer Portal | Bot identity | 6 months (recommended) |
| `OPENAI_API_KEY` | OpenAI | LLM inference | 90 days (recommended) |
| `STABILITY_API_KEY` | Stability AI | Image generation | 90 days |
| `TWITCH_CLIENT_SECRET` | Twitch Developer | Stream detection | 90 days |
| `QDRANT_API_KEY` | Qdrant Cloud | Vector database | 6 months |

### Rotation Procedure

### Discord Bot Token:
```bash
## Step 1: Discord Dev Portal → Reset Token
## (New token generated, old one invalidated)

## Step 2: Update .env locally
ABBY_TOKEN=<new_token>

## Step 3: Deploy to production
git add .env
git commit -m "chore: rotate Discord token"
git push origin main

## Step 4: Restart bot (old token invalid)
systemctl restart abby-bot

## Step 5: Verify bot is online
## (should rejoin all guilds automatically)

## Downtime: ~30 seconds (graceful reconnect)
```python

### OpenAI API Key:
```bash
## Step 1: OpenAI Dashboard → Create new key
## (Keep old key for 24h overlap period)

## Step 2: Test new key locally
OPENAI_API_KEY=<new_key> python -c "from openai import OpenAI; ..."

## Step 3: Deploy to staging first
## (allow 24h observation period)

## Step 4: Deploy to production
## (old key still works as fallback)

## Step 5: Delete old key after 24h
## (now fully migrated)

## Downtime: 0 (seamless transition)
```python

### Key Compromise Response

If a key is compromised (exposed in logs, committed to git, etc.):

1. **Immediate (5 min):**
   - Revoke compromised key in provider dashboard
   - Generate new key
   - Update production `.env`
   - Redeploy bot

1. **Audit (1 hour):**
   - Search git history for key: `git log -p | grep "sk-"`
   - Search deployment logs for usage from unknown IPs
   - Check API billing for unusual charges

1. **Post-Incident (1 day):**
   - Add pre-commit hook to prevent secrets in git:
     ```bash
     # .git/hooks/pre-commit
     #!/bin/bash
     if git diff --cached | grep -E "sk- | MzI8"; then
         echo "ERROR: API key detected in commit"
         exit 1
     fi
     ```

   - Enable secret scanning in CI/CD
   - Document in incident log

---

## 50-Year Security Strategy

### Annual Audits

- [ ] Review all OWNER_USER_IDs (are users still authorized?)
- [ ] Audit role-based access (quotas still balanced?)
- [ ] Rotate all API keys (even if not compromised)
- [ ] Check for deprecated encryption schemes
- [ ] Verify SALT hasn't been exposed

### 5-Year Reviews

- [ ] Migrate to next-generation encryption (post-Fernet)
- [ ] Audit all sanitization patterns (new injection techniques?)
- [ ] Review user privacy controls (GDPR/CCPA compliance)
- [ ] Evaluate multi-factor authentication for admin actions

### 10-Year Reviews

- [ ] Full security architecture redesign
- [ ] Quantum-resistant cryptography evaluation
- [ ] Zero-trust network architecture assessment
- [ ] Plan migration to post-quantum algorithms

---

## Related Documents

- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) — API key requirements
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) — Access control procedures
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — Security incident triage
