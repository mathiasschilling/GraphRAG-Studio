from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from .context import ExecutionContext


class BaseNode(ABC):
    """Base class for all node implementations."""

    type_name: str = "base"
    ConfigModel: Type[Any] = object

    def __init__(self, id: str, config: Optional[dict] = None):
        config = config or {}
        self.id = id
        self.config = self.ConfigModel(**config) if callable(getattr(self.ConfigModel, "__call__", None)) else self.ConfigModel

    @abstractmethod
    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ...


class NodeRegistry:
    """Registers node types and instantiates them from graph definitions."""

    def __init__(self):
        self._registry: Dict[str, Type[BaseNode]] = {}

    def register(self, node_cls: Type[BaseNode]) -> None:
        self._registry[node_cls.type_name] = node_cls

    def create_node(self, node_type: str, node_id: str, config: Optional[dict]) -> BaseNode:
        if node_type not in self._registry:
            raise KeyError(f"Unknown node type '{node_type}'")
        node_cls = self._registry[node_type]
        return node_cls(node_id, config)

    def registered_types(self) -> Dict[str, Type[BaseNode]]:
        return dict(self._registry)


default_registry = NodeRegistry()
