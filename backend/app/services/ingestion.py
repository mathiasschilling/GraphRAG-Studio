from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid
from typing import Iterable

from sqlalchemy.orm import Session

from ..config import get_settings
from ..persistence.models import Chunk, Document, VectorDatabase
from .chunking import chunk_text
from .ollama import call_ollama_embeddings
from .text_extractors import extract_text_from_path


@dataclass
class IngestionFile:
    filename: str
    content: bytes
    content_type: str | None = None


def _safe_filename(name: str) -> str:
    return Path(name).name or "document"


def _write_file(base_dir: Path, doc_id: str, filename: str, content: bytes) -> Path:
    safe_name = _safe_filename(filename)
    file_path = base_dir / f"{doc_id}_{safe_name}"
    file_path.write_bytes(content)
    return file_path


async def ingest_files(
    session: Session,
    database: VectorDatabase,
    files: Iterable[IngestionFile],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: str | None = None,
    storage_path: str | Path | None = None,
) -> list[Document]:
    settings = get_settings()
    resolved_chunk_size = chunk_size or database.chunk_size or settings.chunk_size
    resolved_chunk_overlap = chunk_overlap or database.chunk_overlap or settings.chunk_overlap
    resolved_embedding_model = embedding_model or database.embedding_model or settings.embedding_model

    database.embedding_model = database.embedding_model or resolved_embedding_model
    database.chunk_size = database.chunk_size or resolved_chunk_size
    database.chunk_overlap = database.chunk_overlap or resolved_chunk_overlap

    base_path = Path(storage_path or settings.storage_path)
    db_dir = base_path / database.id
    db_dir.mkdir(parents=True, exist_ok=True)

    documents: list[Document] = []
    for file in files:
        content = file.content or b""
        document_id = str(uuid.uuid4())
        document = Document(
            id=document_id,
            database_id=database.id,
            filename=_safe_filename(file.filename),
            mime_type=file.content_type,
            size=len(content),
        )
        session.add(document)
        documents.append(document)

        file_path = _write_file(db_dir, document_id, file.filename, content)
        text = extract_text_from_path(file_path)
        chunks = chunk_text(text, resolved_chunk_size, resolved_chunk_overlap)

        for index, chunk in enumerate(chunks):
            embedding = await call_ollama_embeddings(resolved_embedding_model, chunk)
            session.add(
                Chunk(
                    database_id=database.id,
                    document_id=document_id,
                    chunk_index=index,
                    text=chunk,
                    embedding=embedding,
                )
            )

    return documents
