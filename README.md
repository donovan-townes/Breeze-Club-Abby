# Abby 🐰

## AI-Powered Creative Assistant for Discord

[![Discord](https://img.shields.io/discord/819650821808273408?color=7289da&logo=discord&logoColor=white)](https://discord.gg/yGsBGQAC49)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.6.4-blue.svg?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green.svg?logo=mongodb&logoColor=white)](https://www.mongodb.com/)

[Join the Breeze Club Discord](https://discord.gg/yGsBGQAC49) | [Documentation](docs/INDEX.md) | [Contributing](CONTRIBUTING.md)

---

## About

Abby is a next-generation Discord bot built for the **Breeze Club** creative community. Designed to support artists, producers, and music enthusiasts, Abby combines advanced AI capabilities with robust community management tools.

Built with **clean architecture** principles, Abby separates platform-agnostic business logic (`abby_core`) from Discord-specific implementations (`abby_adapters/discord`), making it modular, testable, and adaptable to future platforms.

### ✨ Key Features

- **🤖 Conversational AI** — Context-aware chatbot powered by LLM (OpenAI/Ollama) with RAG for long-term memory
- **🎨 Image Generation** — AI-powered image creation with Stability AI, smart quota management, and user-level storage
- **📊 Economy & Leveling** — XP system with cooldowns, level-based rewards, and guild-specific progression
- **📚 RAG Knowledge Base** — Retrieval-Augmented Generation for document-aware conversations
- **🎥 Twitch Integration** — Live stream notifications, user linking, and automatic status updates
- **💾 TDOS Memory** — Advanced memory decay, relational learning, and long-term context retention
- **🛡️ Moderation** — Auto-moderation, content nudges, and configurable policies
- **🔐 Security** — Encrypted conversation storage and secure credential management

---

## Architecture

Abby follows **clean architecture** principles with clear separation of concerns:

````python
├── abby_core/              # Platform-agnostic business logic + Discord adapter
│   ├── database/           # MongoDB schemas & queries
│   ├── llm/                # LLM clients (OpenAI, Ollama)
│   ├── rag/                # Vector databases (Chroma)
│   ├── economy/            # XP, leveling, banking
│   ├── generation/         # Image generation APIs
│   ├── storage/            # File management & quotas
│   ├── personality/        # Bot personas & response patterns
│   ├── security/           # Encryption & authentication
│   ├── observability/      # Logging & telemetry
│   └── discord/            # Discord adapter (cogs, loader, config)
│
├── tdos_intelligence/      # TDOS orchestration + memory/rag utilities
├── docs/                   # Documentation (entrypoint: docs/INDEX.md)
└── launch.py               # Bot entry point
```python

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for detailed architectural guidelines.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (recommended: 3.12.0 or later)
- **MongoDB 7.0+** (local or [MongoDB Atlas](https://www.mongodb.com/cloud/atlas))
- **Discord Bot Token** ([Discord Developer Portal](https://discord.com/developers/applications))
- **API Keys** (optional):
  - OpenAI API key for GPT models
  - Stability AI key for image generation
  - Twitch client ID/secret for live notifications

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/Abby_Discord_Latest.git
   cd Abby_Discord_Latest
````

1. **Create virtual environment**

   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

1. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

   ### Minimum required `.env` configuration:

   ```env
   # Discord
   ABBY_TOKEN=your_discord_bot_token_here

   # MongoDB
   MONGO_URI=mongodb://localhost:27017/
   MONGO_DB_NAME=Abby_Database

   # Optional: AI Services
   OPENAI_API_KEY=your_openai_key_here
   STABILITY_API_KEY=your_stability_key_here
   ```

1. **Initialize database (optional)**

   ```bash
   python scripts/initialize_database.py
   ```

1. **Run Abby**
   ```bash
   python launch.py
   ```

### First Steps

Once Abby is online:

1. **Test basic functionality**: `/ping`
2. **Check bot status**: `/info`
3. **Start a conversation**: "Hey Abby, how are you?"
4. **Generate an image**: `/imagine prompt="a cute rabbit in a meadow"`

See [docs/getting-started/](docs/getting-started/) for detailed setup guides.

---

## 📚 Documentation

### Getting Started

- **[Installation Guide](docs/getting-started/installation.md)** — Step-by-step setup
- **[Configuration](docs/getting-started/configuration.md)** — Environment variables and settings
- **[Deployment](docs/deployment/)** — Production deployment with NSSM/systemd

### Architecture

- **[Architecture Overview](docs/architecture/ARCHITECTURE.md)** — Design principles and patterns
- **[Abby Role & Modes](docs/architecture/ABBY_ROLE_AND_MODES.md)** — Portal positioning, operating modes, guardrails
- **[Roadmap](docs/architecture/ROADMAP.md)** — Phase sequencing aligned to architecture
- **[Database Schema](docs/architecture/database-schema.md)** — MongoDB collections and indexes
- **[Storage System](docs/architecture/STORAGE_SYSTEM.md)** — File management and quotas

### Features

- **[Conversational AI](docs/features/chatbot.md)** — LLM configuration and RAG integration
- **[Image Generation](docs/features/image-generation.md)** — Stability AI integration and quotas
- **[Economy & XP](docs/features/economy-xp.md)** — Leveling system and rewards
- **[Twitch Integration](docs/features/twitch.md)** — Live notifications and user linking
- **[RAG System](docs/features/RAG_USAGE_GUIDE.md)** — Knowledge base and document retrieval

### API Reference

- **[Storage API](docs/api-reference/STORAGE_API_REFERENCE.md)** — File management methods
- **[LLM Configuration](docs/api-reference/LLM_CONFIGURATION.md)** — LLM client setup
- **[Core Modules](docs/api-reference/)** — Complete API documentation

### Contributing

- **[Contributing Guide](CONTRIBUTING.md)** — How to contribute
- **[Code Style](docs/contributing/code-style.md)** — Python standards
- **[Testing Guide](docs/contributing/testing.md)** — Writing and running tests

---

## 🎮 Commands

Abby uses **slash commands** for most interactions. Type `/` in Discord to see available commands.

### 🔧 Admin Commands

| Command              | Description                                          | Permission Required |
| -------------------- | ---------------------------------------------------- | ------------------- |
| `/rag_ingest`        | Ingest documents into RAG knowledge base             | Administrator       |
| `/rag_query`         | Query the RAG knowledge base                         | Administrator       |
| `/moderation_config` | Configure auto-moderation settings                   | Administrator       |
| `/persona <name>`    | Change Abby's personality (bunny, kitten, owl, etc.) | Administrator       |
| `/clear_conv <user>` | Clear a user's conversation history                  | Administrator       |
| `/sync_slash`        | Sync slash commands with Discord                     | Administrator       |
| `/shutdown`          | Gracefully shut down the bot                         | Administrator       |
| `/reload <cog>`      | Reload a specific cog without restarting             | Administrator       |

### 🎨 Creative Commands

| Command            | Description                                  | Example                                              |
| ------------------ | -------------------------------------------- | ---------------------------------------------------- |
| `/imagine`         | Generate AI images with Stability AI         | `/imagine prompt:"cyberpunk rabbit" style:neon-punk` |
| `/analyze`         | Analyze text for sentiment, keywords, themes | `/analyze text:"Check out this track!"`              |
| **Conversational** | Chat naturally with Abby by mentioning her   | "Hey Abby, what's your favorite genre?"              |

### Chatbot Triggers:

- Summon: "hey abby", "hi abby", "@Abby", or direct mentions
- Dismiss: "thanks abby", "bye abby", "that's all"
- Auto-dismiss: 60 seconds of inactivity

### Personality Personas:

- `bunny` (default) — Energetic, creative, supportive
- `kitten` — Playful, curious, affectionate
- `owl` — Wise, analytical, thoughtful
- `squirrel` — Energetic, scattered, enthusiastic
- `fox` — Clever, witty, mischievous
- `panda` — Calm, zen, chill
- `kiki` — Custom personality (configurable)

### 💰 Economy Commands

| Command                | Description                              |
| ---------------------- | ---------------------------------------- |
| `/balance [user]`      | Check your or another user's balance     |
| `/daily`               | Claim daily XP bonus                     |
| `/leaderboard`         | View top users by XP/level               |
| `/pay <user> <amount>` | Transfer currency to another user        |
| `/tip <user> <amount>` | Tip another user (1,000 BC daily budget) |
| `/shop`                | Browse available items and services      |

> **New:** `/tip` command allows peer recognition with daily budgets! See [Tipping Guide](docs/features/TIPPING_GUIDE.md).

### 🎥 Twitch Integration

| Command                    | Description                          |
| -------------------------- | ------------------------------------ |
| `/twitch link <username>`  | Link your Twitch account             |
| `/twitch unlink`           | Unlink your Twitch account           |
| `/twitch check <username>` | Check if a Twitch user is live       |
| `/twitch notify`           | Configure live notification settings |

**Auto-notifications**: Abby automatically posts when linked users go live.

### 🛠️ Utility Commands

| Command                    | Description                              |
| -------------------------- | ---------------------------------------- |
| `/ping`                    | Check bot latency and responsiveness     |
| `/info`                    | Display bot version, uptime, and stats   |
| `/status`                  | Check service health (MongoDB, LLM, RAG) |
| `/remind <time> <message>` | Set a reminder                           |
| `/userinfo [user]`         | Get detailed user information            |

### 🔗 URL Handlers (Automatic)

Abby automatically enhances links from:

- **YouTube** — Rich embeds with thumbnails
- **Twitter/X** — Tweet content previews
- **Twitch** — Clip embeds and stream info
- **SoundCloud** — Track embeds with metadata

---

## 💡 Usage Examples

### Conversational AI with RAG

````python
User: Hey Abby, what's the best way to mix vocals?
Abby: Great question! Based on our production docs, here are the key steps:

      1. Start with gain staging (peak around -6dB)
      2. Apply EQ to remove mud (200-400Hz) and boost presence (3-5kHz)
      3. Add compression (3:1 ratio, medium attack/release)
      4. Use reverb/delay sparingly for depth

      Want me to elaborate on any of these?
```python

### Image Generation with Quotas

```python
/imagine prompt:"a rabbit producer making beats in a neon-lit studio" style:cyberpunk

🎨 Generating image... (2/10 daily generations remaining)
✅ Image created! Saved to your profile gallery.
📊 Storage: 2.3 MB / 50 MB used
```python

### XP System

```python
User: *Posts a helpful tutorial*
Abby: 🌟 +50 XP! You're now level 12!
      Keep sharing great content! Next level: 250 XP
```python

---

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```env
## Core Settings
ABBY_TOKEN=                      # Discord bot token
MONGO_URI=                       # MongoDB connection string
LOG_LEVEL=INFO                   # Logging level (DEBUG, INFO, WARNING, ERROR)

## AI Services
OPENAI_API_KEY=                  # OpenAI API key
OLLAMA_HOST=http://localhost:11434  # Local Ollama endpoint
STABILITY_API_KEY=               # Stability AI key for image generation
RAG_CONTEXT_ENABLED=true         # Enable RAG knowledge retrieval

## Vector Databases
QDRANT_HOST=localhost            # Qdrant host
QDRANT_PORT=6333                 # Qdrant port
QDRANT_API_KEY=                  # Optional: Qdrant API key
CHROMA_PERSIST_DIR=./chroma_db   # ChromaDB storage directory

## Storage & Quotas
MAX_GLOBAL_STORAGE_MB=5000       # Total bot storage limit
MAX_USER_STORAGE_MB=50           # Per-user storage limit
MAX_USER_DAILY_GENS=10           # Daily image generation limit
CLEANUP_DAYS=30                  # Auto-delete files after N days

## XP System
XP_BASE_AMOUNT=10                # Base XP per message
XP_COOLDOWN_SECONDS=60           # Cooldown between XP gains
XP_MESSAGE_BONUS=5               # Bonus XP for longer messages
XP_MEDIA_BONUS=10                # Bonus XP for media attachments

## Twitch Integration
TWITCH_CLIENT_ID=                # Twitch app client ID
TWITCH_CLIENT_SECRET=            # Twitch app secret
TWITCH_POLL_INTERVAL=300         # Check streams every N seconds

## Moderation
AUTO_MOVE_IMAGES=true            # Auto-move images to correct channels
NUDGE_INACTIVE_USERS=true        # Send engagement nudges
NUDGE_CHANNEL_ID=123456789       # Channel for nudge messages
```python

See [docs/getting-started/configuration.md](docs/getting-started/configuration.md) for full configuration reference.

### Channel IDs

Configure Discord channel IDs in `abby_adapters/discord/config.py`:

```python
@dataclass
class DiscordChannels:
    breeze_lounge: int = 802512963519905852      # Main chat
    abby_chat: int = 1103490012500201632         # Abby conversation channel
    giveaway_channel: int = 802461884091465748   # Giveaway announcements
    radio_channel: int = 839379779790438430      # Voice/radio channel
    test_channel: int = 1103490012500201632      # Testing
```python

---

## 🧩 Core Technologies

- **[discord.py](https://discordpy.readthedocs.io/)** — Discord bot framework
- **[MongoDB](https://www.mongodb.com/)** — NoSQL database for user data, XP, economy
- **[OpenAI](https://openai.com/)** / **[Ollama](https://ollama.ai/)** — LLM providers for conversational AI
- **[Qdrant](https://qdrant.tech/)** / **[ChromaDB](https://www.trychroma.com/)** — Vector databases for RAG
- **[Stability AI](https://stability.ai/)** — Image generation API
- **TDOS Memory** — Advanced memory decay and relational learning system
- **[aiohttp](https://docs.aiohttp.org/)** — Async HTTP for external APIs
- **[cryptography](https://cryptography.io/)** — Encryption for sensitive data

---

## 🚀 Roadmap

### Current Focus

- ✅ Clean architecture refactor (core/adapters separation)
- ✅ Unified MongoDB schema
- ✅ RAG system with Qdrant/Chroma
- ✅ Advanced memory system (TDOS Memory v1.0)
- ✅ Storage system with quota management
- ✅ Twitch live notifications

### Upcoming Features

- 🔄 **Enhanced Moderation** — AI-powered content filtering and context-aware moderation
- 🔄 **Music Commands** — Spotify/SoundCloud integration, playlist management
- 🔄 **Community Events** — Giveaways, polls, scheduled events
- 🔄 **Analytics Dashboard** — Web dashboard for server insights
- 🔄 **Voice Commands** — Voice channel interaction and audio processing
- 🔄 **Multi-Guild Support** — Per-guild configurations and isolated data

See [GitHub Issues](https://github.com/your-org/abby/issues) for detailed feature requests and bug reports.

---

## 🤝 Contributing

We welcome contributions! Whether it's bug fixes, new features, or documentation improvements.

**Important**: Direct pushes to `main` are disabled. All changes must go through Pull Requests.

### Quick Contribution Guide

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make changes** following our [code style](docs/contributing/code-style.md)
4. **Test thoroughly** in your development environment
5. **Submit a PR** with clear description and tests

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Development Setup

```bash
## Clone your fork
git clone https://github.com/your-username/Abby_Discord_Latest.git
cd Abby_Discord_Latest

## Create feature branch
git checkout -b feature/my-new-feature

## Set up development environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

## Configure test environment
cp .env.example .env
## Edit .env with test credentials

## Run the bot
python launch.py
```python

### Areas We Need Help

- 🐛 **Bug Fixes** — Check [Issues](https://github.com/your-org/abby/issues?q=is%3Aissue+is%3Aopen+label%3Abug)
- 📝 **Documentation** — Improve guides and API docs
- 🎨 **UI/UX** — Better Discord embeds and interactions
- 🧪 **Testing** — Add unit/integration tests
- 🌐 **Integrations** — New platform integrations (Spotify, YouTube Music, etc.)

---

## 📋 Project Status

![Development Status](https://img.shields.io/badge/status-active%20development-brightgreen.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-in%20progress-yellow.svg)

**Current Version**: `v2.0.0-beta`
**Last Updated**: January 2026
**Active Contributors**: 2
**Open Issues**: [View on GitHub](https://github.com/your-org/abby/issues)

---

## 📜 License

This project is **not licensed**. You are free to use, modify, and distribute it as you wish.

Attribution is appreciated but not required. If you use Abby or parts of its codebase, a mention would be awesome! 🙏

---

## 🙏 Acknowledgments

- **[brndndiaz](https://brndndiaz.dev)** — Core architecture, MongoDB integration, and deployment infrastructure
- **[Breeze Club Community](https://discord.gg/yGsBGQAC49)** — Testing, feedback, and creative inspiration
- **Open Source Community** — For the amazing libraries that power Abby

Special thanks to all contributors who have helped shape Abby into what it is today!

---

## 📞 Support & Community

- **Discord**: [Breeze Club Server](https://discord.gg/yGsBGQAC49)
- **Issues**: [GitHub Issues](https://github.com/your-org/abby/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/abby/discussions)
- **Lead Developer**: [@z8phyr\_](https://discord.com/users/your-user-id) on Discord

---

## 📸 Screenshots

### Conversational AI

![Abby Chatbot](docs/images/chatbot-example.png)

### Image Generation

![Image Generation](docs/images/image-generation-example.png)

### Twitch Notifications

![Twitch Live](docs/images/twitch-notification-example.png)

---

### Built with ❤️ for the Breeze Club community by [@z8phyr\_](https://discord.com/users/your-user-id)

🐰 _"Let's make something amazing together!"_ — Abby
````
