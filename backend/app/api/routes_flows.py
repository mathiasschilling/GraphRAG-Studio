from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..core.executor import execute_graph
from ..core.graph import flow_graph_from_dict
from ..persistence.db import SessionLocal
from ..persistence.models import Flow, Run, RunStatus
from ..services.run_events import run_event_broker
from .schemas import FlowCreate, FlowGraphSchema, FlowRead, FlowUpdate, RunCreateRequest, RunRead

router = APIRouter(prefix="/flows", tags=["flows"])
logger = logging.getLogger(__name__)


def get_db():
    """Provide a scoped SQLAlchemy session for request handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
def create_flow(payload: FlowCreate, db: Session = Depends(get_db)) -> FlowRead:
    """Persist a new flow and return the hydrated schema."""
    flow = Flow(name=payload.name, graph=payload.graph.model_dump())
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return FlowRead(id=flow.id, name=flow.name, graph=payload.graph)


@router.get("", response_model=List[FlowRead])
def list_flows(db: Session = Depends(get_db)) -> List[FlowRead]:
    """Return flows ordered by recency for the list view."""
    flows = db.query(Flow).order_by(Flow.created_at.desc()).all()
    return [FlowRead(id=flow.id, name=flow.name, graph=FlowGraphSchema(**flow.graph)) for flow in flows]


@router.get("/{flow_id}", response_model=FlowRead)
def get_flow(flow_id: str, db: Session = Depends(get_db)) -> FlowRead:
    """Fetch a single flow or return 404 if it is missing."""
    flow = db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    return FlowRead(id=flow.id, name=flow.name, graph=FlowGraphSchema(**flow.graph))


@router.put("/{flow_id}", response_model=FlowRead)
def update_flow(flow_id: str, payload: FlowUpdate, db: Session = Depends(get_db)) -> FlowRead:
    """Update a flow's name or graph contents in place."""
    flow = db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    if payload.name is not None:
        flow.name = payload.name
    if payload.graph is not None:
        flow.graph = payload.graph.model_dump()

    db.add(flow)
    db.commit()
    db.refresh(flow)

    return FlowRead(id=flow.id, name=flow.name, graph=FlowGraphSchema(**flow.graph))


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_flow(flow_id: str, db: Session = Depends(get_db)) -> Response:
    """Remove a flow and its runs; callers should handle missing flows upstream."""
    flow = db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    db.delete(flow)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{flow_id}/run", response_model=RunRead)
async def run_flow(flow_id: str, payload: RunCreateRequest, db: Session = Depends(get_db)) -> RunRead:
    """Execute a stored flow while capturing metadata about the run."""
    flow = db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    now = datetime.now(timezone.utc)
    run = Run(
        flow_id=flow_id,
        input_payload=payload.input,
        status=RunStatus.PENDING,
        started_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    async def _execute_run(run_id: str, flow_graph: dict, input_payload: dict | list | str | int | float | None):
        session: Session | None = None
        run_record: Run | None = None
        try:
            session = SessionLocal()
            run_record = session.get(Run, run_id)
            if not run_record:
                return

            run_record.status = RunStatus.RUNNING
            run_record.started_at = run_record.started_at or datetime.now(timezone.utc)
            session.add(run_record)
            session.commit()
            session.refresh(run_record)

            await run_event_broker.publish(
                run_id,
                {"node_id": None, "status": "run_started", "timestamp": run_record.started_at.isoformat()},
            )

            graph = flow_graph_from_dict(flow_graph)
            result = await execute_graph(
                graph,
                input_payload,
                event_handler=lambda event: run_event_broker.publish(run_id, event),
            )

            run_record.status = RunStatus.COMPLETED
            run_record.output_payload = result.outputs
            run_record.completed_at = result.completed_at
            run_record.node_outputs = result.node_output_map()
            run_record.key_usage = result.key_usage
            await run_event_broker.publish(
                run_id,
                {
                    "node_id": None,
                    "status": "run_completed",
                    "timestamp": run_record.completed_at.isoformat(),
                },
            )
        except Exception as exc:  # pragma: no cover - general error capture
            if run_record is None and session is not None:
                run_record = session.get(Run, run_id)
            if run_record is not None:
                run_record.status = RunStatus.FAILED
                run_record.error = str(exc)
                run_record.completed_at = datetime.now(timezone.utc)
                await run_event_broker.publish(
                    run_id,
                    {
                        "node_id": None,
                        "status": "run_failed",
                        "timestamp": run_record.completed_at.isoformat(),
                        "error": str(exc),
                    },
                )
                session.add(run_record)
                session.commit()

            logger.exception("Flow run failed", extra={"flow_id": flow_id, "run_id": run_id})
        finally:
            if run_record is not None and session is not None:
                session.add(run_record)
                session.commit()
                session.refresh(run_record)
                session.close()
            elif session is not None:
                session.close()

    # mark the run as started for the response while executing asynchronously
    run.status = RunStatus.RUNNING
    db.add(run)
    db.commit()
    db.refresh(run)

    asyncio.create_task(_execute_run(run.id, flow.graph, payload.input))

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
