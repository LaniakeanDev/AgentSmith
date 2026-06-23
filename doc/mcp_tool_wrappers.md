They're just Python functions dynamically created from the MCP server's tool schemas and injected into the execution namespace. Here's how you'd build them:

```python
async def build_tool_wrappers(session: ClientSession) -> dict:
    """Discover tools from MCP server and create callable wrappers."""
    response = await session.list_tools()
    wrappers = {}
    
    for tool in response.tools:
        # Capture tool.name in closure to avoid late binding issue
        def make_wrapper(tool_name):
            def wrapper(**kwargs):
                # This is synchronous from the LLM code's perspective
                # but calls the async MCP session underneath
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    session.call_tool(tool_name, kwargs)
                )
                # Extract text content from result
                return "\n".join(
                    block.text for block in result.content 
                    if hasattr(block, "text")
                )
            wrapper.__name__ = tool_name
            wrapper.__doc__ = tool.description
            return wrapper
        
        wrappers[tool.name] = make_wrapper(tool.name)
    
    return wrappers
```

Then when building the execution namespace:

```python
async def build_namespace(session: ClientSession, config: SandboxConfig) -> dict:
    tool_wrappers = await build_tool_wrappers(session)
    
    # final_answer is always present, not from MCP
    final_answer_result = {}
    def final_answer(answer):
        final_answer_result["value"] = answer
        raise FinalAnswerException(answer)  # signals agent loop to stop
    
    namespace = {
        "__builtins__": safe_builtins,
        "final_answer": final_answer,
        **tool_wrappers,  # e.g. read_file, search_code, run_tests...
    }
    
    return namespace, final_answer_result
```

So from the LLM-generated code's perspective, it just sees plain callable functions in its namespace:

```python
# LLM-generated code sees this naturally:
result = read_file(filepath="/testbed/src/module.py", start_line=1, end_line=50)
print(result)

content = search_code(pattern="validate_email", file_pattern="*.py")
print(content)

final_answer("def solution(): ...")
```

The wrappers completely hide the async MCP machinery underneath. The LLM doesn't need to know anything about MCP — it just calls functions.

One important detail: the sandbox manual that gets fed to the LLM prompt should be generated from the same tool schemas:

```python
async def generate_sandbox_manual(session: ClientSession) -> str:
    response = await session.list_tools()
    lines = ["# Available Tools\n"]
    
    for tool in response.tools:
        lines.append(f"## {tool.name}")
        lines.append(f"{tool.description}\n")
        lines.append("Parameters:")
        for param_name, param_info in tool.inputSchema.get("properties", {}).items():
            required = param_name in tool.inputSchema.get("required", [])
            lines.append(f"  - {param_name} ({param_info.get('type', 'any')})"
                        f"{'*' if required else ''}: {param_info.get('description', '')}")
        lines.append("")
    
    return "\n".join(lines)
```

This way when a different MCP server is connected, both the wrappers and the manual automatically reflect that server's tools.