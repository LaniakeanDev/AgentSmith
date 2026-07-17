import asyncio
import signal
import time
from typing import List

from agent_swebench.swebench_models import SWEBenchTaskInput
from agent_mbpp.mbpp_models import MBPPTaskInput
from .sandbox_models import SandboxConfig, ExecutionResult
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
            docker_cmd: List[str]
              ) -> ExecutionResult:
        """Execute LLM-generated code in restricted environment"""
        if hasattr(self.task, 'test_list'):
            task_type = "mbpp"
            subprocess_inputs = {
                "config": self.config.model_dump(),
                "code": code,
                "task_type": task_type,
                "test_list": self.task.test_list
            }
        elif hasattr(self.task, 'eval_script'):
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
        process = None
        try:
            # Use Popen to get process control
            process = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                # Create a new process group - CRITICAL for killing entire tree
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            try:
                # Communicate with timeout
                stdout, stderr = process.communicate(
                    input=json.dumps(subprocess_inputs),
                    timeout=self.config.max_execution_time_seconds
                )
                try:
                    output_data = json.loads(stdout)
                    # print(f"output_data:\n{str(output_data)}")
                    # import sys
                    # sys.exit(0)
                    if output_data["success"] and \
                            "final_answer" in output_data:
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
                            f"parseable: {stdout}\n{stderr}"
                    return ExecutionResult(
                        success=False,
                        output=stdout,
                        error=error
                    )
            except subprocess.TimeoutExpired:
                # KILL THE ENTIRE PROCESS TREE
                if process:
                    print(f"⏰ Timeout! Killing process tree for PID {process.pid}")
                    # Kill the entire process group (including all child processes)
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    # Give it a moment to clean up
                    time.sleep(0.5)
                    # Force kill if still running
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Process already gone
                    process.wait()  # Wait for process to end
                raise Exception(
                    f"Spawner: Sandbox execution timed out after "
                    f"{self.config.max_execution_time_seconds} seconds"
                )
        except KeyboardInterrupt:
            # KILL THE ENTIRE PROCESS TREE on Ctrl+C
            if process:
                print(f"🛑 KeyboardInterrupt! Killing process tree for PID {process.pid}")
                try:
                    # Kill the entire process group
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    time.sleep(0.5)
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Process already gone
                process.wait()
            raise
        except Exception:
            # Clean up on any other exception
            if process:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    time.sleep(0.5)
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            raise

    # def spawn(
    #         self,
    #         code: str,
    #         docker_cmd: List[str]
    #           ) -> ExecutionResult:
    #     """Execute LLM-generated code in restricted environment"""
    #     if hasattr(self.task, 'test_list'):
    #         task_type = "mbpp"
    #         subprocess_inputs = {
    #             "config": self.config.model_dump(),
    #             "code": code,
    #             "task_type": task_type,
    #             "test_list": self.task.test_list
    #         }
    #     elif hasattr(self.task, 'eval_script'):
    #         task_type = "swebench"
    #         subprocess_inputs = {
    #             "config": self.config.model_dump(),
    #             "code": code,
    #             "task_type": task_type,
    #             "eval_script": self.task.eval_script
    #         }
    #     else:
    #         task_type = "sandbox"
    #         subprocess_inputs = {
    #             "config": self.config.model_dump(),
    #             "code": code,
    #             "task_type": task_type,
    #         }
    #     self.exec_count += 1
    #     try:
    #         result = subprocess.run(
    #             docker_cmd,
    #             input=json.dumps(subprocess_inputs),
    #             text=True,
    #             capture_output=True,
    #             timeout=self.config.max_execution_time_seconds
    #         )
    #         try:
    #             output_data = json.loads(result.stdout)
    #             # print(f"output_data:\n{str(output_data)}")
    #             # import sys
    #             # sys.exit(0)
    #             if output_data["success"] and "final_answer" in output_data:
    #                 return ExecutionResult(
    #                     success=True,
    #                     final_answer=output_data["final_answer"],
    #                     output=output_data["output"]
    #                 )
    #             elif output_data["success"]:
    #                 return ExecutionResult(
    #                     success=True,
    #                     output=output_data["output"],
    #                 )
    #             else:
    #                 error = output_data["error"]
    #                 return ExecutionResult(
    #                     success=False,
    #                     output=output_data["output"] or ("No output from "
    #                                                      "execution"),
    #                     error=f"Spawner: Error during sandbox execution:"
    #                           f" {error}"
    #                 )
    #         except json.JSONDecodeError:
    #             error = f"Spawner: The sandbox output isn't "\
    #                     f"parseable: {result.stdout}\n{result.stderr}"
    #             return ExecutionResult(
    #                 success=False,
    #                 output=result.stdout,
    #                 error=error
    #             )
    #     except subprocess.TimeoutExpired:
    #         process.kill()
    #         process.wait()
    #         raise Exception(
    #             f"Spawner: Sandbox execution timed out after "
    #             f"{self.config.max_execution_time_seconds} seconds")
    #     except KeyboardInterrupt:
    #         if result and hasattr(result, 'pid'):
    #             os.killpg(os.getpgid(result.pid), signal.SIGTERM)
    #         raise
    #     except Exception:
    #         if result and hasattr(result, 'pid'):
    #             os.killpg(os.getpgid(result.pid), signal.SIGTERM)
    #         raise




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

