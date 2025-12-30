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
