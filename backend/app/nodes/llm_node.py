from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Any, Dict

from ..core.context import ExecutionContext
from ..core.node_base import BaseNode, default_registry
from ..services import call_ollama_generate


@dataclass
class LLMConfig:
    model: str = "llama3"
    system_prompt: str | None = None
    user_template: str | None = None
    # Legacy single-field prompt support for already-saved flows.
    prompt: str | None = None
    output_key: str = "response"
    # When true, attempt to remove "reasoning" wrappers (e.g., <think>...</think>)
    # from the model output so only the final answer is returned as the output key.
    strip_reasoning: bool = False


_REASONING_TAGS = ("think", "thinking", "analysis", "reasoning", "reflect", "reflection")


def _strip_reasoning_tokens(text: str) -> str:
    """Remove common reasoning wrappers while keeping the final answer intact.

    This targets known tag pairs (<think>...</think>, <analysis>...</analysis>, etc.),
    heading-style prefixes ("Reasoning:"/"Thoughts:"), and "Answer:" markers.
    Falls back to the original text if stripping would empty the content.
    """

    if not isinstance(text, str):
        return text

    cleaned = text

    # Drop tagged reasoning blocks
    for tag in _REASONING_TAGS:
        cleaned = re.sub(
            rf"<{tag}>\s*.*?\s*</{tag}>",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

    cleaned = cleaned.strip()

    # Remove a leading reasoning heading line if present
    lines = cleaned.splitlines()
    if lines and re.match(r"(?i)\s*(reasoning|analysis|thoughts?|reflection)\s*[:：]", lines[0]):
        lines = lines[1:]
        # Drop a following blank line to avoid leading whitespace
        while lines and lines[0].strip() == "":
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()

    # If an explicit answer marker exists, take the last one to keep the final answer
    answer_match = re.search(r"(?is)(answer|final answer)\s*[:：]\s*(.+)", cleaned)
    if answer_match:
        cleaned = answer_match.group(2).strip()

    # Remove trailing literal escape sequences like "\n\n" as well as
    # newline/whitespace characters.
    cleaned = re.sub(r"(\\[nrt])+(\s*)$", "", cleaned).strip()

    return cleaned or text.strip()


class LLMNode(BaseNode):
    type_name = "LLMNode"
    ConfigModel = LLMConfig

    async def execute(self, ctx: ExecutionContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        template = self.config.user_template or self.config.prompt or ""

        safe_inputs = defaultdict(str, inputs)
        if "input" not in safe_inputs and "prompt" in safe_inputs:
            safe_inputs["input"] = safe_inputs["prompt"]
        if "text" not in safe_inputs and "prompt" in safe_inputs:
            safe_inputs["text"] = safe_inputs["prompt"]
        user_prompt = (
            template.format_map(safe_inputs)
            if template
            else inputs.get("prompt") or inputs.get("input") or inputs.get("text") or ""
        )

        system_prompt = (self.config.system_prompt or "").strip()
        prompt_parts = [part for part in [system_prompt, str(user_prompt).strip()] if part]
        prompt = "\n\n".join(prompt_parts)
        response = await call_ollama_generate(self.config.model, prompt)
        if getattr(self.config, "strip_reasoning", False):
            response = _strip_reasoning_tokens(response)
        output_key = (self.config.output_key or "response").strip() or "response"
        return {output_key: response}


default_registry.register(LLMNode)
