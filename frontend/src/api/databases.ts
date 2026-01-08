import { apiClient } from './client';
import type { DatabaseChunk, DatabaseDocument, VectorDatabase } from '../types/databases';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export interface CreateDatabasePayload {
  name: string;
  files: FileList;
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;
}

export interface AddDocumentsPayload {
  files: FileList;
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

async function addDocuments(databaseId: string, payload: AddDocumentsPayload): Promise<DatabaseDocument[]> {
  const form = new FormData();
  Array.from(payload.files).forEach((file) => {
    form.append('files', file);
  });

  const response = await fetch(`${API_BASE}/databases/${databaseId}/documents`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Request failed');
  }
  return (await response.json()) as DatabaseDocument[];
}

function listChunks(
  databaseId: string,
  options?: { documentId?: string; limit?: number; offset?: number }
): Promise<DatabaseChunk[]> {
  const params = new URLSearchParams();
  if (options?.documentId) {
    params.append('document_id', options.documentId);
  }
  if (options?.limit !== undefined) {
    params.append('limit', String(options.limit));
  }
  if (options?.offset !== undefined) {
    params.append('offset', String(options.offset));
  }
  const query = params.toString();
  return apiClient.get<DatabaseChunk[]>(`/databases/${databaseId}/chunks${query ? `?${query}` : ''}`);
}

export const databasesApi = {
  list: () => apiClient.get<VectorDatabase[]>('/databases'),
  get: (id: string) => apiClient.get<VectorDatabase>(`/databases/${id}`),
  create: (payload: CreateDatabasePayload) => createDatabase(payload),
  addDocuments: (databaseId: string, payload: AddDocumentsPayload) => addDocuments(databaseId, payload),
  listDocuments: (databaseId: string) => apiClient.get<DatabaseDocument[]>(`/databases/${databaseId}/documents`),
  listChunks,
  deleteDocument: (databaseId: string, documentId: string) =>
    apiClient.delete(`/databases/${databaseId}/documents/${documentId}`),
  deleteChunk: (databaseId: string, chunkId: string) =>
    apiClient.delete(`/databases/${databaseId}/chunks/${chunkId}`),
  remove: (id: string) => apiClient.delete(`/databases/${id}`),
};
