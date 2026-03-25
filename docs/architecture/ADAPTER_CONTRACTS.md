# Platform Adapter Contracts

Specification for platform-agnostic adapters enabling Abby to run on Discord, Web, CLI, and future platforms without code changes.

**Last Updated:** January 31, 2026  
**Architecture:** Interface segregation, factory pattern, contract validation  
**Scope:** All platform-specific I/O

---

## Executive Summary

Abby is **platform-agnostic**. All user-facing I/O is routed through adapter interfaces:

1. **Tool Adapters** — Server/user/XP/status info queries
2. **Output Adapters** — Format responses for platform
3. **Economy Adapters** — Manage XP/currency balance
4. **LLM Adapters** — Swap language models
5. **Prompt Security Adapters** — Injection detection

This design enables:

- Multi-platform deployment (Discord, Web, CLI) without forking code
- Testing without platform dependencies
- Future platform additions (Slack, Teams, etc.) with minimal changes
- Clear platform boundaries

---

## Adapter Pattern Overview

### Interface → Implementation → Factory Registration

````python
## Step 1: Define interface (platform-agnostic)
from abc import ABC, abstractmethod

class IServerInfoTool(ABC):
    @abstractmethod
    async def get_server_info(self, server_id: str) -> ServerInfo:
        """Get server information."""
        pass

## Step 2: Implement for Discord
class DiscordServerInfoTool(IServerInfoTool):
    async def get_server_info(self, server_id: str) -> ServerInfo:
        guild = self.bot.get_guild(int(server_id))
        return ServerInfo(
            name=guild.name,
            member_count=len(guild.members),
            created_at=guild.created_at
        )

## Step 3: Register in factory
TOOL_REGISTRY = {
    "discord": DiscordServerInfoTool,
    "web": WebServerInfoTool,
    "cli": CLIServerInfoTool,
}

## Step 4: Resolve at runtime
def get_server_info_tool(platform: str) -> IServerInfoTool:
    return TOOL_REGISTRY[platform]()
```python

---

## Tool Adapters

### IServerInfoTool

**Purpose:** Query server/guild/workspace information

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ServerInfo:
    server_id: str
    name: str
    member_count: int
    owner_id: str
    created_at: datetime
    region: str | None
    custom_data: dict  # Platform-specific fields

class IServerInfoTool(ABC):
    @abstractmethod
    async def get_server_info(self, server_id: str) -> ServerInfo:
        """Get server/guild/workspace information."""
        pass
```python

### Discord Implementation:
```python
class DiscordServerInfoTool(IServerInfoTool):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    async def get_server_info(self, server_id: str) -> ServerInfo:
        guild = self.bot.get_guild(int(server_id))
        if not guild:
            raise ValueError(f"Guild {server_id} not found")

        return ServerInfo(
            server_id=str(guild.id),
            name=guild.name,
            member_count=len(guild.members),
            owner_id=str(guild.owner_id),
            created_at=guild.created_at,
            region=str(guild.region) if guild.region else None,
            custom_data={
                "verification_level": guild.verification_level.name,
                "features": list(guild.features)
            }
        )
```python

### IUserInfoTool

**Purpose:** Query user profile information

```python
@dataclass
class UserInfo:
    user_id: str
    username: str
    display_name: str
    avatar_url: str | None
    created_at: datetime
    is_bot: bool
    custom_data: dict

class IUserInfoTool(ABC):
    @abstractmethod
    async def get_user_info(self, user_id: str, server_id: str) -> UserInfo:
        """Get user profile in server context."""
        pass
```python

### Discord Implementation:
```python
class DiscordUserInfoTool(IUserInfoTool):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    async def get_user_info(self, user_id: str, server_id: str) -> UserInfo:
        guild = self.bot.get_guild(int(server_id))
        member = guild.get_member(int(user_id))
        user = member.user if member else self.bot.get_user(int(user_id))

        return UserInfo(
            user_id=str(user.id),
            username=user.name,
            display_name=member.display_name if member else user.display_name,
            avatar_url=user.display_avatar.url,
            created_at=user.created_at,
            is_bot=user.bot,
            custom_data={
                "roles": [r.name for r in member.roles] if member else [],
                "joined_at": member.joined_at if member else None
            }
        )
```python

### IUserXPTool

**Purpose:** Query user XP and level

```python
@dataclass
class UserXPInfo:
    user_id: str
    server_id: str
    xp: int
    level: int
    xp_next_level: int
    created_at: datetime

class IUserXPTool(ABC):
    @abstractmethod
    async def get_user_xp(self, user_id: str, server_id: str) -> UserXPInfo:
        """Get user XP and level."""
        pass

    @abstractmethod
    async def increment_user_xp(
        self,
        user_id: str,
        server_id: str,
        xp_delta: int,
        reason: str
    ) -> UserXPInfo:
        """Increment user XP."""
        pass
```python

**Implementation Location:** `abby_core/discord/adapters/economy.py`

### IBotStatusTool

**Purpose:** Report bot health and status

```python
@dataclass
class BotStatus:
    is_online: bool
    uptime_seconds: int
    latency_ms: float
    guild_count: int
    user_count: int
    memory_usage_mb: int
    custom_data: dict

class IBotStatusTool(ABC):
    @abstractmethod
    async def get_bot_status(self) -> BotStatus:
        """Get bot health status."""
        pass
```python

---

## Output Adapters

### IOutputFormatter

**Purpose:** Format bot responses for platform

```python
from discord import Embed

@dataclass
class FormattedOutput:
    content: str
    format_type: str  # "plain", "embed", "markdown", "html"
    platform_data: dict

class IOutputFormatter(ABC):
    @abstractmethod
    async def format_message(
        self,
        text: str,
        title: str | None = None,
        fields: list[dict] | None = None,
        color: str | None = None
    ) -> FormattedOutput:
        """Format text response for platform."""
        pass
```python

### Discord Implementation:
```python
class DiscordOutputFormatter(IOutputFormatter):
    async def format_message(
        self,
        text: str,
        title: str | None = None,
        fields: list[dict] | None = None,
        color: str | None = None
    ) -> FormattedOutput:
        embed = Embed(
            title=title,
            description=text,
            color=int(color, 16) if color else 0x2B2D31
        )

        if fields:
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", True)
                )

        return FormattedOutput(
            content="",
            format_type="embed",
            platform_data={"embed": embed}
        )
```python

### IAnnouncementDelivery

**Purpose:** Deliver announcements to users/channels

```python
class IAnnouncementDelivery(ABC):
    @abstractmethod
    async def deliver_to_channel(
        self,
        channel_id: str,
        message: str,
        attachments: list[str] | None = None
    ) -> str:
        """Deliver message to channel. Returns message_id."""
        pass

    @abstractmethod
    async def deliver_to_user(
        self,
        user_id: str,
        message: str,
        attachments: list[str] | None = None
    ) -> str:
        """Deliver DM to user. Returns message_id."""
        pass
```python

**Implementation Location:** `abby_core/discord/adapters/__init__.py`

---

## Economy Adapters

### IEconomyService

**Purpose:** Manage user currency/XP balances

```python
@dataclass
class Balance:
    user_id: str
    server_id: str
    currency: str  # "xp", "coins", "tokens"
    balance: int
    last_updated_at: datetime

class IEconomyService(ABC):
    @abstractmethod
    async def get_balance(
        self,
        user_id: str,
        server_id: str,
        currency: str
    ) -> Balance:
        """Get user balance."""
        pass

    @abstractmethod
    async def deposit(
        self,
        user_id: str,
        server_id: str,
        currency: str,
        amount: int,
        reason: str
    ) -> Balance:
        """Deposit into user account."""
        pass

    @abstractmethod
    async def withdraw(
        self,
        user_id: str,
        server_id: str,
        currency: str,
        amount: int,
        reason: str
    ) -> Balance:
        """Withdraw from user account (fails if insufficient)."""
        pass
```python

### IXPService

**Purpose:** XP-specific operations

```python
class IXPService(ABC):
    @abstractmethod
    async def get_xp(self, user_id: str, server_id: str) -> int:
        """Get total XP."""
        pass

    @abstractmethod
    async def get_level(self, user_id: str, server_id: str) -> int:
        """Get XP level."""
        pass

    @abstractmethod
    async def increment_xp(
        self,
        user_id: str,
        server_id: str,
        xp_delta: int,
        reason: str
    ) -> int:
        """Increment XP. Returns new total."""
        pass
```python

### IEconomyAdapter (Combined)

**Purpose:** Unified economy interface for core services

```python
class IEconomyAdapter(IEconomyService, IXPService):
    """Combined economy interface."""
    @abstractmethod
    async def tip_user(
        self,
        from_user: str,
        to_user: str,
        server_id: str,
        amount: int
    ) -> Balance:
        """Transfer XP from one user to another."""
        pass
```python

---

## LLM Adapters

### ILLMService

**Purpose:** Swap language models without code changes

```python
@dataclass
class LLMResponse:
    text: str
    stop_reason: str
    tokens_used: int
    model: str
    latency_ms: float

class ILLMService(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_context: str,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings for text."""
        pass
```python

### Implementations:

- `OpenAILLMService` — GPT-4, GPT-3.5-turbo
- `ClaudeLLMService` — Claude 3.x (future)
- `LocalLLMService` — Llama 2, Mistral (self-hosted)

### Runtime Selection:
```python
llm_service = LLM_REGISTRY[config.llm_provider]()
response = await llm_service.generate(prompt, system_context)
```python

---

## Prompt Security Adapters

### IPromptSecurityGate

**Purpose:** Detect prompt injection attacks

```python
from enum import Enum

class InjectionSeverity(Enum):
    SAFE = "safe"           # ✅ Process normally
    SUSPICIOUS = "suspicious"  # ⚠️ Log but process
    BLOCKED = "blocked"     # 🚫 Reject message

class IPromptSecurityGate(ABC):
    @abstractmethod
    async def detect_injection_pattern(
        self,
        text: str,
        field_name: str
    ) -> tuple[InjectionSeverity, str]:
        """Detect injection attempt. Returns (severity, reason)."""
        pass
```python

**Implementation:** `abby_core/security/prompt_injection_detector.py`

---

## Contract Validation Tests

All adapters are validated to match interfaces:

```python
## tests/test_adapter_contracts.py

def test_discord_tool_implements_interface():
    """Verify DiscordServerInfoTool implements IServerInfoTool."""
    assert issubclass(DiscordServerInfoTool, IServerInfoTool)

    # Verify all methods present
    for method in ["get_server_info"]:
        assert hasattr(DiscordServerInfoTool, method)

def test_output_formatter_contract():
    """Verify IOutputFormatter methods are called correctly."""
    formatter = DiscordOutputFormatter()

    output = await formatter.format_message(
        text="Hello",
        title="Greeting"
    )

    assert output.format_type == "embed"
    assert output.platform_data["embed"].title == "Greeting"

def test_adapter_factory_registration():
    """Verify all adapters registered in factories."""
    for platform in ["discord", "web", "cli"]:
        tool = TOOL_REGISTRY[platform]()
        assert isinstance(tool, IServerInfoTool)
```python

### Running Contract Tests:
```bash
pytest tests/test_adapter_contracts.py -v
```python

---

## Adding New Adapters

### For a New Platform (e.g., Web)

1. **Create interface implementations:**
   ```python
   # abby_core/web/adapters/server_info_tool.py
   class WebServerInfoTool(IServerInfoTool):
       async def get_server_info(self, server_id: str) -> ServerInfo:
           # Query from REST API
           pass
````

1. **Register in factory:**

   ```python
   TOOL_REGISTRY["web"] = WebServerInfoTool
   ```

1. **Add contract tests:**
   ```python
   def test_web_adapter_contracts():
       tool = WebServerInfoTool()
       assert isinstance(tool, IServerInfoTool)
   ```

### For a New Capability

1. **Define interface in `abby_core/interfaces/`:**

   ```python
   class INewCapability(ABC):
       @abstractmethod
       async def do_something(self) -> str:
           pass
   ```

1. **Implement for Discord:**

   ```python
   class DiscordNewCapability(INewCapability):
       async def do_something(self) -> str:
           pass
   ```

1. **Inject into core service:**
   ```python
   class MyService:
       def __init__(self, capability: INewCapability):
           self.capability = capability
   ```

---

## Bridging Adapters

### OrchestratorAdapter

**Purpose:** Add personality and guild context to generic requests

````python
class OrchestratorAdapter:
    """Wraps IEconomyAdapter to add personality + guild context."""

    def __init__(self, economy: IEconomyAdapter, personality: IPersonalityService):
        self.economy = economy
        self.personality = personality

    async def increment_xp_with_flavor(
        self,
        user_id: str,
        guild_id: str,
        xp_delta: int
    ) -> str:
        """Increment XP and return personality-flavored message."""
        await self.economy.increment_xp(user_id, guild_id, xp_delta, "activity")

        flavor = await self.personality.get_xp_flavor(guild_id)
        return flavor.format(xp=xp_delta)
```python

### RAGAdapter

**Purpose:** Add guild isolation and quota enforcement to queries

```python
class RAGAdapter:
    """Wraps RAG handler with guild isolation + quotas."""

    def __init__(self, handler: RAGHandler, quota_manager: QuotaManager):
        self.handler = handler
        self.quota_manager = quota_manager

    async def ingest_document(
        self,
        guild_id: str,
        document_type: str,
        content: str
    ) -> str:
        """Ingest with quota check."""
        # Check guild quota
        usage = await self.quota_manager.get_storage_usage(guild_id)
        if usage >= QUOTA_LIMIT:
            raise PermissionError(f"Guild quota exceeded: {usage}/{QUOTA_LIMIT}")

        # Ingest with guild_id metadata
        doc_id = await self.handler.ingest(
            content=content,
            metadata={"guild_id": guild_id, "type": document_type}
        )

        return doc_id
```python

---

## 50-Year Adapter Strategy

### Annual Audits

- [ ] Review interface definitions (still fit use cases?)
- [ ] Audit adapter implementations (any tech debt?)
- [ ] Check for unused adapters (deprecate?)
- [ ] Verify factory registration complete

### 5-Year Reviews

- [ ] Evaluate new platforms (Slack, Teams, etc.)
- [ ] Redesign adapters for emerging capabilities
- [ ] Plan interface versioning (v1, v2, v3)
- [ ] Consider unified adapter registry (service discovery)

### 10-Year Reviews

- [ ] Full adapter architecture redesign
- [ ] Evaluate plugin-based adapter system
- [ ] Plan for decoupled platform services
- [ ] Multi-region adapter distribution

---

## Related Documents

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Adapter layer overview
- [../operations/TEST_STRATEGY.md](../operations/TEST_STRATEGY.md) — Contract validation testing
- [../operations/INCIDENT_RESPONSE.md](../operations/INCIDENT_RESPONSE.md) — Adapter failure diagnostics
````
