import { apiClient } from './client';
import type { RunRecord } from '../types/nodes';
import type { RunEvent } from '../types/runs';

export const runsApi = {
  get: (id: string) => apiClient.get<RunRecord>(`/runs/${id}`),
  list: () => apiClient.get<RunRecord[]>(`/runs`),
  events: (id: string, after?: number) =>
    apiClient.get<RunEvent[]>(after !== undefined ? `/runs/${id}/events?after=${after}` : `/runs/${id}/events`),
};
