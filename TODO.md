


# General

- Your project must follow clean software architecture principles.
- All errors must be handled gracefully
- Your code must be readable, structured, and documented.

## Makefile

- clean or fclean removes containers


# Agentic Framework

- Implement a Thought → Code → Observation loop
- Your sandbox must provide explicit feedback to the LLM in all of these situations:
    - No valid code block was found in the model’s response
    - A code block was malformed but was interpreted anyway (explain how)
    - Execution hit the timeout and output is partial
    - Tool output was truncated due to size limits
    - An edit introduced a syntax error or lint violation



# Sandbox


## Misc
- Exception propagation:
Your sandbox must correctly propagate exceptions that control program flow. In particular, KeyboardInterrupt and SystemExit must not be silently caught — they need to reach the agent loop for proper shutdown.

- Filesystem restrictions: file access by the sandboxed code is limited to an allowlist of directories (the allowed_directories field of SandboxConfig). 

- Execution timeout: Terminate code exceeding the configured timeout 

- Memory limits: Terminate code exceeding allowed RAM usage

- The MCP tool files (mcp_tools_mbpp.py, mcp_tools_swebench.py) should be located at the root of your repository

- Both stdio or streamable HTTP transports must be supported for MCP server connections


# MBPP

All good!


# SWEBench

Generate and submit valid patches using 
```
’git -c core.fileMode=false diff’
```

Agent system descriptions — how do the top-performing systems design their agent loop, tools, and prompts?




