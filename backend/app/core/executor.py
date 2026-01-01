from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from string import Formatter
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
    key_usage: Dict[str, Any] = field(default_factory=dict)

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


def _normalized_key(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        value = value.strip()
    return value or fallback


def _condition_branch_keys(node_def: Any) -> tuple[str, str]:
    config = getattr(node_def, "config", {}) or {}
    true_key = _normalized_key(config.get("true_key"), "true")
    false_key = _normalized_key(config.get("false_key"), "false")
    return true_key, false_key


def _default_source_handle(node_def: Any) -> str:
    if node_def is None:
        return "input"
    config = getattr(node_def, "config", {}) or {}
    node_type = getattr(node_def, "type", None)
    if node_type == "UserInputNode":
        return _normalized_key(config.get("key"), "input")
    if node_type == "PromptTemplateNode":
        return _normalized_key(config.get("output_key"), "prompt")
    if node_type == "LLMNode":
        return _normalized_key(config.get("output_key"), "response")
    if node_type == "DatabaseNode":
        return _normalized_key(config.get("output_key"), "response")
    if node_type == "FinalAnswerNode":
        return _normalized_key(config.get("output_key"), "output")
    if node_type == "ConditionNode":
        true_key, _ = _condition_branch_keys(node_def)
        return true_key
    return "input"


def _default_target_handle(node_def: Any, from_output: str) -> str:
    if node_def is None:
        return from_output or "input"
    config = getattr(node_def, "config", {}) or {}
    node_type = getattr(node_def, "type", None)
    if node_type == "UserInputNode":
        return _normalized_key(config.get("key"), "input")
    if node_type == "PromptTemplateNode":
        return "input"
    if node_type == "LLMNode":
        return "prompt"
    if node_type == "DatabaseNode":
        return _normalized_key(config.get("input_key"), "query")
    if node_type == "FinalAnswerNode":
        return _normalized_key(config.get("key"), "response")
    if node_type == "ConditionNode":
        return _normalized_key(config.get("input_key"), "input")
    return from_output or "input"


def _template_keys(template: str | None) -> set[str]:
    if not template:
        return set()
    keys: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        base = field_name.split(".", 1)[0].split("[", 1)[0]
        if base:
            keys.add(base)
    return keys


def _required_input_keys(node_def: Any) -> set[str]:
    if node_def is None:
        return set()
    config = getattr(node_def, "config", {}) or {}
    node_type = getattr(node_def, "type", None)

    if node_type == "PromptTemplateNode":
        return _template_keys(config.get("template"))
    if node_type == "LLMNode":
        template = config.get("user_template") or config.get("prompt")
        if template:
            return _template_keys(template)
        return {"prompt", "input", "text"}
    if node_type == "DatabaseNode":
        template = config.get("query_template")
        if template:
            return _template_keys(template)
        return {_normalized_key(config.get("input_key"), "query")}
    if node_type == "ConditionNode":
        keys = {_normalized_key(config.get("input_key"), "input")}
        pass_key = _normalized_key(config.get("pass_through_key"), "")
        if pass_key:
            keys.add(pass_key)
        return keys
    if node_type == "FinalAnswerNode":
        return {_normalized_key(config.get("key"), "response")}
    return set()


def _ensure_key_usage(key_usage: Dict[str, Dict[str, Any]], key: str) -> Dict[str, Any]:
    return key_usage.setdefault(
        key,
        {"consumers": set(), "writers": [], "source_node": None, "value": None},
    )


def _incoming_edge_pairs(graph: FlowGraph) -> Dict[str, Tuple[Tuple[str, str, str], ...]]:
    """Group incoming edges for each node as (from_id, from_output, to_input)."""

    incoming: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for edge in graph.edges:
        source_def = graph.nodes.get(edge.from_node)
        target_def = graph.nodes.get(edge.to_node)

        from_output = edge.from_output or _default_source_handle(source_def)
        to_input = edge.to_input or _default_target_handle(target_def, from_output) or from_output

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
    key_usage: Dict[str, Dict[str, Any]] = {}

    async def emit_event(status: str, node_id: str, timestamp: datetime | None = None) -> None:
        if event_handler is None:
            return

        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        await event_handler({"node_id": node_id, "status": status, "timestamp": ts})

    for node_id in order:
        node = nodes[node_id]
        node_def = graph.nodes.get(node_id)
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

        required_keys = _required_input_keys(node_def)
        inputs = ctx.collect_inputs(inbound, required_keys)

        # Conditional branching: if a node is wired to the "true" output of a
        # Condition node but that condition evaluated to False (or vice versa),
        # skip this node and its downstream dependents.
        branch_blocked = False
        for parent, from_output, _ in inbound:
            parent_def = graph.nodes.get(parent)
            if parent_def and parent_def.type == "ConditionNode":
                true_key, false_key = _condition_branch_keys(parent_def)
                branch_keys = {true_key, false_key, "true", "false"}
                if from_output in branch_keys:
                    condition_passed = ctx.get(parent, "condition")
                    if condition_passed is not None:
                        if (from_output in {true_key, "true"} and condition_passed is False) or (
                            from_output in {false_key, "false"} and condition_passed is True
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
        if required_keys:
            for key in required_keys:
                _ensure_key_usage(key_usage, key)["consumers"].add(node_id)
        outputs = await node.execute(ctx, inputs)
        node_completed_at = datetime.now(timezone.utc)
        for output_name, value in outputs.items():
            ctx.add(node_id, output_name, value)
            entry = _ensure_key_usage(key_usage, output_name)
            entry["writers"].append(node_id)
            entry["source_node"] = node_id
            entry["value"] = value
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

    finalized_key_usage = {
        key: {
            "value": entry.get("value"),
            "source_node": entry.get("source_node"),
            "writers": entry.get("writers", []),
            "consumers": sorted(entry.get("consumers", set())),
        }
        for key, entry in key_usage.items()
    }

    return ExecutionResult(
        outputs=ctx.values,
        node_logs=node_logs,
        started_at=started_at,
        completed_at=completed_at,
        key_usage=finalized_key_usage,
    )
