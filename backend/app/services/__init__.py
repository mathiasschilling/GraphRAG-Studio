"""Service layer helpers for external integrations (e.g., Ollama)."""

from .ollama import OllamaClient, call_ollama_embeddings, call_ollama_generate, list_ollama_models

__all__ = ["OllamaClient", "call_ollama_embeddings", "call_ollama_generate", "list_ollama_models"]
