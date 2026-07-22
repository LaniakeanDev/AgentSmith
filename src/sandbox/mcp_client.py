import asyncio
# import subprocess
import json
import os
import shlex
from typing import Optional, List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
import aiohttp
from sandbox.sandbox_models import SandboxConfig


# class MCPClient:
#     def __init__(
#         self,
#         task_type: str,
#         config: SandboxConfig,
#         eval_script: str | None = None,
#         test_list: List[str] | None = None,
#         code: str | None = None
#             ):
#         self.task_type = task_type
#         self.config = config
#         self.mcp_cmd = config.mcp_cmd
#         self.conn_type = config.conn_type
#         self.session: Optional[ClientSession] = None
#         self.exit_stack: Optional[AsyncExitStack] = None
#         self.tools = None
#         self.connected = False
#         self.read_stream = None
#         self.write_stream = None
#         self.messages = ""
#         self.eval_script = eval_script
#         self.test_list = test_list
#         self.code = code

#     async def connect_server(self):
#         """Connect to the MCP server using stdio_client"""
#         if self.connected:
#             return None
#         self.exit_stack = AsyncExitStack()
#         cmd_args = shlex.split(self.mcp_cmd)
#         # spawn and manage the server process
#         command = cmd_args[0]
#         args = cmd_args[1:] if len(cmd_args) > 1 else []

#         # resolve any relative script path against the project root
#         PROJECT_ROOT = os.path.dirname(
#             os.path.dirname(os.path.abspath(__file__)))
#         args = [
#             os.path.join(PROJECT_ROOT, a) if not os.path.isabs(a) and
#             a.endswith(".py") else a
#             for a in args
#         ]
#         # print(f"PROJECT_ROOT: {PROJECT_ROOT}")
#         # print(f"Resolved args: {args}")
#         # print(f"Full command: {command} {' '.join(args)}")
#         if self.eval_script is not None:
#             if self.conn_type == 'stdio':
#                 server_params = StdioServerParameters(
#                     command=command,
#                     args=args,
#                     env={"eval_script": self.eval_script}
#                 )
#             else:
#                 pass
#         elif self.test_list is not None:
#             server_params = StdioServerParameters(
#                 command=command,
#                 args=args,
#                 env={
#                         "test_list": str(self.test_list),
#                         "code": self.code
#                     }
#             )
#         else:
#             server_params = StdioServerParameters(
#                 command=command,
#                 args=args,
#             )
#         try:
#             # Start the server and connect to it
#             stdio_transport = await self.exit_stack.enter_async_context(
#                 stdio_client(server_params)
#             )
#             self.read_stream, self.write_stream = stdio_transport
#             # Create client session
#             self.session = await self.exit_stack.enter_async_context(
#                 ClientSession(self.read_stream, self.write_stream)
#             )
#             if self.session is None:
#                 raise Exception("Failed to create client session")
#             # Initialize the session
#             await self.session.initialize()
#             # List available tools
#             response = await self.session.list_tools()
#             self.tools = response.tools
#             self.connected = True

#         except Exception as e:
#             await self.cleanup()
#             raise Exception(
#                 f"Failed to connect to server: {type(e).__name__}: "
#                 f"{str(e)}, cmd: {self.mcp_cmd}")


class MCPClient:
    def __init__(
        self,
        task_type: str,
        config: SandboxConfig,
        eval_script: str | None = None,
        test_list: List[str] | None = None,
        code: str | None = None
    ):
        self.task_type = task_type
        self.config = config
        self.mcp_cmd = config.mcp_command
        self.mcp_url = config.mcp_url
        self.transport = config.transport
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self.tools = None
        self.connected = False
        self.read_stream = None
        self.write_stream = None
        self.messages = ""
        self.eval_script = eval_script
        self.test_list = test_list
        self.code = code

    async def connect_server(self):
        """Connect to the MCP server using the appropriate connection type"""
        if self.connected:
            return None
        self.exit_stack = AsyncExitStack()
        try:
            if self.transport == 'http':
                await self._connect_http()
            else:  # Default to stdio
                await self._connect_stdio()
            # Initialize the session
            await self.session.initialize()
            # List available tools
            response = await self.session.list_tools()
            self.tools = response.tools
            self.connected = True
        except Exception as e:
            await self.cleanup()
            raise Exception(
                f"Failed to connect to server: {type(e).__name__}: "
                f"{str(e)}, transport: {self.transport}"
            )

    async def _connect_stdio(self):
        """Connect using stdio transport"""
        cmd_args = shlex.split(self.mcp_cmd)
        command = cmd_args[0]
        args = cmd_args[1:] if len(cmd_args) > 1 else []

        # Resolve any relative script path against the project root
        PROJECT_ROOT = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        args = [
            os.path.join(PROJECT_ROOT, a) if not os.path.isabs(a) and
            a.endswith(".py") else a
            for a in args
        ]

        # Prepare environment variables
        env = os.environ.copy()
        env["allowed_directories"] = ":".join(self.config.allowed_directories)
        env["transport"] = 'stdio'
        if self.eval_script is not None:
            env["eval_script"] = self.eval_script
        elif self.test_list is not None:
            env["test_list"] = str(self.test_list)
            if self.code:
                env["code"] = self.code

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env if env != os.environ else None  # Only pass if modified
        )

        # Start the server and connect to it
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.read_stream, self.write_stream = stdio_transport
        
        # Create client session
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.read_stream, self.write_stream)
        )

    # async def _connect_http(self):
    #     """Connect using HTTP/SSE transport"""
    #     if not self.mcp_url:
    #         raise ValueError("MCP URL is required for HTTP connection")
        
    #     # Ensure URL has proper format
    #     url = self.mcp_url
    #     if not url.startswith(('http://', 'https://')):
    #         url = f'http://{url}'
        
    #     # Remove trailing slash if present
    #     if url.endswith('/'):
    #         url = url[:-1]
        
    #     # For SSE, the endpoint is typically /sse
    #     sse_url = f"{url}/sse"
        
    #     # Start the HTTP/SSE client
    #     sse_transport = await self.exit_stack.enter_async_context(
    #         sse_client(sse_url)
    #     )
    #     self.read_stream, self.write_stream = sse_transport
        
    #     # Create client session
    #     self.session = await self.exit_stack.enter_async_context(
    #         ClientSession(self.read_stream, self.write_stream)
    #     )

    async def _wait_for_server(self, timeout=30):
        deadline = asyncio.get_running_loop().time() + timeout

        url = self.mcp_url.rstrip("/") + "/mcp"

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url):
                        return
            except Exception:
                if asyncio.get_running_loop().time() > deadline:
                    raise TimeoutError(
                        f"Timed out waiting for MCP server at {url}"
                    )
                await asyncio.sleep(0.2)

    async def _connect_http(self):
        if not self.mcp_url:
            raise ValueError("MCP URL is required")

        cmd_args = shlex.split(self.mcp_cmd)
        command = cmd_args[0]
        args = cmd_args[1:]

        PROJECT_ROOT = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        args = [
            os.path.join(PROJECT_ROOT, a)
            if not os.path.isabs(a) and a.endswith(".py")
            else a
            for a in args
        ]
        env = os.environ.copy()
        env["allowed_directories"] = ":".join(self.config.allowed_directories)
        env["transport"] = 'http'
        env["mcp_url"] = self.mcp_url
        if self.eval_script is not None:
            env["eval_script"] = self.eval_script
        elif self.test_list is not None:
            env["test_list"] = str(self.test_list)
            if self.code:
                env["code"] = self.code

        # print(f"\n\n{command} {args}") 
        # # uv ['run', 'python', '/app/sandbox/default_server.py']

        # Launch the HTTP server
        self.server_process = await asyncio.create_subprocess_exec(
            command,
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(1)
        if self.server_process.returncode is not None:
            stdout, stderr = await self.server_process.communicate()

            message = (
                f"HTTP server exited with code {self.server_process.returncode}\n"
                f"stdout:\n{stdout.decode()}\n"
                f"stderr:\n{stderr.decode()}"
            )
            print(message)
            raise Exception(message)
        # Wait until the server is listening
        await self._wait_for_server()

        url = self.mcp_url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        url += '/mcp'
        self.read_stream, self.write_stream, _ = (
            await self.exit_stack.enter_async_context(
                streamable_http_client(url)
            )
        )

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.read_stream, self.write_stream)
        )

    async def cleanup(self):
        """Clean up resources"""
        if self.exit_stack:
            await self.exit_stack.aclose()
            self.exit_stack = None
        if getattr(self, "server_process", None):
            self.server_process.terminate()
            await self.server_process.wait()
        self.connected = False
        self.session = None
        self.tools = None
        self.read_stream = None
        self.write_stream = None

    # @property
    # def tools(self):
    #     return self.tools

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
        if not self.connected or self.session is None:
            raise Exception("Not connected to server")
        response = await self.session.list_tools()
        self.tools = response.tools

    async def build_tool_wrappers(self, loop=None) -> dict:
        """Discover tools from MCP server and create callable wrappers."""
        wrappers = {}
        await self.get_tools()
        # print(f"DEBUG: Found {len(self.tools)} tools: {[t.name for t in self.tools]}")
        for tool in self.tools:
            # Capture tool and loop in closure to avoid late binding issue
            def make_wrapper(tool, loop=loop):
                # Parameter names in declared order, from the tool's JSON schema
                param_names = list(tool.inputSchema.get("properties", {}).keys())

                def wrapper(*args, **kwargs):
                    if len(args) > len(param_names):
                        raise TypeError(
                            f"{tool.name}() takes {len(param_names)} "
                            f"positional arguments but {len(args)} were given"
                        )
                    # Map positional args onto their named parameters
                    call_kwargs = dict(zip(param_names, args))
                    # Guard against a name being passed both positionally and by keyword
                    overlap = call_kwargs.keys() & kwargs.keys()
                    if overlap:
                        raise TypeError(
                            f"{tool.name}() got multiple values for "
                            f"argument(s): {', '.join(overlap)}"
                        )
                    call_kwargs.update(kwargs)
                    # Check if there's already a running event loop
                    if loop is not None and not loop.is_running():
                        # Use the existing loop (session is bound to it)
                        result = loop.run_until_complete(
                            self.session.call_tool(tool.name, call_kwargs)
                        )
                    elif loop is not None and loop.is_running():
                        # Loop is running - schedule on it
                        future = asyncio.run_coroutine_threadsafe(
                            self.session.call_tool(tool.name, call_kwargs),
                            loop
                        )
                        result = future.result(timeout=60)
                    else:
                        # No loop provided, create a new one
                        result = asyncio.run(
                            self.session.call_tool(tool.name, call_kwargs)
                        )
                    text = "\n".join(
                        block.text for block in result.content
                        if hasattr(block, "text")
                    )
                    to_print = [
                        'search_code', 'edit_file', 'read_file',
                        'search_function_or_class_definition_in_code',
                        'run_tests'
                        ]
                    if tool.name in to_print and "print(" not in self.code:
                        print(text)
                    # Try to parse as JSON - return dict/list if valid JSON
                    try:
                        return json.loads(text)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        # Return raw string for non-JSON responses
                        return text
                    except Exception:
                        return "another exception happened"
                wrapper.__name__ = tool.name
                wrapper.__doc__ = tool.description
                return wrapper
            wrappers[tool.name] = make_wrapper(tool)
        return wrappers

    def generate_sandbox_manual(self) -> str:
        lines = ["## Available Tools\n"]
        for tool in self.tools:
            lines.append(f"### {tool.name}")
            lines.append(f"{tool.description}\n")
            if len(tool.inputSchema) > 0:
                lines.append("Parameters:")
                for param_name, param_info in tool.inputSchema.get(
                        "properties", {}).items():
                    required = param_name in tool.inputSchema.get("required", [])
                    lines.append(
                        f"  - {param_name} ({param_info.get('type', 'any')})"
                        f"{'*' if required else ''}: "
                        f"{param_info.get('description', '')}")
            lines.append("")
        manual = "\n".join(lines)
        self.sandbox_manual = manual
        return manual
