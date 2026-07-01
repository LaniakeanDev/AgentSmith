# MBPP

## Sandbox

?Remove the Docker and use a simple subprocess

Retry logic, provider shift logic

### sandbox CLI usage
```bash
# With MBPP tools (HTTP)
uv run sandbox --mcp-server <URL>
```

### sandbox manual

Generate a sandbox manual to be fed to the LLM prompt, which must include the MCP
tools doc, or how to access it.

The sandbox manual should be dynamically generated from the connected
MCP server’s tool schemas — tool names, descriptions, and parameter types.
When a different MCP server is connected, the manual should automatically
reflect that server’s tools.
The manual is what the LLM reads to understand what tools are available
and how to call them.



## MBPP

### agent CLI interface
```bash
# 1. Dump a task
cd moulinette
uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json
# 2. Run your agent
cd ../student
uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json \
--output ../cache/mbpp_solution.json \
--model-name "model/name" --provider-url "https://provider.api/v1"
# 3. Validate solution
cd ../moulinette
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json \
../cache/mbpp_solution.json
```