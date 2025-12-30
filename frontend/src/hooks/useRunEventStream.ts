import { useEffect, useRef } from 'react';

import type { RunEvent } from '../types/runs';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function useRunEventStream(
  runId: string | null,
  onEvent: (event: RunEvent) => void,
  onTerminal?: (event: RunEvent) => void,
) {
  const lastSequenceRef = useRef(-1);
  const onEventRef = useRef(onEvent);
  const onTerminalRef = useRef(onTerminal);

  useEffect(() => {
    // Reset sequence tracking whenever a new run is observed so polling does not
    // filter out the fresh event stream using stale sequence numbers from a
    // previous run.
    lastSequenceRef.current = -1;
  }, [runId]);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onTerminalRef.current = onTerminal;
  }, [onTerminal]);

  useEffect(() => {
    if (!runId) return undefined;

    let pollTimer: number | null = null;
    const streamUrl = `${API_BASE}/runs/${runId}/events`;

    const startPolling = () => {
      pollTimer = window.setInterval(async () => {
        try {
          const response = await fetch(`${streamUrl}?after=${lastSequenceRef.current}`);
          const events = (await response.json()) as RunEvent[];
          events.forEach((event) => {
            lastSequenceRef.current = Math.max(lastSequenceRef.current, event.sequence);
            onEventRef.current?.(event);
            if (onTerminalRef.current && ['run_completed', 'run_failed'].includes(event.status)) {
              onTerminalRef.current(event);
              if (pollTimer) window.clearInterval(pollTimer);
            }
          });
        } catch (err) {
          console.error('Failed to poll run events', err);
        }
      }, 500);
    };

    const source = new EventSource(streamUrl);

    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as RunEvent;
      lastSequenceRef.current = Math.max(lastSequenceRef.current, event.sequence);
      onEventRef.current?.(event);
      if (onTerminalRef.current && ['run_completed', 'run_failed'].includes(event.status)) {
        onTerminalRef.current(event);
      }
    };

    source.onerror = () => {
      source.close();
      startPolling();
    };

    return () => {
      source.close();
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
    };
  }, [runId]);
}
