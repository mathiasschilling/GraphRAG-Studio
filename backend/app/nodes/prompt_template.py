from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry


@dataclass
class PromptTemplateConfig:
    template: str


class PromptTemplateNode(BaseNode):
    type_name = "PromptTemplateNode"
    ConfigModel = PromptTemplateConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        rendered = self.config.template.format(**inputs)
        return {"prompt": rendered}


default_registry.register(PromptTemplateNode)
