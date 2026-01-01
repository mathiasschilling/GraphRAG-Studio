from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import nodes  # noqa: F401  # ensure node types are registered
from .api.routes_databases import router as databases_router
from .api.routes_flows import router as flows_router
from .api.routes_models import router as models_router
from .api.routes_runs import router as runs_router
from .api.schemas import RunRequest, RunResponse
from .core.executor import execute_graph
from .config import get_settings
from .logging_config import setup_logging
from .persistence.db import init_db

settings = get_settings()

app = FastAPI(title="GraphRAG Studio")

# Attach permissive CORS middleware so the Vite dev server (or other frontends)
# can reach the API without additional proxying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize logging and database connections when the process starts."""
    setup_logging()
    init_db()


@app.get("/health")
async def health() -> dict:
    """Simple liveness probe endpoint."""
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
async def run_flow(request: RunRequest) -> RunResponse:
    """Execute an ad-hoc graph payload without persisting it to storage."""
    result = await execute_graph(request.graph.to_core(), request.input)
    return RunResponse(outputs=result.outputs, key_usage=result.key_usage)


app.include_router(flows_router)
app.include_router(databases_router)
app.include_router(models_router)
app.include_router(runs_router)
