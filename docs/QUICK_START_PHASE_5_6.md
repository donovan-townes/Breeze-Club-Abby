# Quick Start: Phase 5 & 6 Features

Get up and running with moderation, engagement tuning, Twitch integration, and RAG in 5 minutes.

---

## Prerequisites

- Abby bot installed and running
- MongoDB connection configured
- Discord server with admin permissions

---

## Step 1: Install New Dependencies

```bash
# Activate virtual environment
.venv\Scripts\activate

# Install new packages
pip install -r requirements.txt
```

This adds:

- `qdrant-client` (vector DB for RAG)
- `chromadb` (initial RAG storage)
- `sentence-transformers` (embeddings)

---

## Step 2: Configure Environment

Copy `.env.example` to `.env` (if not already done), then add/update:

```dotenv
# === Moderation ===
IMAGE_AUTO_MOVE_ENABLED=true
GENERAL_CHANNEL_ID=123456789  # Your general channel ID
MEMES_CHANNEL_ID=987654321    # Your memes channel ID

# === Nudges ===
NUDGE_ENABLED=false  # Enable when ready
NUDGE_CHANNEL_ID=123456789
NUDGE_INTERVAL_HOURS=24

# === XP Tuning ===
XP_CHANNEL_ID=123456789  # Your main chat channel
XP_MESSAGE_COOLDOWN_SECONDS=60
XP_ATTACHMENT_COOLDOWN_SECONDS=600
XP_STREAM_INTERVAL_MINUTES=5

# === Twitch ===
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
TWITCH_NOTIFY_CHANNEL_ID=123456789
TWITCH_POLL_MINUTES=15

# === RAG ===
CHROMA_PERSIST_DIR=chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
RAG_CONTEXT_ENABLED=false  # Enable after testing
```

**Pro tip:** Use Discord Developer Mode (Settings → Advanced → Developer Mode) to right-click channels/roles and "Copy ID".

---

## Step 3: Create Required Directories

```bash
mkdir chroma_db
mkdir shared\logs
```

---

## Step 4: Restart Bot

```bash
python main.py
```

Check logs for:

```
[🪪] Moderation cog ready (image auto-move=on)
[👈] Nudge Handler Loaded (enabled=False, interval=24h)
[🎥] Starting Twitch Live Scheduler
✅ TwitchSettings Success
```

---

## Step 5: Test Features

### Test 1: Image Auto-Move

1. Post an image in your general channel
2. Verify: Image appears in memes channel with attribution
3. Verify: Original post deleted, friendly reply sent

### Test 2: XP Tuning

1. Send a message in your XP channel
2. Check XP gain: `/xp status` (or your xp check command)
3. Send another message immediately
4. Verify: No XP gain (cooldown active)
5. Wait 60 seconds, send another message
6. Verify: XP gained

### Test 3: Twitch Commands

1. Run: `/twitch_notify enable:true channel:#your-channel`
2. Verify: "Twitch notifications enabled" response
3. Run: `/twitch_link @YourUser your_twitch_handle`
4. Verify: "Linked @YourUser to Twitch handle 'your_twitch_handle'" response

---

## Step 6: Test RAG (Optional)

### 6.1 Ingest Test Document

```discord
/rag ingest
  title: Test Guidelines
  text: Artists must submit high-quality demos in WAV or MP3 format. All tracks should be properly mixed and mastered.
  source: guidelines
  tags: submission,demo
```

### 6.2 Query RAG

```discord
/rag query
  query: What audio formats are accepted?
  top_k: 3
```

Should return chunk mentioning "WAV or MP3".

### 6.3 Check Stats

```discord
/rag stats
```

Should show 1 document, 1-2 chunks (depending on text length).

### 6.4 Enable RAG in Chatbot

In a channel where Abby chatbot is active:

```
rag on
```

Then ask Abby:

```
@Abby What are the submission requirements?
```

Abby's response should include context from the ingested guidelines.

---

## Step 7: (Advanced) Migrate to Qdrant

When your RAG corpus grows (100+ documents), migrate to Qdrant for better performance.

### 7.1 Start Qdrant

```bash
docker run -p 6333:6333 -v C:\Abby_Discord_Latest\qdrant_storage:/qdrant/storage qdrant/qdrant
```

### 7.2 Run Migration

```bash
# Dry run first (preview)
set MIGRATE_DRY_RUN=true
python scripts/migrate_chroma_to_qdrant.py abby_rag_collection 384

# Actual migration
set MIGRATE_DRY_RUN=false
python scripts/migrate_chroma_to_qdrant.py abby_rag_collection 384
```

### 7.3 Verify

```discord
/rag query query: test query top_k: 3
```

Results should match pre-migration queries.

---

## Troubleshooting

### "Cog not loading" in logs

- Check `pip list` shows all dependencies installed
- Look for ImportError in logs
- Verify `.py` files have `async def setup(bot)` signature

### Image not moving

- Verify `IMAGE_AUTO_MOVE_ENABLED=true`
- Check channel IDs correct (use Discord dev mode to copy)
- Ensure bot has Manage Messages permission in both channels

### Twitch commands not appearing

- Restart bot (slash commands registered on startup)
- Check bot has `applications.commands` OAuth scope
- Try `/help` to see if commands listed

### RAG query returns no results

- Check `/rag stats` shows documents ingested
- Verify `CHROMA_PERSIST_DIR=chroma_db` in `.env`
- Look for "ChromaDB" errors in logs

### Qdrant connection failed

- Verify Qdrant running: `docker ps` (should show qdrant container)
- Check port 6333 not blocked by firewall
- Try: `curl http://localhost:6333` (should return Qdrant version)

---

## What's Next?

- **Tune settings:** Adjust cooldowns, intervals based on server activity
- **Build RAG corpus:** Ingest label docs, guidelines, artist profiles
- **Monitor TDOS events:** Check `shared/logs/events.jsonl` for signals
- **Scale:** Migrate to Qdrant when ready

For detailed guides:

- **RAG Usage:** [docs/RAG_USAGE_GUIDE.md](./RAG_USAGE_GUIDE.md)
- **Phase Summary:** [docs/PHASE_5_6_SUMMARY.md](./PHASE_5_6_SUMMARY.md)
- **Environment:** [.env.example](./../.env.example)

---

## Quick Commands Reference

### Moderation

- Auto-move images (no commands, automatic)

### Engagement

- `/xp status` - Check your XP
- `/xp leaderboard` - View top users

### Twitch

- `/twitch_notify enable:[true/false] channel:[#channel]` - Toggle notifications
- `/twitch_link @user twitch_handle` - Link Discord to Twitch

### RAG (Admin Only)

- `/rag ingest title:[text] text:[text] source:[category] tags:[csv]` - Add document
- `/rag query query:[text] top_k:[number]` - Test retrieval
- `/rag stats` - Show corpus stats

### Chatbot RAG Toggle

- `rag on` - Enable RAG context
- `rag off` - Disable RAG context

---

Enjoy your upgraded Abby! 🐰
