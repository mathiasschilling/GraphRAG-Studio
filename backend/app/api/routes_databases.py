from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..persistence.db import SessionLocal
from ..persistence.models import Chunk, Document, VectorDatabase, VectorDatabaseStatus
from ..services.ingestion import IngestionFile, ingest_files
from .schemas import VectorDatabaseRead

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


@router.delete("/{database_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_database(database_id: str, db: Session = Depends(get_db)) -> None:
    database = db.get(VectorDatabase, database_id)
    if not database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    db.delete(database)
    db.commit()
