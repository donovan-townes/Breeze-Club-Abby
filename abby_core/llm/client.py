import os
import time
import logging
from typing import Any, Dict, List, Optional

import requests

# TDOS event emission
from abby_core.observability.telemetry import emit_llm_inference, emit_error

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    openai = None

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Provider-agnostic LLM client with Ollama primary and OpenAI fallback.
    Uses env-driven configuration and emits TDOS LLM.INFERENCE events.
    
    Supports two-tier architecture:
    - High priority (user-facing): Fast provider only (OpenAI)
    - Low priority (background): Try all available providers
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        ollama_host: Optional[str] = None,
        ollama_model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.openai_model = openai_model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.timeout = timeout or float(os.getenv("LLM_TIMEOUT", "30"))
        
        # Provider availability cache (checked once at startup)
        self._ollama_available: Optional[bool] = None
        self._check_provider_availability()

    def _check_provider_availability(self) -> None:
        """Check if Ollama is available at startup. Run once to avoid repeated 404s."""
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=2)
            self._ollama_available = response.status_code == 200
            if self._ollama_available:
                logger.info(f"[🦙] Ollama available at {self.ollama_host}")
            else:
                logger.info(f"[🦙] Ollama responded with status {response.status_code}, marking unavailable")
        except Exception:
            self._ollama_available = False
            logger.info(f"[🦙] Ollama not available at {self.ollama_host}, using OpenAI only")

    # Public API -------------------------------------------------------------
    def chat(
        self,
        messages: List[Dict[str, str]],
        request_type: str = "generate",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model_hint: Optional[str] = None,
        invoker_subject_id: Optional[str] = None,
        job_id: Optional[str] = None,
        task_priority: str = "normal",
    ) -> str:
        """
        Chat/generation entrypoint. Attempts primary provider first, then fallback.
        Emits TDOS LLM.INFERENCE events for both success and failure.
        
        Args:
            task_priority: "high" = user-facing (fast only), "normal" = background (try all)
        """
        providers = self._provider_sequence(task_priority)
        last_error: Optional[Exception] = None

        for provider in providers:
            model_used = model_hint or (self.ollama_model if provider == "ollama" else self.openai_model)
            start = time.perf_counter()
            try:
                if provider == "ollama":
                    text = self._chat_ollama(messages, temperature, max_tokens, model_used)
                elif provider == "openai":
                    text = self._chat_openai(messages, temperature, max_tokens, model_used)
                else:
                    raise ValueError(f"Unsupported provider '{provider}'")

                latency_ms = int((time.perf_counter() - start) * 1000)
                prompt_length = self._prompt_length(messages)
                emit_llm_inference(
                    provider=provider,
                    model=model_used,
                    request_type=request_type,
                    prompt_length=prompt_length,
                    latency_ms=latency_ms,
                    token_count=None,
                    success=True,
                    job_id=job_id,
                    invoker_subject_id=invoker_subject_id,
                )
                return text
            except Exception as exc:  # capture and try fallback
                latency_ms = int((time.perf_counter() - start) * 1000)
                prompt_length = self._prompt_length(messages)
                emit_llm_inference(
                    provider=provider,
                    model=model_used,
                    request_type=request_type,
                    prompt_length=prompt_length,
                    latency_ms=latency_ms,
                    token_count=None,
                    success=False,
                    job_id=job_id,
                    invoker_subject_id=invoker_subject_id,
                )
                last_error = exc
                logger.warning("LLM provider '%s' failed: %s", provider, exc)

        # If we reach here, all providers failed
        if last_error:
            emit_error(
                error_type=last_error.__class__.__name__,
                message=str(last_error),
                recovery_action="LLM fallback exhausted",
            )
            raise last_error
        raise RuntimeError("LLM inference failed with unknown error")

    def summarize(self, text: str, max_tokens: int = 300, invoker_subject_id: Optional[str] = None) -> str:
        """Generate a summary of text or chat history. Background task."""
        messages = [
            {"role": "system", "content": "Summarize this chat session between Abby and the user. Focus on the key topics discussed and any important details or context that should be remembered for future conversations."},
            {"role": "user", "content": f"Please summarize this conversation:\n\n{text}"},
        ]
        return self.chat(
            messages,
            request_type="summarize",
            temperature=0,
            max_tokens=max_tokens,
            invoker_subject_id=invoker_subject_id,
            task_priority="normal",  # Background task: can use slower models
        )

    # Internal helpers ------------------------------------------------------
    def _provider_sequence(self, task_priority: str = "normal") -> List[str]:
        """
        Determine provider sequence based on availability and task priority.
        
        High priority (user-facing): Use OpenAI only for speed
        Normal priority (background): Try all available providers
        """
        # High priority tasks: fast provider only
        if task_priority == "high":
            if self.openai_api_key:
                return ["openai"]
            # Fallback if no OpenAI but Ollama available
            if self._ollama_available:
                return ["ollama"]
            return ["openai"]  # Will fail but emit proper error
        
        # Normal priority: try available providers in sequence
        if self.provider == "ollama":
            seq = []
            if self._ollama_available:
                seq.append("ollama")
            if self.openai_api_key:
                seq.append("openai")
            return seq if seq else ["ollama"]  # Fallback to try anyway
        
        if self.provider == "openai":
            seq = ["openai"]
            # Allow reverse fallback if Ollama is confirmed available
            if self._ollama_available:
                seq.append("ollama")
            return seq
        
        return [self.provider]

    def _chat_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: str,
    ) -> str:
        url = self.ollama_host.rstrip("/") + "/api/chat"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        options: Dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if options:
            payload["options"] = options

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            if data.get("message") and data["message"].get("content"):
                return data["message"]["content"]
            if data.get("output"):
                return data["output"]
        raise RuntimeError("Ollama response missing content")

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: str,
    ) -> str:
        if openai is None:
            raise RuntimeError("openai package not installed")
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        # OpenAI v1.0+ API
        client = openai.OpenAI(api_key=self.openai_api_key, timeout=self.timeout)
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = client.chat.completions.create(**kwargs)
        if not response.choices:
            raise RuntimeError("OpenAI response missing choices")
        message = response.choices[0].message
        if not message or not message.content:
            raise RuntimeError("OpenAI response missing message content")
        return message.content

    @staticmethod
    def _prompt_length(messages: List[Dict[str, str]]) -> int:
        return sum(len(m.get("content", "")) for m in messages)
