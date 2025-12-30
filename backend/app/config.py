from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for API, persistence, and model connectivity."""
    database_url: str = "sqlite:///./app.db"
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    chunk_size: int = 500
    chunk_overlap: int = 100
    storage_path: str = "./storage"
    # When false, LLM nodes call the configured Ollama instance. Set to true to stub responses.
    use_llm_stub: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_prefix = "GRAPHRAG_"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance to avoid re-parsing env files."""
    return Settings()
