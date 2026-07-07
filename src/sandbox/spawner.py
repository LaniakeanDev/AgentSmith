import asyncio
from typing import List

from agent_swebench.swebench_models import SWEBenchTaskInput
from agent_mbpp.mbpp_models import MBPPTaskInput
from models import SandboxConfig, ExecutionResult
import subprocess
import json
import os
import shlex


class Spawner:
    def __init__(self,
                 config: SandboxConfig,
                 task: SWEBenchTaskInput | MBPPTaskInput | None = None,
                 server_path: str | None = None,
                 mcp_command: str | None = None
                 ) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.config = config
        self.task = task
        self.config.server_path = server_path
        self.config.mcp_command = mcp_command
        self.exec_count: int = 0
        if mcp_command is not None:
            self.parse_mcp_cmd(mcp_command)

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

    def spawn(
            self,
            code: str,
            docker_cmd: List[str],
            # task_type: str,
            # task: SWEBenchTaskInput,
            # container_name: str
              ) -> ExecutionResult:
        """Execute LLM-generated code in restricted environment"""
        print("DEBUG: spawner.spawn()")
        if isinstance(self.task, MBPPTaskInput):
            task_type = "mbpp"
            subprocess_inputs = {
                "config": self.config.model_dump(),
                "code": code,
                "task_type": task_type,
                "test_list": self.task.test_list
            }
            print("MBPP task. To be refactored")
            import sys
            sys.exit(0)
        elif isinstance(self.task, SWEBenchTaskInput):
            task_type = "swebench"
            subprocess_inputs = {
                "config": self.config.model_dump(),
                "code": code,
                "task_type": task_type,
                "eval_script": self.task.eval_script
            }
        else:
            task_type = "sandbox"
            subprocess_inputs = {
                "config": self.config.model_dump(),
                "code": code,
                "task_type": task_type,
            }
        self.exec_count += 1
        try:
            print("DEBUG: result = subprocess.run")
            result = subprocess.run(
                docker_cmd,
                input=json.dumps(subprocess_inputs),
                text=True,
                capture_output=True,
                timeout=self.config.max_execution_time_seconds
            )
            print("DEBUG: subprocess.run done")
            try:
                output_data = json.loads(result.stdout)
                if output_data["success"] and "final_answer" in output_data:
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
            raise
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="No output from execution",
                error=f"Spawner: {type(e).__name__}: {str(e)}",
            )




# import asyncio

# from agent_swebench.swebench_models import SWEBenchTaskInput
# # from .constants import DEFAULT_SERVER_PATH
# from .sandbox_models import SandboxConfig, ExecutionResult
# # from .mcp_client import MCPClient
# import subprocess
# import json
# import os
# # from .constants import safe_builtins
# import shlex


# # class TimeoutError(Exception):
# #     pass


# # def timeout_handler(signum, frame):
# #     raise TimeoutError("Execution timed out")


# class Spawner:
#     def __init__(self,
#                  config: SandboxConfig,
#                  server_path: str | None = None,
#                  mcp_command: str | None = None) -> None:
#         self.loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(self.loop)
#         self.config = config
#         self.config.server_path = server_path
#         self.config.mcp_command = mcp_command
#         # self.server_path = server_path
#         # self.mcp_client = MCPClient()
#         self.exec_count: int = 0
#         # self.mcp_command = mcp_command
#         if mcp_command is not None:
#             self.parse_mcp_cmd(mcp_command)
#             # split_cmd = shlex.split(mcp_command)
#             # for word in split_cmd:
#             #     if self.is_mcp_server_file(word):
#             #         try:
#             #             with open(word, 'r') as f:
#             #                 content = f.read()
#             #             filename = word.split('/').pop()
#             #             with open('src/sandbox/' + filename, 'w') as f:
#             #                 f.write(content)
#             #             # self.server_path = filename
#             #             self.config.server_path = filename
#             #             self.config.mcp_command = mcp_command
#             #         except Exception as e:
#             #             print(f"WARNING: {type(e).__name__}: {str(e)}")
#             #             print("Using default MCP server instead")
#             #         finally:
#             #             break

#     def parse_mcp_cmd(self, cmd: str) -> None:
#         split_cmd = shlex.split(cmd)
#         for word in split_cmd:
#             if self.is_mcp_server_file(word):
#                 try:
#                     with open(word, 'r') as f:
#                         content = f.read()
#                     filename = word.split('/').pop()
#                     with open('src/sandbox/' + filename, 'w') as f:
#                         f.write(content)
#                     # self.server_path = filename
#                     self.config.server_path = filename
#                     self.config.mcp_command = cmd
#                 except Exception as e:
#                     print(f"WARNING: {type(e).__name__}: {str(e)}")
#                     print("Using default MCP server instead")
#                 finally:
#                     break

#     def is_mcp_server_file(self, file_path):
#         """
#         Check if a file could be an MCP server based on common extensions.
#         """
#         mcp_extensions = {
#             '.py', '.js', '.ts', '.go', '.rs', '.rb',
#             '.java', '.cs', '.kt', '.swift'
#         }
#         if not os.path.isfile(file_path):
#             return False
#         ext = os.path.splitext(file_path)[1].lower()
#         return ext in mcp_extensions

#     # def configure(self):
#     #     if self.config.server_path is None:
#     #         self.config.server_path = DEFAULT_SERVER_PATH
#     #     self.loop.run_until_complete(
#     #         self.mcp_client.connect_server_stdio_path(self.config.server_path)
#     #     )
#     #     self.restricted_globals = self.loop.run_until_complete(
#     #         self.build_globals()
#     #     )

#     def spawn(self, code: str, task: SWEBenchTaskInput) -> ExecutionResult:
#         """Execute LLM-generated code in restricted environment"""
#         self.exec_count += 1
#         subprocess_inputs = {
#             "config": self.config.model_dump(),
#             "code": code,
#             "eval_script": task.eval_script
#         }
#         docker_cmd = [
#             "docker", "run",
#             "--rm",
#             # "--network=none"
#             "--cap-drop=ALL",
#             "--security-opt=no-new-privileges",
#             "--pids-limit=64",
#             f"--memory={self.config.max_memory_mb}m",
#             "--cpus=1",
#             "-i",
#             "sandbox-image",
#             "uv", "run", "python", "-m", "sandbox_mbpp"
#         ]
#         try:
#             result = subprocess.run(
#                 docker_cmd,
#                 input=json.dumps(subprocess_inputs),
#                 text=True,
#                 capture_output=True,
#                 timeout=self.config.max_execution_time_seconds
#             )
#             import pprint
#             pprint.pprint(result)
#             try:
#                 output_data = json.loads(result.stdout)
#                 if output_data["success"] and "final_answer" in output_data:
#                     # import pprint
#                     # pprint.pprint(output_data)
#                     return ExecutionResult(
#                         success=True,
#                         final_answer=output_data["final_answer"],
#                         output=output_data["output"]
#                     )
#                 elif output_data["success"]:
#                     return ExecutionResult(
#                         success=True,
#                         output=output_data["output"],
#                     )
#                 else:
#                     error = output_data["error"]
#                     return ExecutionResult(
#                         success=False,
#                         output=output_data["output"] or ("No output from "
#                                                          "execution"),
#                         error=f"Spawner: Error during sandbox execution:"
#                               f" {error}"
#                     )
#             except json.JSONDecodeError:
#                 error = f"Spawner: The sandbox output isn't "\
#                         f"parseable: {result.stdout}\n{result.stderr}"
#                 return ExecutionResult(
#                     success=False,
#                     output=result.stdout,
#                     error=error
#                 )
#         except subprocess.TimeoutExpired:
#             return ExecutionResult(
#                 success=False,
#                 output="No output from execution",
#                 error=f"Spawner: Sandbox execution timed out after "
#                       f"{self.config.max_execution_time_seconds} seconds",
#             )
#         except KeyboardInterrupt:
#             return ExecutionResult(
#                 success=False,
#                 output="\nUser interrupted execution",
#                 error="\nUser interrupted execution",
#             )
#         except Exception as e:
#             return ExecutionResult(
#                 success=False,
#                 output="No output from execution",
#                 error=f"Spawner: {type(e).__name__}: {str(e)}",
#             )

