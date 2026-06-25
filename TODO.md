# MBPP

## sandbox manual

Generate a sandbox manual to be fed to the LLM prompt, which must include the MCP
tools doc, or how to access it.

The sandbox manual should be dynamically generated from the connected
MCP server’s tool schemas — tool names, descriptions, and parameter types.
When a different MCP server is connected, the manual should automatically
reflect that server’s tools.
The manual is what the LLM reads to understand what tools are available
and how to call them.

