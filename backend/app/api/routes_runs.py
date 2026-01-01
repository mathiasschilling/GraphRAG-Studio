from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..persistence.db import SessionLocal
from ..persistence.models import Run
from ..services.run_events import run_event_broker
from .schemas import RunRead

router = APIRouter(prefix="/runs", tags=["runs"])


def get_db():
    """Yield a database session for run retrieval endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=List[RunRead])
def list_runs(db: Session = Depends(get_db)) -> List[RunRead]:
    """List recent runs so the UI can show a history view."""
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [
        RunRead(
            id=run.id,
            flow_id=run.flow_id,
            status=run.status,
            input_payload=run.input_payload,
            output_payload=run.output_payload,
            error=run.error,
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            node_outputs=run.node_outputs,
            key_usage=run.key_usage,
        )
        for run in runs
    ]


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunRead:
    """Fetch a single run with metadata and per-node outputs."""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return RunRead(
        id=run.id,
        flow_id=run.flow_id,
        status=run.status,
        input_payload=run.input_payload,
        output_payload=run.output_payload,
        error=run.error,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        node_outputs=run.node_outputs,
        key_usage=run.key_usage,
    )


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str, request: Request, after: int = -1):
    """Return progressive node status events for a run.

    When the client requests ``text/event-stream`` the response is an SSE stream.
    Otherwise, a JSON array of events newer than ``after`` is returned for
    polling-friendly access.
    """

    wants_stream = "text/event-stream" in request.headers.get("accept", "")

    if wants_stream:
        async def event_generator():
            async for event in run_event_broker.listen(run_id, after=after):
                payload = json.dumps(event.__dict__)
                yield f"data: {payload}\n\n"
                if event.status in {"run_completed", "run_failed"}:
                    break
                if await request.is_disconnected():
                    break

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return [event.__dict__ for event in run_event_broker.history(run_id, after=after)]
