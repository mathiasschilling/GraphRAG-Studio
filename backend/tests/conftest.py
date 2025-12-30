import os

# Ensure tests always exercise the stubbed LLM to avoid external dependencies
# or Ollama availability during CI runs.
os.environ.setdefault("GRAPHRAG_USE_LLM_STUB", "true")
