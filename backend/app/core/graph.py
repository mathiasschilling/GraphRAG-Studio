from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EdgeDefinition:
    id: str
    from_node: str
    from_output: str
    to_node: str
    to_input: Optional[str] = None


@dataclass
class NodeDefinition:
    id: str
    type: str
    config: dict = field(default_factory=dict)
    position: Optional[dict] = None


@dataclass
class FlowGraph:
    id: str
    nodes: Dict[str, NodeDefinition]
    edges: List[EdgeDefinition]

    def __post_init__(self) -> None:
        for node_id, node in self.nodes.items():
            if node.id != node_id:
                raise ValueError(f"Node key '{node_id}' must match node.id '{node.id}'")
        node_ids = set(self.nodes.keys())
        for edge in self.edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                raise ValueError(f"Edge '{edge.id}' references unknown nodes")

    def incoming_for(self, node_id: str) -> List[EdgeDefinition]:
        return [edge for edge in self.edges if edge.to_node == node_id]

    def outgoing_for(self, node_id: str) -> List[EdgeDefinition]:
        return [edge for edge in self.edges if edge.from_node == node_id]


def flow_graph_from_dict(data: dict) -> FlowGraph:
    nodes = {
        node_id: NodeDefinition(
            id=node_id,
            type=node_data["type"],
            config=node_data.get("config", {}),
            position=node_data.get("position"),
        )
        for node_id, node_data in data.get("nodes", {}).items()
    }

    edges = [
        EdgeDefinition(
            id=edge_data["id"],
            from_node=edge_data["from_node"],
            from_output=edge_data["from_output"],
            to_node=edge_data["to_node"],
            to_input=edge_data.get("to_input"),
        )
        for edge_data in data.get("edges", [])
    ]

    return FlowGraph(id=data["id"], nodes=nodes, edges=edges)


def flow_graph_to_dict(graph: FlowGraph) -> dict:
    return {
        "id": graph.id,
        "nodes": {
            node_id: {
                "id": node.id,
                "type": node.type,
                "config": node.config,
                "position": node.position,
            }
            for node_id, node in graph.nodes.items()
        },
        "edges": [
            {
                "id": edge.id,
                "from_node": edge.from_node,
                "from_output": edge.from_output,
                "to_node": edge.to_node,
                "to_input": edge.to_input,
            }
            for edge in graph.edges
        ],
    }
