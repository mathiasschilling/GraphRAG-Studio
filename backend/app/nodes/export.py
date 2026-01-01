from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict

from ..config import get_settings
from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry


@dataclass
class ExportConfig:
    mode: str = "key"  # "key" or "run_log"
    key: str = "response"
    filename: str | None = None
    output_key: str = "export_path"
    input_key: str = "input"


def _safe_filename(name: str) -> str:
    safe = Path(name).name or "export.json"
    if not safe.lower().endswith(".json"):
        safe = f"{safe}.json"
    return safe


def _default_filename(node_id: str, mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return _safe_filename(f"{node_id}_{mode}_{stamp}.json")


class ExportNode(BaseNode):
    type_name = "ExportNode"
    ConfigModel = ExportConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        mode = (self.config.mode or "key").strip().lower()
        if mode not in {"key", "run_log"}:
            mode = "key"

        if mode == "run_log":
            payload: Any = ctx.run_log
        else:
            key = (self.config.key or "response").strip() or "response"
            if key in inputs:
                value = inputs[key]
            else:
                value = ctx.global_values.get(key)
            payload = {"key": key, "value": value}

        settings = get_settings()
        export_dir = Path(settings.storage_path) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        filename = _safe_filename(self.config.filename) if self.config.filename else _default_filename(self.id, mode)
        file_path = export_dir / filename
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        output_key = (self.config.output_key or "export_path").strip() or "export_path"
        return {output_key: str(file_path)}


default_registry.register(ExportNode)
