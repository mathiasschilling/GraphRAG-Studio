from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict

from ..config import get_settings
from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry
from ..persistence.db import SessionLocal
from ..persistence.models import VectorDatabase
from ..services.ollama import call_ollama_embeddings
from ..services.vector_store import VectorStore


@dataclass
class DatabaseConfig:
    database_id: str = ""
    input_key: str = "query"
    query_template: str | None = None
    top_k: int = 5
    joiner: str = "\n\n"


class DatabaseNode(BaseNode):
    type_name = "DatabaseNode"
    ConfigModel = DatabaseConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        safe_inputs = defaultdict(str, inputs)

        if self.config.query_template:
            query_text = self.config.query_template.format_map(safe_inputs)
        else:
            query_text = inputs.get(self.config.input_key) or ""

        query_text = str(query_text)

        settings = get_settings()
        session = SessionLocal()
        try:
            if not self.config.database_id:
                raise ValueError("Database ID is required for DatabaseNode")
            database = session.get(VectorDatabase, self.config.database_id)
            if database is None:
                raise ValueError(f"Database '{self.config.database_id}' not found")
            embedding_model = database.embedding_model or settings.embedding_model
            embedding = await call_ollama_embeddings(embedding_model, query_text)
            store = VectorStore(session)
            matches = store.search(database.id, embedding, top_k=self.config.top_k)
        finally:
            session.close()

        response = self.config.joiner.join(match.text for match in matches)
        return {
            "response": response,
            "matches": [
                {
                    "chunk_id": match.chunk_id,
                    "document_id": match.document_id,
                    "text": match.text,
                    "score": match.score,
                }
                for match in matches
            ],
        }


default_registry.register(DatabaseNode)
