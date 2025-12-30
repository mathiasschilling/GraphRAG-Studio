import { apiClient } from './client';
import type { VectorDatabase } from '../types/databases';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export interface CreateDatabasePayload {
  name: string;
  files: FileList;
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;
}

async function createDatabase(payload: CreateDatabasePayload): Promise<VectorDatabase> {
  const form = new FormData();
  form.append('name', payload.name);
  Array.from(payload.files).forEach((file) => {
    form.append('files', file);
  });
  if (payload.chunk_size !== undefined) {
    form.append('chunk_size', String(payload.chunk_size));
  }
  if (payload.chunk_overlap !== undefined) {
    form.append('chunk_overlap', String(payload.chunk_overlap));
  }
  if (payload.embedding_model) {
    form.append('embedding_model', payload.embedding_model);
  }

  const response = await fetch(`${API_BASE}/databases`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Request failed');
  }
  return (await response.json()) as VectorDatabase;
}

export const databasesApi = {
  list: () => apiClient.get<VectorDatabase[]>('/databases'),
  get: (id: string) => apiClient.get<VectorDatabase>(`/databases/${id}`),
  create: (payload: CreateDatabasePayload) => createDatabase(payload),
  remove: (id: string) => apiClient.delete(`/databases/${id}`),
};
