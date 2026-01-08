export type VectorDatabaseStatus = 'pending' | 'indexing' | 'ready' | 'failed';

export interface VectorDatabase {
  id: string;
  name: string;
  status: VectorDatabaseStatus | string;
  embedding_model?: string | null;
  chunk_size?: number | null;
  chunk_overlap?: number | null;
  created_at: string;
  document_count: number;
  chunk_count: number;
}

export interface DatabaseDocument {
  id: string;
  database_id: string;
  filename: string;
  mime_type?: string | null;
  size?: number | null;
  created_at: string;
  chunk_count: number;
}

export interface DatabaseChunk {
  id: string;
  database_id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  created_at: string;
}
