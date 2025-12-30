from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SqliteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Flow(Base):
    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    graph: Mapped[dict] = mapped_column(SqliteJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    runs: Mapped[list[Run]] = relationship("Run", back_populates="flow", cascade="all, delete-orphan")


class RunStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id: Mapped[str] = mapped_column(String, ForeignKey("flows.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default=RunStatus.PENDING)
    input_payload: Mapped[dict] = mapped_column(SqliteJSON)
    output_payload: Mapped[dict | None] = mapped_column(SqliteJSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    node_outputs: Mapped[dict | None] = mapped_column(SqliteJSON, nullable=True)

    flow: Mapped[Flow] = relationship("Flow", back_populates="runs")


class VectorDatabaseStatus:
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class VectorDatabase(Base):
    __tablename__ = "vector_databases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default=VectorDatabaseStatus.PENDING)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    chunk_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_overlap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="database",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk",
        back_populates="database",
        cascade="all, delete-orphan",
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    database_id: Mapped[str] = mapped_column(String, ForeignKey("vector_databases.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    database: Mapped[VectorDatabase] = relationship("VectorDatabase", back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    database_id: Mapped[str] = mapped_column(String, ForeignKey("vector_databases.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(SqliteJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    database: Mapped[VectorDatabase] = relationship("VectorDatabase", back_populates="chunks")
    document: Mapped[Document] = relationship("Document", back_populates="chunks")
