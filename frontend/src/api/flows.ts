import { apiClient } from './client';
import type { FlowGraph, FlowRead, RunRecord } from '../types/nodes';

export interface CreateFlowPayload {
  name: string;
  description?: string;
  graph: FlowGraph;
}

export const flowsApi = {
  list: () => apiClient.get<FlowRead[]>('/flows'),
  get: (id: string) => apiClient.get<FlowRead>(`/flows/${id}`),
  create: (payload: CreateFlowPayload) => apiClient.post<FlowRead>('/flows', payload),
  remove: (id: string) => apiClient.delete(`/flows/${id}`),
  save: (id: string, payload: Partial<FlowRead> & { graph: FlowGraph }) =>
    apiClient.put<FlowRead>(`/flows/${id}`, payload),
  run: (id: string, input: Record<string, unknown>) => apiClient.post<RunRecord>(`/flows/${id}/run`, { input }),
};
