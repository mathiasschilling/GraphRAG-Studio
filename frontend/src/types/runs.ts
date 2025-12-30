import { NodeRunStatus } from './nodes';

export type RunPhase = 'idle' | 'running' | 'completed' | 'failed';

export interface RunEvent {
  run_id: string;
  node_id: string | null;
  status: 'run_started' | 'started' | 'completed' | 'skipped' | 'run_completed' | 'run_failed';
  timestamp: string;
  sequence: number;
  error?: string | null;
}

export type NodeStatusMap = Record<string, NodeRunStatus>;
