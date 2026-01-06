# GraphRAG Studio

GraphRAG Studio is a visual builder for Retrieval-Augmented Generation (RAG) flows. The backend (FastAPI) executes directed graphs of nodes such as user input, prompt templates, LLM calls, conditions, and final answers; the frontend (React + React Flow) lets you design, run, and inspect those flows without writing glue code.

## Features
- Drag-and-drop editor with UML-inspired node shapes (input/output, prompt, LLM, condition).
- Flow persistence and execution via the FastAPI backend, with per-node timing/output metadata.
- Optional local model inference through Ollama; stubbed responses available for offline testing.
- Global keys with hoverable key-usage tracing in run results (origin + consumers).

## Node configuration tips
- The input node provides an `input` key, LLM nodes produce `response` keys.
- Keys are literal input/output names. Use `response`, not `{response}`, in Output node configs.
- Curly braces are only for prompt templates (for example, `Hello {input}`).
- Global keys are always-on with inputs-first and last-writer-wins semantics. Any key written by a node is available to later nodes without explicit edges.
- Each node can have an optional `name` shown as the primary label; the type badge stays visible.

## Export node
- Export node writes JSON to disk, either a single key payload or the run log snapshot.
- Modes:
  - `key`: writes `{"key": "<key>", "value": <value>}` (value resolved from inputs, then globals).
  - `run_log`: writes the run log payload (per-node inputs/outputs/timestamps/duration).
- Files are saved under `GRAPHRAG_STORAGE_PATH/exports` (default `backend/storage/exports`).
- The node outputs the file path via `output_key` (default `export_path`).

## Vector databases
- Create a database from the Flows page by uploading `.txt`, `.md`, `.pdf`, or `.docx` files.
- Documents are chunked (default 500 chars with 100 overlap) and embedded via Ollama.
- Configure defaults via environment variables:
  - `GRAPHRAG_EMBEDDING_MODEL`
  - `GRAPHRAG_CHUNK_SIZE`
  - `GRAPHRAG_CHUNK_OVERLAP`
  - `GRAPHRAG_STORAGE_PATH`
- Use the Database node to query: choose a database, set a query template or input key, and pick `top_k`.
- The Database node outputs `response` (joined chunks) and `matches` (structured list).

## Demo flow walkthrough

### Create a vector database and use it in a flow
1.	Upload the files you want to index into your vector database.
2.	Give the database a descriptive name and create it.
3.	Create a new flow.
4.	Add a DB node and select your newly created vector database.
5.	(Optional) Add LLM nodes and connect them to your local models via Ollama.

<video src="https://github.com/user-attachments/assets/5d744006-3ffc-4574-9c67-dff8933d38f1" controls="controls">
</video>

### Create a flow with a condition node
1.	Use the first LLM node to normalize the input (e.g., extract title, description, urgency, category).
2.	Use the second LLM node to classify urgency.
3.	Add a Condition node to branch the flow based on the classification result.
4.	Handle the responses differently per branch (e.g., escalation path for urgent cases).

<video src="https://github.com/user-attachments/assets/fb51a17d-51e3-4d2e-975b-2a0759919590" controls="controls">
</video>

## Prerequisites
- Python 3.10+ and Node.js 18+.
- Ollama running locally if you want real model responses (set `GRAPHRAG_USE_LLM_STUB=false`).

## Quickstart
1) **Backend**
   - `cd backend`
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `python -m app.server`
   - The API listens on `http://localhost:8000` by default (configurable via `GRAPHRAG_API_HOST`/`GRAPHRAG_API_PORT`).

2) **Frontend**
   - Open a new shell, then `cd frontend`
   - `npm install`
   - (Optional) create `.env` with `VITE_API_BASE=http://localhost:8000` if you are not using the default URL
   - `npm run dev` and open the printed localhost URL

Run the backend first so the frontend can reach the API.

## Testing
- Backend tests: `cd backend && source .venv/bin/activate && pytest`
- Frontend lint/tests (if configured): `cd frontend && npm test`

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Attribution (optional)
If you use this project, attribution is appreciated but not required. Suggested credit:

> GraphRAG Studio by Mathias Schilling
