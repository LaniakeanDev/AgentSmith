# import asyncio
import json
import sys
from .sandbox_models import SandboxConfig
from .execute import execute
# import subprocess
from pydantic import ValidationError
# from .spawner import Spawner
import traceback
from .constants import DEFAULT_MCP_CMD
from .mcp_client import MCPClient


class Sandbox:
    def __init__(self):
        self.output = ""
        input_data = sys.stdin.read()
        try:
            inputs = json.loads(input_data)
            self.config = SandboxConfig.model_validate(inputs["config"])
            if self.config.mcp_command is None:
                self.config.mcp_command = DEFAULT_MCP_CMD
            self.code = inputs["code"]
            self.mcp_client = MCPClient(self.config.mcp_command)
        except json.JSONDecodeError as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Invalid JSON input to the sandbox container: {e}"
            }))
            sys.exit(1)
        except ValidationError as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Caught ValidationError while parsing "
                         f"configuration: {e}"
            }))
            sys.exit(1)
        except KeyError as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Mandatory key not present: {e}"
            }))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Caught unexpected Exception: {e}"
            }))
            sys.exit(1)
        # if self.config.server_path is None:
        #     self.config.server_path = DEFAULT_SERVER_PATH
        # self.loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(self.loop)
        # if self.config.mcp_command is not None:
        #     self.loop.run_until_complete(
        #         self.mcp_client.connect_server_stdio_cmd(
        #             self.config.mcp_command)
        #     )
        # else:
        #     self.loop.run_until_complete(
        #         self.mcp_client.connect_server_stdio_cmd(
        #             DEFAULT_MCP_CMD)
        #     )
        # self.output += f"\nConnected to MCP server via \
        #     '{self.config.mcp_command}'"

    def execute(self):
        try:
            result = execute(code=self.code, config=self.config)
            if result.output:
                self.output += f"\nExecution ouput: {result.output}"
            if result.success and result.final_answer:
                print(json.dumps({
                    "success": True,
                    "final_answer": result.final_answer,
                    "output": result.output
                }))
            elif result.success:
                print(json.dumps({
                    "success": True,
                    "output": self.output,
                    "error": result.error or "No error from execution"
                }))
            else:
                print(json.dumps({
                    "success": False,
                    "output": self.output,
                    "error": result.error or "No error from execution"
                }))
        except SystemExit as e:
            print(json.dumps({
                "success": False,
                "output": self.output + f"\nScript exited early with code \
                    {e.code}",
                "error": f"Early SystemExit with code {str(e)}"
            }))
        except KeyboardInterrupt:
            print(json.dumps({
                "success": False,
                "output": self.output,
                "error": "User interrupted the execution"
            }))
        except Exception as e:
            tb_str = traceback.format_exc()
            print(json.dumps({
                "success": False,
                "output": self.output,
                "error": f"{type(e).__name__}: {str(e)}\n{tb_str}"
            }))

    # def configure(self):
    #     if self.server_path is None:
    #         self.server_path = DEFAULT_SERVER_PATH
    #     self.loop.run_until_complete(
    #         self.mcp_client.connect_server_stdio_path(self.server_path)
    #     )
    #     self.restricted_globals = self.loop.run_until_complete(
    #         self.build_globals()
    #     )


# def main():
    # input_data = sys.stdin.read()
    # try:
    #     inputs = json.loads(input_data)
    #     config = SandboxConfig.model_validate(inputs["config"])
    #     code = inputs["code"]
    # except json.JSONDecodeError as e:
    #     print(json.dumps({
    #         "success": False,
    #         "output": "",
    #         "error": f"Invalid JSON input to the sandbox container: {e}"
    #     }))
    #     sys.exit(1)
    # except ValidationError as e:
    #     print(f"Caught ValidationError while parsing configuration: {e}")
    #     sys.exit(1)
    # except KeyError as e:
    #     print(f"Mandatory key not present: {e}")
    # except Exception as e:
    #     print(f"Caught unexpected Exception: {e}")
    # sandbox = Spawner(config)
    # result = sandbox.spawn(code)
    # print(result)

    # input_data = sys.stdin.read()
    # try:
    #     inputs = json.loads(input_data)
    #     config = SandboxConfig.model_validate(inputs["config"])
    #     code = inputs["code"]
    # except json.JSONDecodeError as e:
    #     print(json.dumps({
    #         "success": False,
    #         "output": "",
    #         "error": f"Invalid JSON input to the sandbox container: {e}"
    #     }))
    #     sys.exit(1)
    # except ValidationError as e:
    #     print(f"Caught ValidationError while parsing configuration: {e}")
    #     sys.exit(1)
    # except KeyError as e:
    #     print(f"Mandatory key not present: {e}")
    # except Exception as e:
    #     print(f"Caught unexpected Exception: {e}")
    # try:
    #     result = execute(code=code, config=config)
    #     if result.success and result.final_answer:
    #         print(json.dumps({
    #             "success": True,
    #             "final_answer": result.final_answer,
    #             "output": result.output
    #         }))
    #     elif result.success:
    #         print(json.dumps({
    #             "success": True,
    #             "output": result.output or "No output from execution",
    #             "error": result.error or "No output from execution"
    #         }))
    #     else:
    #         print(json.dumps({
    #             "success": False,
    #             "output": result.output or "No output from execution",
    #             "error": result.error or "No output from execution"
    #         }))
    # except SystemExit as e:
    #     print(json.dumps({
    #         "success": False,
    #         "output": f"Script exited early with code {e.code}",
    #         "error": f"Early SystemExit with code {str(e)}"
    #     }))
    # except KeyboardInterrupt:
    #     print(json.dumps({
    #         "success": False,
    #         "output": result.output or "No output from execution",
    #         "error": "User interrupted the execution"
    #     }))
    # except Exception as e:
    #     tb_str = traceback.format_exc()
    #     print(json.dumps({
    #         "success": False,
    #         "output": result.output or "No output from execution",
    #         "error": f"{type(e).__name__}: {str(e)}\n{tb_str}"
    #     }))


if __name__ == '__main__':
    sandbox = Sandbox()
    sandbox.execute()
    # input_data = sys.stdin.read()
    # try:
    #     inputs = json.loads(input_data)
    #     config = SandboxConfig.model_validate(inputs["config"])
    #     code = inputs["code"]
    # except json.JSONDecodeError as e:
    #     print(json.dumps({
    #         "success": False,
    #         "output": "",
    #         "error": f"Invalid JSON input to the sandbox container: {e}"
    #     }))
    #     sys.exit(1)
    # except ValidationError as e:
    #     print(f"Caught ValidationError while parsing configuration: {e}")
    #     sys.exit(1)
    # except KeyError as e:
    #     print(f"Mandatory key not present: {e}")
    # except Exception as e:
    #     print(f"Caught unexpected Exception: {e}")
    # try:
    #     result = execute(code=code, config=config)
    #     if result.success and result.final_answer:
    #         print(json.dumps({
    #             "success": True,
    #             "final_answer": result.final_answer,
    #             "output": result.output
    #         }))
    #     elif result.success:
    #         print(json.dumps({
    #             "success": True,
    #             "output": result.output or "No output from execution",
    #             "error": result.error or "No output from execution"
    #         }))
    #     else:
    #         print(json.dumps({
    #             "success": False,
    #             "output": result.output or "No output from execution",
    #             "error": result.error or "No output from execution"
    #         }))
    # except SystemExit as e:
    #     print(json.dumps({
    #         "success": False,
    #         "output": f"Script exited early with code {e.code}",
    #         "error": f"Early SystemExit with code {str(e)}"
    #     }))
    # except KeyboardInterrupt:
    #     print(json.dumps({
    #         "success": False,
    #         "output": result.output or "No output from execution",
    #         "error": "User interrupted the execution"
    #     }))
    # except Exception as e:
    #     tb_str = traceback.format_exc()
    #     print(json.dumps({
    #         "success": False,
    #         "output": result.output or "No output from execution",
    #         "error": f"{type(e).__name__}: {str(e)}\n{tb_str}"
    #     }))


# if __name__ == '__main__':
#     input_data = sys.stdin.read()
#     try:
#         inputs = json.loads(input_data)
#         config = SandboxConfig.model_validate(inputs["config"])
#         code = inputs["code"]
#     except json.JSONDecodeError as e:
#         print(json.dumps({
#             "success": False,
#             "output": "",
#             "error": f"Invalid JSON input to the sandbox container: {e}"
#         }))
#         sys.exit(1)
#     except ValidationError as e:
#         print(f"Caught ValidationError while parsing configuration: {e}")
#         sys.exit(1)
#     except KeyError as e:
#         print(f"Mandatory key not present: {e}")
#     except Exception as e:
#         print(f"Caught unexpected Exception: {e}")
#     try:
#         result = execute(code=code, config=config)
#         if result.stdout:
#             try:
#                 execution_result = json.loads(result.stdout)
#                 print(json.dumps(execution_result))
#             except json.JSONDecodeError:
#                 print(json.dumps({
#                     "success": False,
#                     "output": "",
#                     "error": f"Invalid output from execution: \
#                               {result.stdout}"
#                 }))
#         else:
#             print(json.dumps({
#                 "success": False,
#                 "output": "",
#                 "error": result.stderr or "No output from execution"
#             }))
#     except SystemExit as e:
#         print(json.dumps({
#             "success": False,
#             "output": "",
#             "error": f"Caught SystemExit Exception: {e}"
#         }))
#     except KeyboardInterrupt as e:
#         print(json.dumps({
#             "success": False,
#             "output": "",
#             "error": f"Caught KeyboardInterrupt Exception: {e}"
#         }))
#     except subprocess.TimeoutExpired:
#         print(json.dumps({
#             "success": False,
#             "output": "",
#             "error": f"Execution timed out after \
#                 {config.max_execution_time_seconds} seconds"
#         }))
#     except Exception as e:
#         print(json.dumps({
#             "success": False,
#             "output": "",
#             "error": str(e)
#         }))
