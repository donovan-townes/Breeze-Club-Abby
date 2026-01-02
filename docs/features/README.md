# Features Documentation

Detailed guides for each of Abby's features and capabilities.

## 📚 Contents

### 🤖 AI & Conversational

#### [Conversational AI (Chatbot)](chatbot.md)

Natural language conversations with context awareness and personality.

**Topics covered:**

- Summon/dismiss patterns
- Conversation flow and timeouts
- Personality system (personas)
- Context retention and memory
- RAG integration for knowledge retrieval

---

#### [RAG System](RAG_USAGE_GUIDE.md)

Retrieval-Augmented Generation for document-aware conversations.

**Topics covered:**

- Document ingestion workflow
- Query and retrieval mechanisms
- Vector database backends (Qdrant/Chroma)
- Guild-scoped vs. user-scoped knowledge
- Performance tuning and chunking strategies

---

#### [TDOS Memory System](tdos-memory.md)

Advanced memory decay, relational learning, and long-term context.

**Topics covered:**

- Memory envelope structure
- Decay algorithms (exponential, power-law)
- Fact extraction from conversations
- Relational memory updates
- Shared narratives across users

---

### 🎨 Creative Tools

#### [Image Generation](image-generation.md)

AI-powered image creation with Stability AI.

**Topics covered:**

- `/imagine` command usage
- Style presets and parameters
- Quota system (daily limits, storage)
- Role-based quota overrides
- Image gallery and management

---

#### [Text Analysis](text-analysis.md)

Sentiment analysis, keyword extraction, and content insights.

**Topics covered:**

- `/analyze` command
- Sentiment scoring
- Keyword and theme detection
- Content moderation signals

---

### 💰 Economy & Progression

#### [XP & Leveling System](economy-xp.md)

Experience points, leveling, and progression mechanics.

**Topics covered:**

- XP gain mechanics (messages, media, events)
- Cooldown and rate limiting
- Level calculation and thresholds
- Guild-specific vs. global XP
- Leaderboards and ranking

---

#### [Banking & Currency](banking.md)

User balances, transactions, and economy management.

**Topics covered:**

- Balance checking and transfers
- Daily bonuses and rewards
- Shop system integration
- Transaction logging
- Economy moderation tools

---

### 🎥 Integrations

#### [Twitch Integration](twitch.md)

Live stream notifications and Twitch account linking.

**Topics covered:**

- User account linking
- Live notification system
- Automatic status checking
- Clip and VOD embeds
- Configuration and channel setup

---

#### [URL Handlers](url-handlers.md)

Automatic link embeds for YouTube, Twitter, Twitch, and more.

**Topics covered:**

- Supported platforms
- Embed customization
- Metadata extraction
- Rate limiting and caching

---

### 🛡️ Moderation & Community

#### [Auto-Moderation](moderation.md)

Automated content moderation and engagement tools.

**Topics covered:**

- Content filtering rules
- Auto-move images to correct channels
- Inactive user nudges
- Spam detection and prevention
- Configurable moderation policies

---

#### [Greetings & MOTD](greetings.md)

Welcome messages, announcements, and daily messages.

**Topics covered:**

- Welcome message templates
- Message of the day (MOTD) system
- Role assignment on join
- Custom greeting configuration

---

### 🔧 Utility

#### [Reminders](reminders.md)

Scheduled reminders and notifications.

**Topics covered:**

- `/remind` command
- Time parsing (natural language)
- Reminder management (list, cancel)
- Recurring reminders

---

#### [User Info & Stats](user-info.md)

User profiles, statistics, and server information.

**Topics covered:**

- `/userinfo` command
- Server statistics
- Activity tracking
- Profile customization

---

## 🎯 Feature Roadmap

### ✅ Implemented

- Conversational AI with RAG
- Image generation with quotas
- XP and leveling
- Twitch live notifications
- Auto-moderation
- TDOS Memory integration

### 🔄 In Progress

- Music commands (Spotify/SoundCloud)
- Enhanced moderation (AI-powered)
- Community events (giveaways, polls)

### 📋 Planned

- Voice commands and audio processing
- Web dashboard for analytics
- Multi-guild per-server configs
- Custom command creator
- Scheduled content posting

See [GitHub Issues](https://github.com/your-org/abby/issues) for detailed feature tracking.

---

## 📖 Related Documentation

- **[Getting Started](../getting-started/)** — Setup and configuration
- **[Architecture](../architecture/)** — System design
- **[API Reference](../api-reference/)** — Developer API
- **[Contributing](../contributing/)** — Adding new features
