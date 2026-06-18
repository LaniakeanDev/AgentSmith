import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# from dotenv import load_dotenv

# load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools = None

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script
        """
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )
        stdio_transport = await \
            self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await \
            self.exit_stack.enter_async_context(ClientSession(
                self.stdio, self.write))
        await self.session.initialize()
        # List available tools
        response = await self.session.list_tools()
        self.tools = response.tools
        print("\nConnected to server with tools:\
              ", [tool.name for tool in self.tools])

    async def get_tools(self) -> None:
        """Discover tools from MCP server"""
        response = await self.session.list_tools()
        self.tools = response.tools

    def build_tool_wrappers(self) -> dict:
        """Discover tools from MCP server and create callable wrappers."""
        wrappers = {}
        for tool in self.tools:
            # Capture tool.name in closure to avoid late binding issue
            def make_wrapper(tool_name):
                def wrapper(**kwargs):
                    # This is synchronous from the LLM code's perspective
                    # but calls the async MCP session underneath
                    # import asyncio
                    result = asyncio.get_event_loop().run_until_complete(
                        self.session.call_tool(tool_name, kwargs)
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

    def generate_sandbox_manual(self) -> str:
        lines = ["# Available Tools\n"]
        for tool in self.tools:
            lines.append(f"## {tool.name}")
            lines.append(f"{tool.description}\n")
            lines.append("Parameters:")
            for param_name, param_info in tool.inputSchema.get(
                    "properties", {}).items():
                required = param_name in tool.inputSchema.get("required", [])
                lines.append(
                    f"  - {param_name} ({param_info.get('type', 'any')})"
                    f"{'*' if required else ''}: {param_info.get(
                        'description', '')}")
            lines.append("")
        self.sandbox_manual = "\n".join(lines)
