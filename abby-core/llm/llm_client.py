import os
import time
import logging
from typing import Any, Dict, List, Optional

import requests

# TDOS event emission
from utils.tdos_events import emit_llm_inference, emit_error

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    openai = None

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Provider-agnostic LLM client with Ollama primary and OpenAI fallback.
    Uses env-driven configuration and emits TDOS LLM.INFERENCE events.
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
    ) -> str:
        """
        Chat/generation entrypoint. Attempts primary provider first, then fallback.
        Emits TDOS LLM.INFERENCE events for both success and failure.
        """
        providers = self._provider_sequence()
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
        messages = [
            {"role": "system", "content": "Summarize this chat session between Abby and the user"},
            {"role": "assistant", "content": text},
        ]
        return self.chat(
            messages,
            request_type="summarize",
            temperature=0,
            max_tokens=max_tokens,
            invoker_subject_id=invoker_subject_id,
        )

    # Internal helpers ------------------------------------------------------
    def _provider_sequence(self) -> List[str]:
        # Primary provider first; fallback to the other if configured
        if self.provider == "ollama":
            return ["ollama", "openai"] if self.openai_api_key else ["ollama"]
        if self.provider == "openai":
            seq = ["openai"]
            seq.append("ollama")  # allow reverse fallback if Ollama is running
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

        openai.api_key = self.openai_api_key
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": self.timeout,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = openai.ChatCompletion.create(**kwargs)
        choices = response.get("choices")
        if not choices:
            raise RuntimeError("OpenAI response missing choices")
        message = choices[0].get("message")
        if not message or not message.get("content"):
            raise RuntimeError("OpenAI response missing message content")
        return message["content"]

    @staticmethod
    def _prompt_length(messages: List[Dict[str, str]]) -> int:
        return sum(len(m.get("content", "")) for m in messages)
