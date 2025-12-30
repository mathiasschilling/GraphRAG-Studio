# Backend quickstart

## Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure environment (optional overrides in a `.env` file):
   - `GRAPHRAG_DATABASE_URL` (default: `sqlite:///./app.db`)
   - `GRAPHRAG_OLLAMA_BASE_URL` (default: `http://localhost:11434`)
   - `GRAPHRAG_USE_LLM_STUB` (default: `false`; set to `true` to avoid calling Ollama during tests/dev). If Ollama is unreachable at runtime, the service logs a warning and falls back to a stubbed response so flows can still complete.
   - `GRAPHRAG_API_HOST` / `GRAPHRAG_API_PORT` for server binding.

## Database migrations
The project ships with Alembic wiring. To create or upgrade the schema:
```bash
cd backend
alembic upgrade head
```
Use `alembic revision --autogenerate -m "description"` to capture schema changes.

## Running the API
Launch the FastAPI app with uvicorn:
```bash
cd backend
python -m app.server
```
This initializes the database on startup and binds to the configured host/port.

### Ollama troubleshooting
- Ensure `ollama serve` is running and reachable at `GRAPHRAG_OLLAMA_BASE_URL` (default `http://localhost:11434`). The client issues a POST to `/api/generate`; if that path returns 404 the daemon is usually down or unreachable at the configured base URL.
- Pull the model before running (for example, `ollama pull qwen3:0.6b`). Ollama returns HTTP 404 when the model name is unknown, so a missing pull commonly produces this error.
- When Ollama fails, the service falls back to a stubbed response and includes the error text in the LLM output along with a hint to verify the base URL and model. Set `GRAPHRAG_USE_LLM_STUB=true` to always stub during development/tests, or leave it `false` to use the live model once the daemon is healthy.

## Conditional execution
The executor supports simple branching through the `ConditionNode`:
- Configure the node with an input key, comparison value, and operator (`lt`, `gt`, `eq`, `neq`).
- Connect its output to the `condition` input of any downstream nodes you want to gate.
- When the condition evaluates to `False`, the gated node and its downstream dependencies are skipped but still logged with `skipped: true` in the run record.

## Vector databases
- Upload `.txt`, `.md`, `.pdf`, or `.docx` files via the `/databases` API to build a vector database.
- Embeddings are generated through Ollama's `/api/embeddings` endpoint; when `GRAPHRAG_USE_LLM_STUB=true`, embeddings are stubbed deterministically.
- Default settings:
  - `GRAPHRAG_EMBEDDING_MODEL` (default: `nomic-embed-text`)
  - `GRAPHRAG_CHUNK_SIZE` (default: `500`)
  - `GRAPHRAG_CHUNK_OVERLAP` (default: `100`)
  - `GRAPHRAG_STORAGE_PATH` (default: `./storage`)
- Use the `DatabaseNode` in flows to query the most similar chunks and output them as `response` plus a structured `matches` list.
