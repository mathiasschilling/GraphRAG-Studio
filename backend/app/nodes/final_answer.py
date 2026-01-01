from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry


@dataclass
class FinalAnswerConfig:
    key: str = "response"
    output_key: str = "output"


class FinalAnswerNode(BaseNode):
    type_name = "FinalAnswerNode"
    ConfigModel = FinalAnswerConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        final_value = inputs.get(self.config.key)
        output_key = (self.config.output_key or "output").strip() or "output"
        return {output_key: final_value}


default_registry.register(FinalAnswerNode)
