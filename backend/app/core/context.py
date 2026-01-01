from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Tuple


@dataclass
class ExecutionContext:
    """Shared state for node execution.

    Stores outputs per node so downstream nodes can access upstream values.
    """

    initial_input: Any
    values: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    global_values: Dict[str, Any] = field(default_factory=dict)

    def add(self, node_id: str, output_name: str, value: Any) -> None:
        node_bucket = self.values.setdefault(node_id, {})
        node_bucket[output_name] = value
        # Always expose outputs globally, with last-writer-wins semantics.
        self.global_values[output_name] = value

    def get(self, node_id: str, output_name: str) -> Any:
        return self.values.get(node_id, {}).get(output_name)

    def get_value(self, node_id: str) -> Any:
        """Convenience for single-output nodes."""
        outputs = self.values.get(node_id, {})
        if len(outputs) != 1:
            raise KeyError(f"Node '{node_id}' does not have exactly one output")
        return next(iter(outputs.values()))

    def collect_inputs(
        self,
        incoming_edges: Tuple[Tuple[str, str, str], ...],
        required_keys: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Return a mapping of input name -> value from upstream edges.

        Each edge tuple carries: (from_node, from_output, to_input_name)
        The to_input_name will be used if provided, otherwise we fall back to
        the originating output name to preserve prior behavior. When
        required_keys are provided, any missing keys are filled from the
        global value store without overriding existing inputs.
        """
        inputs: Dict[str, Any] = {}
        for from_node, from_output, to_input in incoming_edges:
            key = to_input or from_output
            value = self.get(from_node, from_output)
            inputs[key] = value

            # Preserve the originating output name as an alias when it differs
            # from the target handle so downstream nodes can reference either
            # {prompt} or {response} (or other output names) in their templates.
            if from_output and from_output != key and from_output not in inputs:
                inputs[from_output] = value
        if required_keys:
            for key in required_keys:
                if key not in inputs and key in self.global_values:
                    inputs[key] = self.global_values[key]
        return inputs
