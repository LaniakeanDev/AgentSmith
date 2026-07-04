import asyncio

from swe_models import SWEBenchTaskInput

# from .constants import DEFAULT_SERVER_PATH
from .sandbox_models import SandboxConfig, ExecutionResult
# from .mcp_client import MCPClient
import subprocess
import json
import os
# from .constants import safe_builtins
import shlex


# class TimeoutError(Exception):
#     pass


# def timeout_handler(signum, frame):
#     raise TimeoutError("Execution timed out")


class Spawner:
    def __init__(self,
                 config: SandboxConfig,
                 server_path: str | None = None,
                 mcp_command: str | None = None) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.config = config
        self.config.server_path = server_path
        self.config.mcp_command = mcp_command
        # self.server_path = server_path
        # self.mcp_client = MCPClient()
        self.exec_count: int = 0
        # self.mcp_command = mcp_command
        if mcp_command is not None:
            self.parse_mcp_cmd(mcp_command)
            # split_cmd = shlex.split(mcp_command)
            # for word in split_cmd:
            #     if self.is_mcp_server_file(word):
            #         try:
            #             with open(word, 'r') as f:
            #                 content = f.read()
            #             filename = word.split('/').pop()
            #             with open('src/sandbox/' + filename, 'w') as f:
            #                 f.write(content)
            #             # self.server_path = filename
            #             self.config.server_path = filename
            #             self.config.mcp_command = mcp_command
            #         except Exception as e:
            #             print(f"WARNING: {type(e).__name__}: {str(e)}")
            #             print("Using default MCP server instead")
            #         finally:
            #             break

    def parse_mcp_cmd(self, cmd: str) -> None:
        split_cmd = shlex.split(cmd)
        for word in split_cmd:
            if self.is_mcp_server_file(word):
                try:
                    with open(word, 'r') as f:
                        content = f.read()
                    filename = word.split('/').pop()
                    with open('src/sandbox/' + filename, 'w') as f:
                        f.write(content)
                    # self.server_path = filename
                    self.config.server_path = filename
                    self.config.mcp_command = cmd
                except Exception as e:
                    print(f"WARNING: {type(e).__name__}: {str(e)}")
                    print("Using default MCP server instead")
                finally:
                    break

    def is_mcp_server_file(self, file_path):
        """
        Check if a file could be an MCP server based on common extensions.
        """
        mcp_extensions = {
            '.py', '.js', '.ts', '.go', '.rs', '.rb',
            '.java', '.cs', '.kt', '.swift'
        }
        if not os.path.isfile(file_path):
            return False
        ext = os.path.splitext(file_path)[1].lower()
        return ext in mcp_extensions

    # def configure(self):
    #     if self.server_path is None:
    #         self.server_path = DEFAULT_SERVER_PATH
    #     self.loop.run_until_complete(
    #         self.mcp_client.connect_server_stdio_path(self.server_path)
    #     )
    #     self.restricted_globals = self.loop.run_until_complete(
    #         self.build_globals()
    #     )

    def spawn(self, code: str, task: SWEBenchTaskInput) -> ExecutionResult:
        """Execute LLM-generated code in restricted environment"""
        self.exec_count += 1
        subprocess_inputs = {
            "config": self.config.model_dump(),
            "code": code,
            "eval_script": task.eval_script
        }
        docker_cmd = [
            "docker", "run",
            "--rm",
            # "--network=none"
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            f"--memory={self.config.max_memory_mb}m",
            "--cpus=1",
            "-i",
            "sandbox-image",
            "uv", "run", "python", "-m", "sandbox_mbpp"
        ]
        try:
            result = subprocess.run(
                docker_cmd,
                input=json.dumps(subprocess_inputs),
                text=True,
                capture_output=True,
                timeout=self.config.max_execution_time_seconds
            )
            import pprint
            pprint.pprint(result)
            try:
                output_data = json.loads(result.stdout)
                if output_data["success"] and "final_answer" in output_data:
                    # import pprint
                    # pprint.pprint(output_data)
                    return ExecutionResult(
                        success=True,
                        final_answer=output_data["final_answer"],
                        output=output_data["output"]
                    )
                elif output_data["success"]:
                    return ExecutionResult(
                        success=True,
                        output=output_data["output"],
                    )
                else:
                    error = output_data["error"]
                    return ExecutionResult(
                        success=False,
                        output=output_data["output"] or ("No output from "
                                                         "execution"),
                        error=f"Spawner: Error during sandbox execution:"
                              f" {error}"
                    )
            except json.JSONDecodeError:
                error = f"Spawner: The sandbox output isn't "\
                        f"parseable: {result.stdout}\n{result.stderr}"
                return ExecutionResult(
                    success=False,
                    output=result.stdout,
                    error=error
                )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="No output from execution",
                error=f"Spawner: Sandbox execution timed out after "
                      f"{self.config.max_execution_time_seconds} seconds",
            )
        except KeyboardInterrupt:
            return ExecutionResult(
                success=False,
                output="\nUser interrupted execution",
                error="\nUser interrupted execution",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="No output from execution",
                error=f"Spawner: {type(e).__name__}: {str(e)}",
            )

    # def restricted_import_factory(self):
    #     """Create import filter bound to config"""
    #     def restricted_import(name, *args, **kwargs):
    #         if name in self.config.authorized_imports:
    #             return __import__(name, *args, **kwargs)
    #         authorized_imports_str = ""
    #         for item in self.config.authorized_imports:
    #             authorized_imports_str += f"{item}, "
    #             if item.endswith('.*'):
    #                 prefix = item[:-2]
    #                 if name == prefix or name.startswith(prefix + '.'):
    #                     return __import__(name, *args, **kwargs)
    #         authorized_imports_str = authorized_imports_str[:-2]
    #         message = f"Import of '{name}' is not allowed.\n"
    #         message += f"Authorized imports: {authorized_imports_str}"
    #         raise ImportError(message)
    #     return restricted_import

    # def restricted_open_factory(self):
    #     allowed = [
    #         os.path.realpath(p)
    #         for p in self.config.allowed_directories
    #     ]

    #     def restricted_open(path, *args, **kwargs):
    #         real = os.path.realpath(path)
    #         for root in allowed:
    #             if (real == root
    #                     or real.startswith(root + os.sep)):
    #                 return open(real, *args, **kwargs)
    #         raise PermissionError(f"Unauthorized path: {path}")

    #     return restricted_open

    # async def build_globals(self):
    #     builtins = safe_builtins.copy()
    #     builtins["open"] = self.restricted_open_factory()
    #     builtins['__import__'] = self.restricted_import_factory()
    #     tool_wrappers = await self.mcp_client.build_tool_wrappers()
    #     restricted_globals = {
    #         '__builtins__': builtins,
    #         'final_answer': self.handle_final_answer,
    #         **tool_wrappers
    #     }
    #     return restricted_globals

    # # def set_mem_limit(self):
    # #     max_mem_bytes = self.config.max_memory_mb * 1024 * 1024
    # #     resource.setrlimit(
    # #           resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))

    # def handle_final_answer(self, answer: str):
    #     raise FinalAnswer(answer)
