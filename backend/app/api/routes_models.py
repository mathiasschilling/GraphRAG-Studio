from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..services import list_ollama_models

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[str])
async def list_models() -> list[str]:
    """Expose locally available Ollama models for UI selection."""

    models = await list_ollama_models()
    if models:
        return models

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No models available or Ollama unreachable",
    )
