from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..persistence.db import SessionLocal
from ..persistence.models import Chunk, Document, VectorDatabase, VectorDatabaseStatus
from ..services.ingestion import IngestionFile, document_file_path, ingest_files
from .schemas import ChunkRead, DocumentRead, VectorDatabaseRead

router = APIRouter(prefix="/databases", tags=["databases"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_read(db: Session, database: VectorDatabase) -> VectorDatabaseRead:
    document_count = db.query(Document).filter(Document.database_id == database.id).count()
    chunk_count = db.query(Chunk).filter(Chunk.database_id == database.id).count()
    return VectorDatabaseRead(
        id=database.id,
        name=database.name,
        status=database.status,
        embedding_model=database.embedding_model,
        chunk_size=database.chunk_size,
        chunk_overlap=database.chunk_overlap,
        created_at=database.created_at.isoformat(),
        document_count=document_count,
        chunk_count=chunk_count,
    )


def _chunk_counts_by_document(db: Session, database_id: str) -> dict[str, int]:
    counts = (
        db.query(Chunk.document_id, func.count(Chunk.id))
        .filter(Chunk.database_id == database_id)
        .group_by(Chunk.document_id)
        .all()
    )
    return {document_id: count for document_id, count in counts}


def _document_to_read(document: Document, chunk_count: int) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        database_id=document.database_id,
        filename=document.filename,
        mime_type=document.mime_type,
        size=document.size,
        created_at=document.created_at.isoformat(),
        chunk_count=chunk_count,
    )


def _chunk_to_read(chunk: Chunk) -> ChunkRead:
    return ChunkRead(
        id=chunk.id,
        database_id=chunk.database_id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        created_at=chunk.created_at.isoformat(),
    )


@router.post("", response_model=VectorDatabaseRead, status_code=status.HTTP_201_CREATED)
async def create_database(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    chunk_size: int | None = Form(None),
    chunk_overlap: int | None = Form(None),
    embedding_model: str | None = Form(None),
    db: Session = Depends(get_db),
) -> VectorDatabaseRead:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    database = VectorDatabase(
        id=str(uuid.uuid4()),
        name=name,
        status=VectorDatabaseStatus.INDEXING,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    db.add(database)
    db.commit()
    db.refresh(database)

    ingestion_files: list[IngestionFile] = []
    for file in files:
        content = await file.read()
        ingestion_files.append(
            IngestionFile(
                filename=file.filename,
                content=content,
                content_type=file.content_type,
            )
        )

    settings = get_settings()
    try:
        await ingest_files(
            db,
            database,
            ingestion_files,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
            storage_path=settings.storage_path,
        )
        database.status = VectorDatabaseStatus.READY
        db.add(database)
        db.commit()
        db.refresh(database)
    except Exception as exc:
        database.status = VectorDatabaseStatus.FAILED
        db.add(database)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return _to_read(db, database)


@router.post("/{database_id}/documents", response_model=list[DocumentRead], status_code=status.HTTP_201_CREATED)
async def add_documents(
    database_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    database = db.get(VectorDatabase, database_id)
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")

    database.status = VectorDatabaseStatus.INDEXING
    db.add(database)
    db.commit()
    db.refresh(database)

    ingestion_files: list[IngestionFile] = []
    for file in files:
        content = await file.read()
        ingestion_files.append(
            IngestionFile(
                filename=file.filename,
                content=content,
                content_type=file.content_type,
            )
        )

    settings = get_settings()
    try:
        documents = await ingest_files(
            db,
            database,
            ingestion_files,
            storage_path=settings.storage_path,
        )
        database.status = VectorDatabaseStatus.READY
        db.add(database)
        db.commit()
    except Exception as exc:
        database.status = VectorDatabaseStatus.FAILED
        db.add(database)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    chunk_counts = _chunk_counts_by_document(db, database_id)
    return [_document_to_read(document, chunk_counts.get(document.id, 0)) for document in documents]


@router.get("", response_model=list[VectorDatabaseRead])
def list_databases(db: Session = Depends(get_db)) -> list[VectorDatabaseRead]:
    databases = db.query(VectorDatabase).order_by(VectorDatabase.created_at.desc()).all()
    return [_to_read(db, database) for database in databases]


@router.get("/{database_id}", response_model=VectorDatabaseRead)
def get_database(database_id: str, db: Session = Depends(get_db)) -> VectorDatabaseRead:
    database = db.get(VectorDatabase, database_id)
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    return _to_read(db, database)


@router.get("/{database_id}/documents", response_model=list[DocumentRead])
def list_documents(database_id: str, db: Session = Depends(get_db)) -> list[DocumentRead]:
    database = db.get(VectorDatabase, database_id)
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")

    documents = (
        db.query(Document)
        .filter(Document.database_id == database_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    chunk_counts = _chunk_counts_by_document(db, database_id)
    return [_document_to_read(document, chunk_counts.get(document.id, 0)) for document in documents]


@router.get("/{database_id}/chunks", response_model=list[ChunkRead])
def list_chunks(
    database_id: str,
    document_id: str | None = None,
    limit: int | None = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ChunkRead]:
    database = db.get(VectorDatabase, database_id)
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")

    query = db.query(Chunk).filter(Chunk.database_id == database_id)
    if document_id:
        query = query.filter(Chunk.document_id == document_id)
    query = query.order_by(Chunk.created_at.desc())
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return [_chunk_to_read(chunk) for chunk in query.all()]


@router.delete("/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_database(database_id: str, db: Session = Depends(get_db)) -> None:
    database = db.get(VectorDatabase, database_id)
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    db.delete(database)
    db.commit()


@router.delete("/{database_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(database_id: str, document_id: str, db: Session = Depends(get_db)) -> None:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.database_id == database_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    settings = get_settings()
    file_path = document_file_path(settings.storage_path, database_id, document.id, document.filename)
    try:
        file_path.unlink()
    except FileNotFoundError:
        pass

    db.query(Chunk).filter(Chunk.document_id == document.id).delete(synchronize_session=False)
    db.delete(document)
    db.commit()


@router.delete("/{database_id}/chunks/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk(database_id: str, chunk_id: str, db: Session = Depends(get_db)) -> None:
    chunk = (
        db.query(Chunk)
        .filter(Chunk.id == chunk_id, Chunk.database_id == database_id)
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
    db.delete(chunk)
    db.commit()
