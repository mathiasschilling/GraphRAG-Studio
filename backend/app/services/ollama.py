from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Dict

import httpx
from httpx import HTTPStatusError

from ..logging_config import setup_logging

from ..config import get_settings


@dataclass
class OllamaResponse:
    model: str
    response: str
    raw: Dict[str, Any]


class OllamaClient:
    """Minimal async client for Ollama's /api/generate endpoint."""

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def generate(self, *, model: str, prompt: str, options: Dict[str, Any] | None = None) -> OllamaResponse:
        payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if options:
            payload["options"] = options

        async with httpx.AsyncClient(base_url=self._base_url, timeout=30) as client:
            resp = await client.post("/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return OllamaResponse(model=data.get("model", model), response=data.get("response", ""), raw=data)

    async def list_models(self) -> list[str]:
        """Return the available models from Ollama's /api/tags endpoint."""

        async with httpx.AsyncClient(base_url=self._base_url, timeout=10) as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return []
            models: list[str] = []
            for entry in data.get("models", []):
                if isinstance(entry, dict):
                    name = entry.get("model") or entry.get("name")
                    if name:
                        models.append(name)
            return models

    async def embeddings(self, *, model: str, prompt: str) -> list[float]:
        """Return embeddings from Ollama's /api/embeddings endpoint."""

        payload: Dict[str, Any] = {"model": model, "prompt": prompt}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30) as client:
            resp = await client.post("/api/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if not isinstance(embedding, list):
                return []
            return [float(value) for value in embedding]


async def call_ollama_generate(model: str, prompt: str) -> str:
    """Call Ollama or fall back to a local stub if disabled in settings."""

    settings = get_settings()
    logger = setup_logging()

    # Respect the explicit stub toggle for tests or offline development.
    if getattr(settings, "use_llm_stub", False):
        return f"[{model}] {prompt}".strip()

    client = OllamaClient(settings.ollama_base_url)

    try:
        result = await client.generate(model=model, prompt=prompt)
        return result.response
    except Exception as exc:  # pragma: no cover - fallback path
        # If Ollama is unreachable or errors, fall back to a deterministic stub
        # so flows can still execute while emitting a warning to the logs.
        # Include the exception detail in the stubbed message to clarify why
        # the real model was not used (e.g., Ollama daemon not running, wrong
        # base URL, or missing model on the server).
        detail: str | None = None
        if isinstance(exc, HTTPStatusError) and exc.response is not None:
            # Bubble up any server-provided error text to help users spot
            # missing models (Ollama returns 404 for that case) or other
            # validation errors without requiring them to dig through logs.
            try:
                data = exc.response.json()
                if isinstance(data, dict):
                    detail = data.get("error") or data.get("message")
                if detail is None:
                    detail = str(data)
            except ValueError:
                detail = exc.response.text
        reason = detail or str(exc)

        logger.warning(
            "Falling back to stubbed LLM response because Ollama call failed",
            extra={
                "model": model,
                "error": reason,
                "ollama_base_url": settings.ollama_base_url,
            },
            exc_info=exc,
        )

        hints = (
            f"(Ollama call failed: {reason}. "
            f"Verify the Ollama daemon is running at {settings.ollama_base_url} "
            f"and that the model '{model}' is pulled.)"
        )
        return f"[stub:{model}] {prompt}\n\n{hints}".strip()


def _stub_embedding(model: str, text: str, dimensions: int = 384) -> list[float]:
    """Create a deterministic embedding vector without external dependencies."""

    seed = f"{model}:{text}".encode("utf-8", "ignore")
    digest = hashlib.sha256(seed).digest()
    values: list[float] = []
    current = digest
    while len(values) < dimensions:
        for byte in current:
            values.append((byte / 127.5) - 1.0)
            if len(values) >= dimensions:
                break
        current = hashlib.sha256(current).digest()
    return values[:dimensions]


async def call_ollama_embeddings(model: str, text: str) -> list[float]:
    """Call Ollama embeddings or fall back to a deterministic stub."""

    settings = get_settings()
    logger = setup_logging()

    if getattr(settings, "use_llm_stub", False):
        return _stub_embedding(model, text)

    client = OllamaClient(settings.ollama_base_url)

    try:
        return await client.embeddings(model=model, prompt=text)
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning(
            "Falling back to stubbed embeddings because Ollama call failed",
            extra={
                "model": model,
                "error": str(exc),
                "ollama_base_url": settings.ollama_base_url,
            },
            exc_info=exc,
        )
        return _stub_embedding(model, text)


async def list_ollama_models() -> list[str]:
    """List locally available Ollama models or fall back to defaults when stubbed."""

    settings = get_settings()
    logger = setup_logging()

    # Prefer a deterministic set when stubbing to avoid HTTP calls during tests.
    if getattr(settings, "use_llm_stub", False):
        return ["llama3", "qwen2:0.5b"]

    client = OllamaClient(settings.ollama_base_url)
    try:
        return await client.list_models()
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning(
            "Failed to list Ollama models; returning empty list",
            extra={"error": str(exc), "ollama_base_url": settings.ollama_base_url},
            exc_info=exc,
        )
        return []
