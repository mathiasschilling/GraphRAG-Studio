import asyncio
import os

import httpx

from app.config import get_settings
from app.services.ollama import (
    OllamaClient,
    OllamaResponse,
    call_ollama_generate,
    list_ollama_models,
)


def _set_stub(value: str):
    previous = os.environ.get("GRAPHRAG_USE_LLM_STUB")
    os.environ["GRAPHRAG_USE_LLM_STUB"] = value
    get_settings.cache_clear()
    return previous


def _restore_stub(previous):
    if previous is None:
        os.environ.pop("GRAPHRAG_USE_LLM_STUB", None)
    else:
        os.environ["GRAPHRAG_USE_LLM_STUB"] = previous
    get_settings.cache_clear()


def test_call_ollama_success(monkeypatch):
    prev = _set_stub("false")

    async def fake_generate(self, *, model: str, prompt: str, options=None):
        return OllamaResponse(model=model, response=f"live:{prompt}", raw={"ok": True})

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)

    try:
        result = asyncio.run(call_ollama_generate("model-a", "hello"))
        assert result == "live:hello"
    finally:
        _restore_stub(prev)


def test_call_ollama_fallback(monkeypatch):
    prev = _set_stub("false")

    async def fake_generate(self, *, model: str, prompt: str, options=None):
        request = httpx.Request("POST", "http://localhost:11434/api/generate")
        response = httpx.Response(status_code=404, request=request)
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr(OllamaClient, "generate", fake_generate)

    try:
        result = asyncio.run(call_ollama_generate("model-b", "prompt"))
        assert result.startswith("[stub:model-b]")
        assert "Ollama call failed" in result
        assert "model 'model-b' is pulled" in result
    finally:
        _restore_stub(prev)


def test_list_ollama_models_success(monkeypatch):
    prev = _set_stub("false")

    async def fake_list(self):
        return ["mistral", "qwen"]

    monkeypatch.setattr(OllamaClient, "list_models", fake_list)

    try:
        models = asyncio.run(list_ollama_models())
        assert models == ["mistral", "qwen"]
    finally:
        _restore_stub(prev)


def test_list_ollama_models_stubbed(monkeypatch):
    prev = _set_stub("true")

    try:
        models = asyncio.run(list_ollama_models())
        assert "llama3" in models
    finally:
        _restore_stub(prev)
