from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from ..core.graph import FlowGraph, flow_graph_from_dict, flow_graph_to_dict


class EdgeDefinitionSchema(BaseModel):
    id: str
    from_node: str
    from_output: str
    to_node: str
    to_input: str | None = None


class NodeDefinitionSchema(BaseModel):
    id: str
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    position: Dict[str, Any] | None = None


class FlowGraphSchema(BaseModel):
    id: str
    nodes: Dict[str, NodeDefinitionSchema]
    edges: list[EdgeDefinitionSchema]

    def to_core(self) -> FlowGraph:
        return flow_graph_from_dict(self.model_dump())

    @classmethod
    def from_core(cls, graph: FlowGraph) -> "FlowGraphSchema":
        return cls(**flow_graph_to_dict(graph))


class RunRequest(BaseModel):
    graph: FlowGraphSchema
    input: Any


class RunResponse(BaseModel):
    outputs: dict
    key_usage: dict | None = None


class FlowCreate(BaseModel):
    name: str
    graph: FlowGraphSchema


class FlowUpdate(BaseModel):
    name: str | None = None
    graph: FlowGraphSchema | None = None


class FlowRead(BaseModel):
    id: str
    name: str
    graph: FlowGraphSchema


class RunCreateRequest(BaseModel):
    input: Any


class NodeRunLog(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    started_at: str
    completed_at: str
    duration_ms: float
    skipped: bool = False


class RunRead(BaseModel):
    id: str
    flow_id: str
    status: str
    input_payload: dict
    output_payload: dict | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    node_outputs: Dict[str, NodeRunLog] | None = None
    key_usage: Dict[str, Any] | None = None


class ChunkPreview(BaseModel):
    id: str
    document_id: str
    text: str
    score: float | None = None


class DocumentRead(BaseModel):
    id: str
    database_id: str
    filename: str
    mime_type: str | None = None
    size: int | None = None
    created_at: str
    chunk_count: int


class ChunkRead(BaseModel):
    id: str
    database_id: str
    document_id: str
    chunk_index: int
    text: str
    created_at: str


class VectorDatabaseRead(BaseModel):
    id: str
    name: str
    status: str
    embedding_model: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    created_at: str
    document_count: int
    chunk_count: int


class VectorDatabaseList(BaseModel):
    databases: List[VectorDatabaseRead]
