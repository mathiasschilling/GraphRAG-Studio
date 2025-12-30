import { createContext, useCallback, useContext, useMemo, useReducer } from 'react';
import type { ReactNode } from 'react';

import type { NodeRunStatus } from '../types/nodes';
import type { RunEvent, RunPhase } from '../types/runs';

interface RunState {
  activeRunId: string | null;
  nodeStatuses: Record<string, NodeRunStatus>;
  runPhase: RunPhase;
  lastSequence: number;
}

const initialState: RunState = {
  activeRunId: null,
  nodeStatuses: {},
  runPhase: 'idle',
  lastSequence: -1,
};

type Action =
  | { type: 'begin'; runId: string; nodeIds: string[] }
  | { type: 'register'; nodeIds: string[] }
  | { type: 'ingest'; event: RunEvent }
  | { type: 'reset' };

function statusFromEvent(event: RunEvent): NodeRunStatus | null {
  switch (event.status) {
    case 'started':
      return 'running';
    case 'completed':
      return 'done';
    case 'skipped':
      return 'skipped';
    case 'run_failed':
      return 'error';
    default:
      return null;
  }
}

function reducer(state: RunState, action: Action): RunState {
  switch (action.type) {
    case 'begin': {
      const pendingStatuses = action.nodeIds.reduce<Record<string, NodeRunStatus>>((acc, id) => {
        acc[id] = 'pending';
        return acc;
      }, {});
      return {
        activeRunId: action.runId,
        nodeStatuses: pendingStatuses,
        runPhase: 'running',
        lastSequence: -1,
      };
    }
    case 'register': {
      if (!state.activeRunId) return state;
      const merged = { ...state.nodeStatuses };
      action.nodeIds.forEach((id) => {
        if (!merged[id]) {
          merged[id] = 'pending';
        }
      });
      return { ...state, nodeStatuses: merged };
    }
    case 'ingest': {
      const { event } = action;
      if (state.activeRunId && event.run_id !== state.activeRunId) return state;

      const nodeStatuses = { ...state.nodeStatuses };
      const nextNodeStatus = statusFromEvent(event);
      if (event.node_id && nextNodeStatus) {
        nodeStatuses[event.node_id] = nextNodeStatus;
      }

      let runPhase = state.runPhase;
      let activeRunId = state.activeRunId;
      if (event.status === 'run_completed') {
        runPhase = 'completed';
        activeRunId = null;
      } else if (event.status === 'run_failed') {
        runPhase = 'failed';
        activeRunId = null;
      }

      return {
        activeRunId,
        nodeStatuses,
        runPhase,
        lastSequence: Math.max(state.lastSequence, event.sequence),
      };
    }
    case 'reset':
      return initialState;
    default:
      return state;
  }
}

interface RunStateContextValue extends RunState {
  beginRun: (runId: string, nodeIds: string[]) => void;
  registerNodes: (nodeIds: string[]) => void;
  ingestEvent: (event: RunEvent) => void;
  reset: () => void;
}

const RunStateContext = createContext<RunStateContextValue | undefined>(undefined);

export function RunStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const beginRun = useCallback((runId: string, nodeIds: string[]) => {
    dispatch({ type: 'begin', runId, nodeIds });
  }, []);

  const registerNodes = useCallback((nodeIds: string[]) => {
    dispatch({ type: 'register', nodeIds });
  }, []);

  const ingestEvent = useCallback((event: RunEvent) => {
    dispatch({ type: 'ingest', event });
  }, []);

  const reset = useCallback(() => dispatch({ type: 'reset' }), []);

  const value = useMemo(
    () => ({
      ...state,
      beginRun,
      registerNodes,
      ingestEvent,
      reset,
    }),
    [state, beginRun, registerNodes, ingestEvent, reset],
  );

  return <RunStateContext.Provider value={value}>{children}</RunStateContext.Provider>;
}

export function useRunState(): RunStateContextValue {
  const ctx = useContext(RunStateContext);
  if (!ctx) {
    throw new Error('useRunState must be used inside a RunStateProvider');
  }
  return ctx;
}
