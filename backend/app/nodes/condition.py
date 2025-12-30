from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry


@dataclass
class ConditionConfig:
    input_key: str = "input"
    compare_value: str = ""
    operator: str = "eq"  # eq | neq | lt | gt
    pass_through_key: str | None = None


def _coerce_types(left: Any, right: str) -> tuple[Any, Any]:
    """Try to align types for comparisons.

    If the left side is numeric and the right side looks numeric, compare as floats.
    Otherwise, fall back to plain string comparison.
    """

    try:
        left_num = float(left)
        right_num = float(right)
        return left_num, right_num
    except (TypeError, ValueError):
        return left, right


class ConditionNode(BaseNode):
    type_name = "ConditionNode"
    ConfigModel = ConditionConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        value = inputs.get(self.config.input_key)
        pass_key = (self.config.pass_through_key or "").strip()
        pass_value = inputs.get(pass_key) if pass_key else None
        output_value = pass_value if pass_key else value
        left, right = _coerce_types(value, self.config.compare_value)

        op = self.config.operator
        if op == "lt":
            passed = left < right
        elif op == "gt":
            passed = left > right
        elif op == "neq":
            passed = left != right
        else:
            passed = left == right

        return {
            "condition": passed,
            "value": value,
            "true": output_value if passed else None,
            "false": output_value if not passed else None,
        }


default_registry.register(ConditionNode)
