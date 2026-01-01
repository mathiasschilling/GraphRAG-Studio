from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry


@dataclass
class PromptTemplateConfig:
    template: str
    output_key: str = "prompt"


class PromptTemplateNode(BaseNode):
    type_name = "PromptTemplateNode"
    ConfigModel = PromptTemplateConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        rendered = self.config.template.format(**inputs)
        output_key = (self.config.output_key or "prompt").strip() or "prompt"
        return {output_key: rendered}


default_registry.register(PromptTemplateNode)
