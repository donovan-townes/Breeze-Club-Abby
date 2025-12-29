# LLM Configuration & Usage Guide

## Overview

Abby uses a provider-agnostic LLM abstraction layer that supports **Ollama** as the primary provider with **OpenAI** as an automatic fallback. The system emits TDOS-compliant `LLM.INFERENCE` events for all inference operations, enabling observability and governance.

## Architecture

**LLM Client**: `abby-core/llm/llm_client.py`

- Provider-agnostic interface (`chat`, `summarize`)
- Automatic provider fallback on failure
- TDOS event emission for success/failure
- Configurable timeouts and retries
- Zero Discord dependencies (pure domain logic)

**Integration Layer**: `utils/chat_openai.py`

- Legacy compatibility wrapper
- Routes all LLM operations through `LLMClient`
- Maintains persona/personality system
- Preserves chat history formatting

## Environment Variables

### Required Variables

```bash
# Discord Bot Token (required)
ABBY_TOKEN=your_discord_bot_token

# MongoDB Connection (required)
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=Abby

# LLM Provider Configuration (choose one or both)
LLM_PROVIDER=ollama  # Primary: ollama | openai
```

### Ollama Configuration (Primary Provider)

```bash
# Ollama Service
OLLAMA_HOST=http://localhost:11434  # Default Ollama endpoint
OLLAMA_MODEL=llama3                  # Model name (llama3, mistral, codellama, etc.)

# Timeout Settings
LLM_TIMEOUT=30  # Seconds before provider timeout (default: 30)
```

**Ollama Installation**:

- Windows: Download from [ollama.ai](https://ollama.ai/download/windows)
- Linux: `curl -fsSL https://ollama.ai/install.sh | sh`
- Pull model: `ollama pull llama3`
- Verify: `curl http://localhost:11434/api/tags`

### OpenAI Configuration (Fallback Provider)

```bash
# OpenAI API
OPENAI_API_KEY=sk-...                # Your OpenAI API key
OPENAI_MODEL=gpt-3.5-turbo          # Model name (gpt-3.5-turbo, gpt-4, etc.)
```

**Notes**:

- OpenAI is **optional** if Ollama is available
- Fallback activates automatically on Ollama failure
- API costs apply when fallback is used

## Provider Selection & Fallback Logic

### Primary Provider: Ollama

When `LLM_PROVIDER=ollama`:

1. Attempt Ollama inference at `OLLAMA_HOST`
2. On failure (timeout, connection error), fallback to OpenAI if `OPENAI_API_KEY` is set
3. If both fail, raise exception and emit ERROR event

### Primary Provider: OpenAI

When `LLM_PROVIDER=openai`:

1. Attempt OpenAI inference
2. On failure, attempt Ollama if reachable
3. If both fail, raise exception and emit ERROR event

### Fallback Triggers

Automatic fallback occurs on:

- Connection timeout (exceeds `LLM_TIMEOUT`)
- Service unavailable (HTTP 503)
- Model not found (Ollama only)
- API rate limits (OpenAI only)
- Network errors

## Usage Examples

### Basic Chat (Normal Mode)

```python
from utils.chat_openai import chat

# Invokes LLM with persona, personality, and chat history
response = chat(
    user="What's the best way to mix vocals?",
    user_id="123456789",
    chat_history=[
        {"input": "Tell me about mastering", "response": "Mastering is..."}
    ]
)
```

**Behind the scenes**:

- Loads user profile from MongoDB
- Applies active persona (bunny, kitten, etc.)
- Uses personality temperature setting
- Routes through `llm_client.chat()`
- Emits `LLM.INFERENCE` event with provider, latency, success status

### Code Mode (GPT-4 Preferred)

```python
from utils.chat_openai import chat_gpt4

# Optimized for code generation/debugging
response = chat_gpt4(
    user="Write a Python function to calculate BPM",
    user_id="123456789",
    chat_history=[]
)
```

**Behavior**:

- Uses `gpt-4` model hint (falls back to Ollama if OpenAI unavailable)
- Temperature set to 0 for deterministic output
- Prefixes response with `[Code Abby]:`

### Summarization

```python
from utils.chat_openai import summarize

# Summarize chat session for context carryover
summary = summarize(chat_session=[
    {"input": "How do I...", "response": "You can..."},
    {"input": "Thanks!", "response": "Happy to help!"}
])
```

**Behavior**:

- Max 300 tokens
- Temperature 0 for consistency
- Used by chatbot to generate session summaries on dismissal

### Analysis

```python
from utils.chat_openai import analyze

# Detailed feedback for user submissions
analysis = analyze(
    user="Alice",
    chat_session="[submission content]"
)
```

**Behavior**:

- Max 3000 tokens for detailed analysis
- Temperature 0.3 for balanced creativity/accuracy
- Provides actionable recommendations

## TDOS Event Emission

All LLM operations emit `LLM.INFERENCE` events to `shared/logs/events.jsonl`:

### Success Event Example

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-ABC123",
  "event_type": "LLM.INFERENCE",
  "timestamp": "2025-12-29T14:30:00.123Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:NONE",
  "invoker_subject_id": "SUBJECT:DISCORD-USER-123456789",
  "payload": {
    "provider": "ollama",
    "model": "llama3",
    "request_type": "chat",
    "prompt_length": 250,
    "latency_ms": 1200,
    "token_count": null,
    "success": true
  }
}
```

### Failure Event Example

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-ABC124",
  "event_type": "LLM.INFERENCE",
  "timestamp": "2025-12-29T14:30:05.456Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:NONE",
  "invoker_subject_id": "SUBJECT:DISCORD-USER-123456789",
  "payload": {
    "provider": "ollama",
    "model": "llama3",
    "request_type": "chat",
    "prompt_length": 250,
    "latency_ms": 30000,
    "token_count": null,
    "success": false
  }
}
```

Followed by an `ERROR` event:

```json
{
  "schema_version": "tdos.event.v1",
  "event_id": "EVT-ABBY-20251229-ABC125",
  "event_type": "ERROR",
  "timestamp": "2025-12-29T14:30:05.457Z",
  "agent_subject_id": "AGENT:ABBY-DISCORD",
  "machine_subject_id": "MACHINE:TSERVER",
  "tenant_id": "TENANT:BREEZE_CLUB",
  "job_id": "JOB:NONE",
  "invoker_subject_id": "AGENT:ABBY-DISCORD",
  "payload": {
    "error_type": "ConnectionError",
    "message": "Failed to connect to Ollama at http://localhost:11434",
    "recovery_action": "LLM fallback exhausted"
  }
}
```

## Troubleshooting

### Ollama Connection Issues

**Symptom**: `ConnectionError: Failed to connect to Ollama`

**Solutions**:

1. Verify Ollama is running: `curl http://localhost:11434/api/tags`
2. Check firewall rules allowing port 11434
3. Ensure model is pulled: `ollama pull llama3`
4. Verify `OLLAMA_HOST` environment variable
5. Check logs: `journalctl -u ollama` (Linux) or Ollama app logs (Windows)

### OpenAI Fallback Not Triggering

**Symptom**: Bot fails without trying OpenAI

**Solutions**:

1. Verify `OPENAI_API_KEY` is set in `.env`
2. Check API key validity at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
3. Ensure sufficient OpenAI credits/quota
4. Review `shared/logs/events.jsonl` for ERROR events

### Slow Response Times

**Symptom**: Bot takes >10 seconds to respond

**Solutions**:

1. **Ollama**: Use smaller model (e.g., `llama3:8b` instead of `llama3:70b`)
2. **Ollama**: Enable GPU acceleration (CUDA/ROCm)
3. **OpenAI**: Switch to `gpt-3.5-turbo` instead of `gpt-4`
4. Increase `LLM_TIMEOUT` if legitimate slow inference
5. Check system resources (CPU/RAM usage)

### Persona Not Applied

**Symptom**: Bot responds without persona traits

**Solutions**:

1. Verify active persona is set: `/admin persona list`
2. Check MongoDB `Admin` database → `Persona` collection
3. Ensure `get_persona()` returns valid document
4. Review `utils/chat_openai.py` system message construction

## Performance Tuning

### Ollama Optimization

```bash
# Use quantized models for speed
ollama pull llama3:8b-q4_0  # 4-bit quantization

# Configure Ollama for multi-threading
export OLLAMA_NUM_THREADS=8

# GPU acceleration (if available)
# CUDA automatically detected on Linux/Windows with NVIDIA GPU
```

### Temperature Settings

Controlled via MongoDB `Admin` database → `Personality` collection:

- **0.0**: Deterministic, factual (code mode)
- **0.3**: Balanced (analysis)
- **0.6**: Default (chat)
- **0.9**: Creative, varied responses

### Context Window

- Ollama: Model-dependent (llama3 = 4096 tokens)
- OpenAI: gpt-3.5-turbo = 4096, gpt-4 = 8192
- Chat history limited to last 4 messages (normal) or 8 (code mode)

## Migration from Legacy OpenAI-only

**Before** (legacy `utils/chat_openai.py`):

```python
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")
response = openai.ChatCompletion.create(model="gpt-3.5-turbo", ...)
```

**After** (current LLM abstraction):

```python
from abby-core.llm.llm_client import LLMClient
llm_client = LLMClient()
response = llm_client.chat(messages, request_type="chat", ...)
```

**Compatibility**: `utils/chat_openai.py` maintains legacy function signatures (`chat()`, `summarize()`, `analyze()`, `chat_gpt4()`) but routes through `LLMClient` internally. No breaking changes for existing code.

## Security Considerations

- **API Keys**: Never commit `.env` to version control
- **OpenAI Costs**: Monitor usage at [platform.openai.com/usage](https://platform.openai.com/usage)
- **Ollama Exposure**: Do NOT expose Ollama API to public internet without authentication
- **Prompt Injection**: User inputs are NOT sanitized; avoid executing generated code without review
- **TDOS Events**: Event logs contain prompt lengths but NOT full prompt text (privacy-preserving)

## Future Enhancements

Planned improvements (Phase 5+):

- [ ] Streaming responses for long generations
- [ ] Token counting for cost tracking (OpenAI)
- [ ] Prompt caching for repeated queries
- [ ] Multi-model routing (e.g., code→codellama, chat→llama3)
- [ ] RAG integration for context-augmented responses
- [ ] Fine-tuning support for domain-specific models

## References

- **LLM Client Implementation**: [abby-core/llm/llm_client.py](../abby-core/llm/llm_client.py)
- **Legacy Wrapper**: [utils/chat_openai.py](../utils/chat_openai.py)
- **TDOS Events**: [abby-core/utils/tdos_events.py](../abby-core/utils/tdos_events.py)
- **PLAN_ABBY.md Section 7**: LLM Abstraction design rationale
- **Ollama Documentation**: [github.com/ollama/ollama](https://github.com/ollama/ollama)
- **OpenAI API Docs**: [platform.openai.com/docs](https://platform.openai.com/docs)

## Support

For issues or questions:

1. Check TDOS event logs: `shared/logs/events.jsonl`
2. Review bot logs: `LOG_FILE_PATH` (default: `shared/logs/abby.log`)
3. Test LLM client directly: `python -c "from abby-core.llm.llm_client import LLMClient; print(LLMClient().chat([{'role':'user','content':'test'}]))"`
4. Report bugs with event_id from failure event
