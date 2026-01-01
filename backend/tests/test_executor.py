import asyncio

import pytest

from app.core.executor import execute_graph
from app.core.graph import EdgeDefinition, FlowGraph, NodeDefinition


def test_simple_graph_execution():
    graph = FlowGraph(
        id="demo",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "prompt": NodeDefinition(id="prompt", type="PromptTemplateNode", config={"template": "Hello {input}"}),
            "llm": NodeDefinition(id="llm", type="LLMNode", config={"model": "test-model"}),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "response"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="prompt", from_output="input"),
            EdgeDefinition(id="e2", from_node="prompt", to_node="llm", from_output="prompt"),
            EdgeDefinition(id="e3", from_node="llm", to_node="final", from_output="response"),
        ],
    )

    result = asyncio.run(execute_graph(graph, {"name": "GraphRAG"}))

    assert result.outputs["prompt"]["prompt"] == "Hello {'name': 'GraphRAG'}"
    assert result.outputs["llm"]["response"] == "[test-model] Hello {'name': 'GraphRAG'}"
    assert result.outputs["final"]["output"] == "[test-model] Hello {'name': 'GraphRAG'}"
    assert result.node_logs
    assert result.started_at <= result.completed_at


def test_detects_cycle():
    graph = FlowGraph(
        id="cycle",
        nodes={
            "a": NodeDefinition(id="a", type="UserInputNode"),
            "b": NodeDefinition(id="b", type="PromptTemplateNode", config={"template": "{input}"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="a", to_node="b", from_output="input"),
            EdgeDefinition(id="e2", from_node="b", to_node="a", from_output="prompt"),
        ],
    )

    with pytest.raises(Exception):
        asyncio.run(execute_graph(graph, "data"))


def test_condition_node_skips_downstream_when_false():
    graph = FlowGraph(
        id="conditional",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode", config={"key": "value"}),
            "check": NodeDefinition(
                id="check",
                type="ConditionNode",
                config={"input_key": "value", "compare_value": "5", "operator": "gt"},
            ),
            "llm": NodeDefinition(id="llm", type="LLMNode", config={"model": "test-model"}),
        },
        edges=[
            EdgeDefinition(
                id="e1",
                from_node="user",
                to_node="check",
                from_output="value",
                to_input="value",
            ),
            EdgeDefinition(
                id="e2",
                from_node="check",
                to_node="llm",
                from_output="condition",
                to_input="condition",
            ),
        ],
    )

    result = asyncio.run(execute_graph(graph, 3))

    # Condition should be false (3 > 5 is False) which skips the LLM node
    assert "llm" not in result.outputs
    assert any(log.node_id == "llm" and log.skipped for log in result.node_logs)


def test_condition_branches_activate_true_or_false_handles():
    graph = FlowGraph(
        id="branching",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "check": NodeDefinition(
                id="check",
                type="ConditionNode",
                config={"input_key": "input", "compare_value": "5", "operator": "gt"},
            ),
            "llm_true": NodeDefinition(id="llm_true", type="LLMNode", config={"model": "test-model"}),
            "llm_false": NodeDefinition(id="llm_false", type="LLMNode", config={"model": "test-model"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="check", from_output="input"),
            EdgeDefinition(id="e2", from_node="check", to_node="llm_true", from_output="true", to_input="prompt"),
            EdgeDefinition(id="e3", from_node="check", to_node="llm_false", from_output="false", to_input="prompt"),
        ],
    )

    result = asyncio.run(execute_graph(graph, 10))

    # True branch should run, false branch should be skipped entirely
    assert result.outputs["check"]["condition"] is True
    assert result.outputs["check"]["true"] == 10
    assert result.outputs["llm_true"]["response"] == "[test-model] 10"
    assert "llm_false" not in result.outputs
    assert any(log.node_id == "llm_false" and log.skipped for log in result.node_logs)


def test_condition_allows_custom_branch_keys():
    graph = FlowGraph(
        id="branching-custom-keys",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "check": NodeDefinition(
                id="check",
                type="ConditionNode",
                config={
                    "input_key": "input",
                    "compare_value": "5",
                    "operator": "gt",
                    "true_key": "pass",
                    "false_key": "fail",
                },
            ),
            "llm_true": NodeDefinition(id="llm_true", type="LLMNode", config={"model": "test-model"}),
            "llm_false": NodeDefinition(id="llm_false", type="LLMNode", config={"model": "test-model"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="check", from_output="input"),
            EdgeDefinition(id="e2", from_node="check", to_node="llm_true", from_output="pass", to_input="prompt"),
            EdgeDefinition(id="e3", from_node="check", to_node="llm_false", from_output="fail", to_input="prompt"),
        ],
    )

    result = asyncio.run(execute_graph(graph, 10))

    assert result.outputs["check"]["condition"] is True
    assert result.outputs["check"]["pass"] == 10
    assert result.outputs["llm_true"]["response"] == "[test-model] 10"
    assert "llm_false" not in result.outputs
    assert any(log.node_id == "llm_false" and log.skipped for log in result.node_logs)


def test_condition_pass_through_preserves_original_input():
    graph = FlowGraph(
        id="branching-pass-through",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "check_prompt": NodeDefinition(
                id="check_prompt",
                type="PromptTemplateNode",
                config={"template": "true"},
            ),
            "check": NodeDefinition(
                id="check",
                type="ConditionNode",
                config={
                    "input_key": "check",
                    "pass_through_key": "input",
                    "compare_value": "true",
                    "operator": "eq",
                },
            ),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="check", from_output="input", to_input="input"),
            EdgeDefinition(
                id="e2",
                from_node="check_prompt",
                to_node="check",
                from_output="prompt",
                to_input="check",
            ),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Keep me"))

    assert result.outputs["check"]["condition"] is True
    assert result.outputs["check"]["value"] == "true"
    assert result.outputs["check"]["true"] == "Keep me"
    assert result.outputs["check"]["false"] is None


def test_llm_consumes_default_input_when_prompt_missing():
    graph = FlowGraph(
        id="direct-llm",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm": NodeDefinition(id="llm", type="LLMNode", config={"model": "test-model"}),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "response"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="llm", from_output="input"),
            EdgeDefinition(id="e2", from_node="llm", to_node="final", from_output="response"),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Echo me"))

    # With no explicit prompt input handle, the LLM node should fall back to
    # the upstream "input" value so downstream nodes still receive a response.
    assert result.outputs["llm"]["response"] == "[test-model] Echo me"
    assert result.outputs["final"]["output"] == "[test-model] Echo me"


def test_prompt_receives_explicit_and_default_inputs():
    graph = FlowGraph(
        id="multi-input",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "check": NodeDefinition(
                id="check",
                type="ConditionNode",
                config={"input_key": "input", "compare_value": "", "operator": "neq"},
            ),
            "prompt": NodeDefinition(
                id="prompt",
                type="PromptTemplateNode",
                config={"template": "Question: {input}. Seen: {extra}"},
            ),
            "llm": NodeDefinition(id="llm", type="LLMNode", config={"model": "test-model"}),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "response"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="check", from_output="input"),
            EdgeDefinition(id="e2", from_node="check", to_node="prompt", from_output="value", to_input="extra"),
            EdgeDefinition(id="e3", from_node="user", to_node="prompt", from_output="input"),
            EdgeDefinition(id="e4", from_node="prompt", to_node="llm", from_output="prompt"),
            EdgeDefinition(id="e5", from_node="llm", to_node="final", from_output="response"),
        ],
    )

    result = asyncio.run(execute_graph(graph, "GraphRAG"))

    # The prompt node should see both the default "input" key from the direct
    # edge and the explicitly named "extra" value from the condition node.
    assert result.outputs["prompt"]["prompt"] == "Question: GraphRAG. Seen: GraphRAG"
    assert result.outputs["llm"]["response"] == "[test-model] Question: GraphRAG. Seen: GraphRAG"
    assert result.outputs["final"]["output"] == "[test-model] Question: GraphRAG. Seen: GraphRAG"


def test_chained_llms_receive_prompt_defaults():
    graph = FlowGraph(
        id="chained-llms",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm1": NodeDefinition(id="llm1", type="LLMNode", config={"model": "test-model"}),
            "llm2": NodeDefinition(id="llm2", type="LLMNode", config={"model": "test-model"}),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "response"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", from_output="", to_node="llm1"),
            EdgeDefinition(id="e2", from_node="llm1", from_output="", to_node="llm2"),
            EdgeDefinition(id="e3", from_node="llm2", from_output="", to_node="final"),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Chain me"))

    assert result.outputs["llm1"]["response"] == "[test-model] Chain me"
    assert result.outputs["llm2"]["response"] == "[test-model] [test-model] Chain me"
    assert result.outputs["final"]["output"] == "[test-model] [test-model] Chain me"


def test_llm_renders_system_and_user_templates():
    graph = FlowGraph(
        id="system-user-templates",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm": NodeDefinition(
                id="llm",
                type="LLMNode",
                config={
                    "model": "test-model",
                    "system_prompt": "You are a helpful assistant.",
                    "user_template": "User said: {input}",
                },
            ),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "response"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="llm", from_output="input"),
            EdgeDefinition(id="e2", from_node="llm", to_node="final", from_output="response"),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Hello"))

    expected_prompt = "You are a helpful assistant.\n\nUser said: Hello"
    assert result.outputs["llm"]["response"] == f"[test-model] {expected_prompt}"
    assert result.outputs["final"]["output"] == f"[test-model] {expected_prompt}"


def test_downstream_llm_can_reference_response_alias():
    graph = FlowGraph(
        id="llm-chains-response-alias",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm_primary": NodeDefinition(
                id="llm_primary",
                type="LLMNode",
                config={"model": "model-a", "user_template": "First turn: {input}"},
            ),
            "llm_secondary": NodeDefinition(
                id="llm_secondary",
                type="LLMNode",
                config={"model": "model-b", "user_template": "Follow up on {response}"},
            ),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "response"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="llm_primary", from_output=""),
            EdgeDefinition(id="e2", from_node="llm_primary", to_node="llm_secondary", from_output=""),
            EdgeDefinition(id="e3", from_node="llm_secondary", to_node="final", from_output=""),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Hello again"))

    assert result.outputs["llm_primary"]["response"] == "[model-a] First turn: Hello again"
    assert result.outputs["llm_secondary"]["response"] == "[model-b] Follow up on [model-a] First turn: Hello again"
    assert result.outputs["final"]["output"] == "[model-b] Follow up on [model-a] First turn: Hello again"


def test_prompt_template_can_use_response_key():
    graph = FlowGraph(
        id="prompt-uses-response-alias",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm": NodeDefinition(id="llm", type="LLMNode", config={"model": "model-a"}),
            "prompt": NodeDefinition(
                id="prompt",
                type="PromptTemplateNode",
                config={"template": "Previous response was: {response}"},
            ),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "prompt"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="llm", from_output=""),
            EdgeDefinition(id="e2", from_node="llm", to_node="prompt", from_output=""),
            EdgeDefinition(id="e3", from_node="prompt", to_node="final", from_output=""),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Alias me"))

    assert result.outputs["prompt"]["prompt"] == "Previous response was: [model-a] Alias me"
    assert result.outputs["final"]["output"] == "Previous response was: [model-a] Alias me"


def test_llm_output_key_overrides_default_output():
    graph = FlowGraph(
        id="llm-output-key",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm": NodeDefinition(
                id="llm",
                type="LLMNode",
                config={"model": "test-model", "output_key": "summary"},
            ),
            "prompt": NodeDefinition(
                id="prompt",
                type="PromptTemplateNode",
                config={"template": "Summary: {summary}"},
            ),
            "final": NodeDefinition(id="final", type="FinalAnswerNode", config={"key": "prompt"}),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="llm", from_output=""),
            EdgeDefinition(id="e2", from_node="llm", to_node="prompt", from_output=""),
            EdgeDefinition(id="e3", from_node="prompt", to_node="final", from_output=""),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Hello"))

    assert result.outputs["llm"]["summary"] == "[test-model] Hello"
    assert result.outputs["prompt"]["prompt"] == "Summary: [test-model] Hello"
    assert result.outputs["final"]["output"] == "Summary: [test-model] Hello"


def test_custom_keys_flow_through_prompt_llm_and_final():
    graph = FlowGraph(
        id="custom-keys-end-to-end",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode", config={"key": "user_text"}),
            "prompt": NodeDefinition(
                id="prompt",
                type="PromptTemplateNode",
                config={"template": "Ask: {user_text}", "output_key": "question"},
            ),
            "llm": NodeDefinition(
                id="llm",
                type="LLMNode",
                config={
                    "model": "test-model",
                    "user_template": "Answer: {question}",
                    "output_key": "answer",
                },
            ),
            "final": NodeDefinition(
                id="final",
                type="FinalAnswerNode",
                config={"key": "answer", "output_key": "final"},
            ),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="prompt", from_output=""),
            EdgeDefinition(id="e2", from_node="prompt", to_node="llm", from_output=""),
            EdgeDefinition(id="e3", from_node="llm", to_node="final", from_output=""),
        ],
    )

    result = asyncio.run(execute_graph(graph, "Hello"))

    assert result.outputs["prompt"]["question"] == "Ask: Hello"
    assert result.outputs["llm"]["answer"] == "[test-model] Answer: Ask: Hello"
    assert result.outputs["final"]["final"] == "[test-model] Answer: Ask: Hello"


def test_custom_condition_input_and_branch_keys_flow():
    graph = FlowGraph(
        id="custom-keys-condition",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode", config={"key": "payload"}),
            "prompt": NodeDefinition(
                id="prompt",
                type="PromptTemplateNode",
                config={"template": "{payload}", "output_key": "criteria"},
            ),
            "check": NodeDefinition(
                id="check",
                type="ConditionNode",
                config={
                    "input_key": "criteria",
                    "compare_value": "go",
                    "operator": "eq",
                    "true_key": "yes",
                    "false_key": "no",
                },
            ),
            "llm_true": NodeDefinition(
                id="llm_true",
                type="LLMNode",
                config={"model": "test-model", "user_template": "Proceed {yes}"},
            ),
            "llm_false": NodeDefinition(
                id="llm_false",
                type="LLMNode",
                config={"model": "test-model", "user_template": "Stop {no}"},
            ),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="prompt", from_output=""),
            EdgeDefinition(id="e2", from_node="prompt", to_node="check", from_output=""),
            EdgeDefinition(id="e3", from_node="check", to_node="llm_true", from_output="yes", to_input="prompt"),
            EdgeDefinition(id="e4", from_node="check", to_node="llm_false", from_output="no", to_input="prompt"),
        ],
    )

    result = asyncio.run(execute_graph(graph, "go"))

    assert result.outputs["prompt"]["criteria"] == "go"
    assert result.outputs["check"]["condition"] is True
    assert result.outputs["check"]["yes"] == "go"
    assert result.outputs["llm_true"]["response"] == "[test-model] Proceed go"
    assert "llm_false" not in result.outputs
    assert any(log.node_id == "llm_false" and log.skipped for log in result.node_logs)


def test_llm_reasoning_strip_opt_in():
    graph = FlowGraph(
        id="strip-reasoning",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm_raw": NodeDefinition(
                id="llm_raw",
                type="LLMNode",
                config={
                    "model": "model-a",
                    "user_template": "Return raw {input}",
                    "strip_reasoning": False,
                },
            ),
            "llm_clean": NodeDefinition(
                id="llm_clean",
                type="LLMNode",
                config={
                    "model": "model-b",
                    "user_template": "Return raw {input}",
                    "strip_reasoning": True,
                },
            ),
        },
        edges=[
            EdgeDefinition(id="e1", from_node="user", to_node="llm_raw", from_output=""),
            EdgeDefinition(id="e2", from_node="user", to_node="llm_clean", from_output=""),
        ],
    )

    # Simulate a model response that contains a reasoning tag and a final answer.
    # call_ollama_generate stubs to "[model] prompt" in tests; we mimic the tag
    # inside the prompt to ensure the stripper is exercised.
    result = asyncio.run(execute_graph(graph, "<think>meta</think> Final answer"))

    raw_response = result.outputs["llm_raw"]["response"]
    cleaned_response = result.outputs["llm_clean"]["response"]

    assert raw_response == "[model-a] Return raw <think>meta</think> Final answer"
    assert "<think>" not in cleaned_response.lower()
    assert cleaned_response.endswith("Final answer")


def test_llm_reasoning_strip_handles_headings_and_answer_marker():
    graph = FlowGraph(
        id="strip-headings",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm": NodeDefinition(
                id="llm",
                type="LLMNode",
                config={
                    "model": "model-a",
                    "strip_reasoning": True,
                    "user_template": "Reasoning: some chain\n\nAnswer: {input}",
                },
            ),
        },
        edges=[EdgeDefinition(id="e1", from_node="user", to_node="llm", from_output="")],
    )

    result = asyncio.run(execute_graph(graph, "Final here"))

    cleaned = result.outputs["llm"]["response"]
    assert cleaned == "Final here"


def test_llm_reasoning_strip_trims_trailing_escapes():
    graph = FlowGraph(
        id="strip-escapes",
        nodes={
            "user": NodeDefinition(id="user", type="UserInputNode"),
            "llm": NodeDefinition(
                id="llm",
                type="LLMNode",
                config={
                    "model": "model-a",
                    "strip_reasoning": True,
                    "user_template": "Answer: {input}\\n\\n",
                },
            ),
        },
        edges=[EdgeDefinition(id="e1", from_node="user", to_node="llm", from_output="")],
    )

    result = asyncio.run(execute_graph(graph, "Done"))

    assert result.outputs["llm"]["response"] == "Done"
