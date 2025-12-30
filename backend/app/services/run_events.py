from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List


@dataclass
class RunEvent:
    run_id: str
    node_id: str | None
    status: str
    timestamp: str
    sequence: int
    error: str | None = None


class RunEventBroker:
    """In-memory event bus for streaming per-run progress updates."""

    def __init__(self) -> None:
        self._events: Dict[str, List[RunEvent]] = defaultdict(list)
        self._queues: Dict[str, asyncio.Queue[RunEvent]] = defaultdict(asyncio.Queue)

    def _next_sequence(self, run_id: str) -> int:
        return len(self._events[run_id])

    async def publish(self, run_id: str, payload: Dict[str, str]) -> RunEvent:
        event = RunEvent(
            run_id=run_id,
            node_id=payload.get("node_id"),
            status=payload.get("status", "unknown"),
            timestamp=payload.get("timestamp")
            or datetime.now(timezone.utc).isoformat(),
            sequence=self._next_sequence(run_id),
            error=payload.get("error"),
        )
        self._events[run_id].append(event)
        await self._queues[run_id].put(event)
        return event

    def history(self, run_id: str, after: int = -1) -> List[RunEvent]:
        return [event for event in self._events.get(run_id, []) if event.sequence > after]

    async def listen(
        self, run_id: str, after: int = -1, stop_on_terminal: bool = True
    ) -> AsyncGenerator[RunEvent, None]:
        queue = self._queues[run_id]
        last_sent = after

        # replay existing events first
        for event in self.history(run_id, after=after):
            last_sent = event.sequence
            yield event

        while True:
            event = await queue.get()
            if event.sequence <= last_sent:
                continue

            yield event
            last_sent = event.sequence
            if stop_on_terminal and event.status in {"run_completed", "run_failed"}:
                break


run_event_broker = RunEventBroker()
