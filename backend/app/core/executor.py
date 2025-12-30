from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from .. import nodes  # noqa: F401  # ensure node types are registered
from .context import ExecutionContext
from .graph import FlowGraph
from .node_base import BaseNode, NodeRegistry, default_registry


class GraphExecutionError(RuntimeError):
    ...


@dataclass
class NodeExecutionLog:
    node_id: str
    started_at: datetime
    completed_at: datetime
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    skipped: bool = False

    @property
    def duration_ms(self) -> float:
        return (self.completed_at - self.started_at).total_seconds() * 1000


@dataclass
class ExecutionResult:
    outputs: Dict[str, Dict[str, Any]]
    node_logs: List[NodeExecutionLog]
    started_at: datetime
    completed_at: datetime

    @property
    def duration_ms(self) -> float:
        return (self.completed_at - self.started_at).total_seconds() * 1000

    def node_output_map(self) -> Dict[str, Dict[str, Any]]:
        return {
            log.node_id: {
                "inputs": log.inputs,
                "outputs": log.outputs,
                "started_at": log.started_at.isoformat(),
                "completed_at": log.completed_at.isoformat(),
                "duration_ms": log.duration_ms,
                "skipped": log.skipped,
            }
            for log in self.node_logs
        }


def _topological_sort(graph: FlowGraph) -> List[str]:
    """Return node ids sorted so every dependency appears before its consumers."""
    indegree = {node_id: 0 for node_id in graph.nodes.keys()}
    adjacency: Dict[str, List[str]] = defaultdict(list)

    for edge in graph.edges:
        adjacency[edge.from_node].append(edge.to_node)
        indegree[edge.to_node] += 1

    queue: deque[str] = deque(node for node, deg in indegree.items() if deg == 0)
    ordered: List[str] = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for neighbor in adjacency[node]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(indegree):
        raise GraphExecutionError("Flow contains a cycle or disconnected nodes")

    return ordered


def _incoming_edge_pairs(graph: FlowGraph) -> Dict[str, Tuple[Tuple[str, str, str], ...]]:
    """Group incoming edges for each node as (from_id, from_output, to_input)."""

    default_source = {
        "UserInputNode": "input",
        "PromptTemplateNode": "prompt",
        "LLMNode": "response",
        "DatabaseNode": "response",
        "FinalAnswerNode": "output",
        "ConditionNode": "true",
    }

    default_target = {
        "UserInputNode": "input",
        "PromptTemplateNode": "input",
        "LLMNode": "prompt",
        "DatabaseNode": "query",
        "FinalAnswerNode": "response",
        "ConditionNode": "input",
    }

    incoming: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for edge in graph.edges:
        source_type = graph.nodes.get(edge.from_node).type if edge.from_node in graph.nodes else None
        target_type = graph.nodes.get(edge.to_node).type if edge.to_node in graph.nodes else None

        from_output = edge.from_output or default_source.get(source_type, "input")
        to_input = edge.to_input or default_target.get(target_type, from_output) or from_output

        incoming[edge.to_node].append((edge.from_node, from_output, to_input))
    return {node: tuple(edges) for node, edges in incoming.items()}


def _instantiate_nodes(graph: FlowGraph, registry: NodeRegistry) -> Dict[str, BaseNode]:
    """Create concrete node instances from graph definitions using the registry."""
    instances: Dict[str, BaseNode] = {}
    for node_id, node_def in graph.nodes.items():
        instances[node_id] = registry.create_node(node_def.type, node_def.id, node_def.config)
    return instances


async def execute_graph(
    graph: FlowGraph,
    initial_input: Any,
    registry: NodeRegistry | None = None,
    event_handler: Callable[[dict], Awaitable[None]] | None = None,
) -> ExecutionResult:
    """Execute a flow graph in topological order."""

    registry = registry or default_registry
    order = _topological_sort(graph)
    incoming_pairs = _incoming_edge_pairs(graph)
    nodes = _instantiate_nodes(graph, registry)
    ctx = ExecutionContext(initial_input=initial_input)
    started_at = datetime.now(timezone.utc)
    node_logs: List[NodeExecutionLog] = []
    skipped_nodes: set[str] = set()

    async def emit_event(status: str, node_id: str, timestamp: datetime | None = None) -> None:
        if event_handler is None:
            return

        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        await event_handler({"node_id": node_id, "status": status, "timestamp": ts})

    for node_id in order:
        node = nodes[node_id]
        inbound = incoming_pairs.get(node_id, tuple())

        # Skip execution if any upstream dependency was skipped
        if any(parent in skipped_nodes for parent, *_ in inbound):
            now = datetime.now(timezone.utc)
            skipped_nodes.add(node_id)
            await emit_event("skipped", node_id, now)
            node_logs.append(
                NodeExecutionLog(
                    node_id=node_id,
                    started_at=now,
                    completed_at=now,
                    inputs={},
                    outputs={},
                    skipped=True,
                )
            )
            continue

        inputs = ctx.collect_inputs(inbound)

        # Conditional branching: if a node is wired to the "true" output of a
        # Condition node but that condition evaluated to False (or vice versa),
        # skip this node and its downstream dependents.
        branch_blocked = False
        for parent, from_output, _ in inbound:
            parent_def = graph.nodes.get(parent)
            if parent_def and parent_def.type == "ConditionNode" and from_output in {"true", "false"}:
                condition_passed = ctx.get(parent, "condition")
                if condition_passed is not None:
                    if (from_output == "true" and condition_passed is False) or (
                        from_output == "false" and condition_passed is True
                    ):
                        branch_blocked = True
                        break

        if branch_blocked:
            now = datetime.now(timezone.utc)
            skipped_nodes.add(node_id)
            await emit_event("skipped", node_id, now)
            node_logs.append(
                NodeExecutionLog(
                    node_id=node_id,
                    started_at=now,
                    completed_at=now,
                    inputs=inputs,
                    outputs={},
                    skipped=True,
                )
            )
            continue

        # Conditional gating: if a node receives a falsy "condition" input, skip it
        if inputs.get("condition") is False:
            now = datetime.now(timezone.utc)
            skipped_nodes.add(node_id)
            await emit_event("skipped", node_id, now)
            node_logs.append(
                NodeExecutionLog(
                    node_id=node_id,
                    started_at=now,
                    completed_at=now,
                    inputs=inputs,
                    outputs={},
                    skipped=True,
                )
            )
            continue

        node_started_at = datetime.now(timezone.utc)
        await emit_event("started", node_id, node_started_at)
        outputs = await node.execute(ctx, inputs)
        node_completed_at = datetime.now(timezone.utc)
        for output_name, value in outputs.items():
            ctx.add(node_id, output_name, value)
        node_logs.append(
            NodeExecutionLog(
                node_id=node_id,
                started_at=node_started_at,
                completed_at=node_completed_at,
                inputs=inputs,
                outputs=outputs,
            )
        )
        await emit_event("completed", node_id, node_completed_at)

    completed_at = datetime.now(timezone.utc)

    return ExecutionResult(outputs=ctx.values, node_logs=node_logs, started_at=started_at, completed_at=completed_at)
