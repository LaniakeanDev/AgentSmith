import asyncio
# import subprocess
import os
import shlex
import sys
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self, mcp_cmd: str):
        self.mcp_cmd = mcp_cmd
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self.tools = None
        self.connected = False
        self.read_stream = None
        self.write_stream = None
        self.messages = ""
        # try:
        #     self.spawn_server()
        # except Exception:
        #     raise

    async def connect_server(self):
        """Connect to the MCP server using stdio_client"""
        if self.connected:
            return None
        self.exit_stack = AsyncExitStack()
        cmd_args = shlex.split(self.mcp_cmd)
        # spawn and manage the server process
        command = cmd_args[0]
        args = cmd_args[1:] if len(cmd_args) > 1 else []

        # resolve any relative script path against the project root
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        args = [
            os.path.join(PROJECT_ROOT, a) if not os.path.isabs(a) and a.endswith(".py") else a
            for a in args
        ]
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )
        try:
            # Start the server and connect to it
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.read_stream, self.write_stream = stdio_transport
            # Create client session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read_stream, self.write_stream)
            )
            if self.session is None:
                raise Exception("Failed to create client session")
            # Initialize the session
            await self.session.initialize()
            # List available tools
            response = await self.session.list_tools()
            self.tools = response.tools
            self.messages += \
                f"Connected to server with tools: "\
                f"{[tool.name for tool in self.tools]}"
            self.connected = True

        except Exception as e:
            await self.cleanup()
            raise Exception(
                f"Failed to connect to server: {type(e).__name__}: "
                f"{str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        if self.exit_stack:
            await self.exit_stack.aclose()
            self.exit_stack = None
        self.connected = False
        self.session = None
        self.tools = None
        self.read_stream = None
        self.write_stream = None

    # async def connect_server_stdio_path(self, server_path: str):
    #     """Connect to the MCP server via path

    #     Args:
    #         server_script_path: Path to the server script
    #     """
    #     if self.connected:
    #         return None
    #     self.exit_stack = AsyncExitStack()
    #     server_params = StdioServerParameters(
    #         command="python",
    #         args=[server_path],
    #         env=None
    #     )
    #     stdio_transport = await self.exit_stack.enter_async_context(
    #         stdio_client(server_params)
    #     )
    #     self.read_stream, self.write_stream = stdio_transport
    #     # Enter the ClientSession context manually
    #     self.session = await self.exit_stack.enter_async_context(
    #         ClientSession(self.read_stream, self.write_stream)
    #     )
    #     await self.session.initialize()
    #     response = await self.session.list_tools()
    #     self.tools = response.tools
    #     print("\nConnected to server with tools:",
    #           [tool.name for tool in self.tools])
    #     self.connected = True

    async def get_tools(self) -> None:
        """Discover tools from MCP server"""
        response = await self.session.list_tools()
        self.tools = response.tools

    async def build_tool_wrappers(self) -> dict:
        """Discover tools from MCP server and create callable wrappers."""
        await self.get_tools()
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
