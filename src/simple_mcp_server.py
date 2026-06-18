#!/usr/bin/env python3
"""
Simple one-file MCP server example
"""

import asyncio
from typing import Any, Dict, List
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

# Create server instance
server = Server("simple-server")


# Define available tools
@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List all available tools"""
    return [
        types.Tool(
            name="echo",
            description="Echo back the input message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo"
                    }
                },
                "required": ["message"]
            }
        ),
        types.Tool(
            name="add",
            description="Add two numbers together",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["a", "b"]
            }
        )
    ]


# Handle tool calls
@server.call_tool()
async def handle_call_tool(
        name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool execution"""
    if name == "echo":
        message = arguments.get("message", "")
        return [types.TextContent(type="text", text=f"Echo: {message}")]

    elif name == "add":
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        result = a + b
        return [types.TextContent(type="text", text=f"Result: {result}")]

    else:
        raise ValueError(f"Unknown tool: {name}")


# Define available resources (optional)
@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    """List available resources"""
    return [
        types.Resource(
            uri="info://server",
            name="Server Information",
            description="Information about this MCP server",
            mimeType="text/plain",
        )
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read resource content"""
    if uri == "info://server":
        return "Simple MCP Server running in one file!"
    raise ValueError(f"Unknown resource: {uri}")


# Define prompts (optional)
@server.list_prompts()
async def handle_list_prompts() -> List[types.Prompt]:
    """List available prompts"""
    return [
        types.Prompt(
            name="greeting",
            description="A friendly greeting prompt",
            arguments=[
                types.PromptArgument(
                    name="name",
                    description="Your name",
                    required=True
                )
            ]
        )
    ]


@server.get_prompt()
async def handle_get_prompt(
        name: str, arguments: Dict[str, str]) -> types.GetPromptResult:
    """Get prompt content"""
    if name == "greeting":
        name_arg = arguments.get("name", "World")
        return types.GetPromptResult(
            description="A greeting message",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Hello, {name_arg}! Welcome to the MCP server."
                    )
                )
            ]
        )
    raise ValueError(f"Unknown prompt: {name}")


async def main():
    """Main entry point"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="simple-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
