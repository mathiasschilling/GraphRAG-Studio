from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry


@dataclass
class UserInputConfig:
    key: str = "input"


class UserInputNode(BaseNode):
    type_name = "UserInputNode"
    ConfigModel = UserInputConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Surface the initial input under a configurable key, unwrapping common payload shapes
        initial = ctx.initial_input
        if isinstance(initial, dict) and "text" in initial:
            initial = initial["text"]

        return {self.config.key: initial}


default_registry.register(UserInputNode)
