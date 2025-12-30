import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { databasesApi } from '../api/databases';
import { flowsApi } from '../api/flows';
import type { FlowGraph } from '../types/nodes';

function defaultGraph(): FlowGraph {
  const id = crypto.randomUUID ? crypto.randomUUID() : `flow-${Date.now()}`;
  const userId = `UserInputNode-${Date.now()}`;
  const llmId = `LLMNode-${Date.now()}`;
  const finalId = `FinalAnswerNode-${Date.now()}`;

  return {
    id,
    nodes: {
      [userId]: { id: userId, type: 'UserInputNode', config: { key: 'input' }, position: { x: 240, y: 40 } },
      [llmId]: {
        id: llmId,
        type: 'LLMNode',
        config: { model: 'llama3', prompt: 'Answer the user message: {input}' },
        position: { x: 240, y: 200 },
      },
      [finalId]: { id: finalId, type: 'FinalAnswerNode', config: { key: 'response' }, position: { x: 240, y: 360 } },
    },
    edges: [
      { id: `${userId}-${llmId}-prompt`, from_node: userId, from_output: 'input', to_node: llmId, to_input: 'prompt' },
      { id: `${llmId}-${finalId}-response`, from_node: llmId, from_output: 'response', to_node: finalId, to_input: 'response' },
    ],
  };
}

export default function FlowsListPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [databaseName, setDatabaseName] = useState('');
  const [databaseFiles, setDatabaseFiles] = useState<FileList | null>(null);
  const [chunkSize, setChunkSize] = useState('500');
  const [chunkOverlap, setChunkOverlap] = useState('100');
  const [embeddingModel, setEmbeddingModel] = useState('');
  const [fileInputKey, setFileInputKey] = useState(0);

  const { data: flows, isLoading, error } = useQuery({
    queryKey: ['flows'],
    queryFn: flowsApi.list,
  });

  const { data: databases, isLoading: databasesLoading, error: databasesError } = useQuery({
    queryKey: ['databases'],
    queryFn: databasesApi.list,
  });

  const createFlow = useMutation({
    mutationFn: () => flowsApi.create({ name: 'New Flow', graph: defaultGraph() }),
    onSuccess: (flow) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      navigate(`/flows/${flow.id}`);
    },
  });

  const deleteFlow = useMutation({
    mutationFn: (id: string) => flowsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['flows'] }),
  });

  const createDatabase = useMutation({
    mutationFn: () => {
      const name = databaseName.trim();
      if (!name) {
        throw new Error('Database name is required');
      }
      if (!databaseFiles || databaseFiles.length === 0) {
        throw new Error('Please select at least one file');
      }
      const parsedChunkSize = chunkSize.trim() === '' ? undefined : Number(chunkSize);
      const parsedChunkOverlap = chunkOverlap.trim() === '' ? undefined : Number(chunkOverlap);
      return databasesApi.create({
        name,
        files: databaseFiles,
        chunk_size: parsedChunkSize !== undefined && Number.isFinite(parsedChunkSize) ? parsedChunkSize : undefined,
        chunk_overlap: parsedChunkOverlap !== undefined && Number.isFinite(parsedChunkOverlap) ? parsedChunkOverlap : undefined,
        embedding_model: embeddingModel.trim() || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] });
      setDatabaseName('');
      setDatabaseFiles(null);
      setChunkSize('500');
      setChunkOverlap('100');
      setEmbeddingModel('');
      setFileInputKey((value) => value + 1);
    },
  });

  const deleteDatabase = useMutation({
    mutationFn: (id: string) => databasesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['databases'] }),
  });

  const canCreateDatabase = Boolean(databaseName.trim() && databaseFiles && databaseFiles.length > 0);

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="card">
        <div className="flex-between">
          <div>
            <h2>Flows</h2>
            <p>Create, open, or delete flows.</p>
          </div>
          <button className="button" onClick={() => createFlow.mutate()} disabled={createFlow.isPending}>
            + New Flow
          </button>
        </div>

        {isLoading && <p>Loading flows…</p>}
        {error && <p style={{ color: 'red' }}>Failed to load flows</p>}

        <div className="grid">
          {flows?.map((flow) => (
            <div key={flow.id} className="card" style={{ borderColor: '#e2e8f0' }}>
              <div className="flex-between">
                <div>
                  <h3 style={{ margin: '0 0 4px' }}>{flow.name}</h3>
                  {flow.description && <p style={{ margin: 0 }}>{flow.description}</p>}
                </div>
                <button className="button secondary" onClick={() => deleteFlow.mutate(flow.id)} disabled={deleteFlow.isPending}>
                  Delete
                </button>
              </div>
              <div style={{ marginTop: 10 }}>
                <Link to={`/flows/${flow.id}`}>Open Editor</Link>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div>
          <h2>Databases</h2>
          <p>Upload documents to build a vector database.</p>
        </div>

        <div
          style={{
            display: 'grid',
            gap: 12,
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            marginTop: 12,
          }}
        >
          <div>
            <label htmlFor="database-name">Database name</label>
            <input
              id="database-name"
              className="input"
              value={databaseName}
              onChange={(event) => setDatabaseName(event.target.value)}
              placeholder="Support knowledge base"
            />
          </div>
          <div>
            <label htmlFor="database-files">Files</label>
            <input
              key={fileInputKey}
              id="database-files"
              className="input"
              type="file"
              multiple
              accept=".txt,.md,.pdf,.docx"
              onChange={(event) => setDatabaseFiles(event.target.files)}
            />
          </div>
          <div>
            <label htmlFor="database-chunk-size">Chunk size</label>
            <input
              id="database-chunk-size"
              className="input"
              type="number"
              min={1}
              value={chunkSize}
              onChange={(event) => setChunkSize(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="database-chunk-overlap">Chunk overlap</label>
            <input
              id="database-chunk-overlap"
              className="input"
              type="number"
              min={0}
              value={chunkOverlap}
              onChange={(event) => setChunkOverlap(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="database-embedding-model">Embedding model (optional)</label>
            <input
              id="database-embedding-model"
              className="input"
              value={embeddingModel}
              onChange={(event) => setEmbeddingModel(event.target.value)}
              placeholder="nomic-embed-text"
            />
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <button
            className="button"
            onClick={() => createDatabase.mutate()}
            disabled={!canCreateDatabase || createDatabase.isPending}
          >
            {createDatabase.isPending ? 'Creating…' : 'Create database'}
          </button>
        </div>
        {createDatabase.error && (
          <p style={{ color: 'red', marginTop: 8 }}>
            {createDatabase.error instanceof Error ? createDatabase.error.message : 'Failed to create database'}
          </p>
        )}

        {databasesLoading && <p>Loading databases…</p>}
        {databasesError && <p style={{ color: 'red' }}>Failed to load databases</p>}

        {!databasesLoading && databases && databases.length === 0 && (
          <p style={{ color: '#475569' }}>No databases yet.</p>
        )}

        <div className="grid" style={{ marginTop: 12 }}>
          {databases?.map((database) => (
            <div key={database.id} className="card" style={{ borderColor: '#e2e8f0' }}>
              <div className="flex-between">
                <div>
                  <h3 style={{ margin: '0 0 4px' }}>{database.name}</h3>
                  <p style={{ margin: 0, color: '#475569' }}>Status: {database.status}</p>
                </div>
                <button
                  className="button secondary"
                  onClick={() => deleteDatabase.mutate(database.id)}
                  disabled={deleteDatabase.isPending}
                >
                  Delete
                </button>
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: '#475569' }}>
                <div>Documents: {database.document_count}</div>
                <div>Chunks: {database.chunk_count}</div>
                {database.embedding_model && <div>Embedding: {database.embedding_model}</div>}
                {(database.chunk_size || database.chunk_overlap) && (
                  <div>
                    Chunking: {database.chunk_size ?? '-'} / {database.chunk_overlap ?? '-'}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
