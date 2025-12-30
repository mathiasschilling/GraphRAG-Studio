from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from sqlalchemy.orm import Session

from ..persistence.models import Chunk


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


@dataclass
class VectorMatch:
    chunk_id: str
    document_id: str
    text: str
    score: float


class VectorStore:
    """Naive vector search backed by SQLAlchemy rows."""

    def __init__(self, session: Session):
        self._session = session

    def search(self, database_id: str, query_embedding: list[float], top_k: int = 5) -> list[VectorMatch]:
        if top_k <= 0:
            return []
        chunks = (
            self._session.query(Chunk)
            .filter(Chunk.database_id == database_id)
            .all()
        )
        matches = [
            VectorMatch(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                score=cosine_similarity(query_embedding, chunk.embedding or []),
            )
            for chunk in chunks
        ]
        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[:top_k]
