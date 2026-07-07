# import asyncio
import asyncio
import json
import os
import sys
from .sandbox_models import SandboxConfig, FinalAnswer
from .execute import execute
from pydantic import ValidationError
from .constants import safe_builtins
import traceback
from .constants import DEFAULT_MCP_CMD_MBPP, DEFAULT_MCP_CMD_SWEB
from .mcp_client import MCPClient


class Sandbox:
    def __init__(self):
        self.output = ""
        input_data = sys.stdin.read()
        try:
            inputs = json.loads(input_data)
            self.config = SandboxConfig.model_validate(inputs["config"])
            task_type = inputs["task_type"]
            if self.config.mcp_command is None:
                if task_type == 'mbpp':
                    self.config.mcp_command = DEFAULT_MCP_CMD_MBPP
                elif task_type == 'mbpp':
                    self.config.mcp_command = DEFAULT_MCP_CMD_SWEB
                else:
                    self.config.mcp_command = "uv run python sandbox/fastmcp_server.py"
            self.code = inputs["code"]
            if "eval_script" in inputs:
                self.eval_script = inputs["eval_script"]
            else:
                self.eval_script = None
            self.mcp_client = MCPClient(
                self.config.mcp_command, self.eval_script)
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.restricted_globals = self.loop.run_until_complete(
                self.mcp_client.connect_server()
            )
            self.restricted_globals = self.loop.run_until_complete(
                self.build_globals()
            )
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

    def execute(self):
        try:
            result = execute(
                code=self.code,
                config=self.config,
                restricted_globals=self.restricted_globals)
            if result.output:
                self.output += f"\nExecution ouput:\n{result.output}"
            if result.success and result.final_answer:
                print(json.dumps({
                    "success": True,
                    "final_answer": result.final_answer,
                    "output": f"{self.mcp_client.messages}\n{self.output}"
                }))
            elif result.success:
                print(json.dumps({
                    "success": True,
                    "output": f"{self.mcp_client.messages}\n{self.output}",
                    "error": result.error or "No error from execution"
                }))
            else:
                print(json.dumps({
                    "success": False,
                    "output": f"{self.mcp_client.messages}\n{self.output}",
                    "error": result.error or "No error from execution"
                }))
        except SystemExit as e:
            output = f"{self.mcp_client.messages}\n{self.output}"
            output += f"\nScript exited early with code {e.code}"
            print(json.dumps({
                "success": False,
                "output": output,
                "error": f"Early SystemExit with code {str(e)}"
            }))
        except KeyboardInterrupt:
            print(json.dumps({
                "success": False,
                "output": f"{self.mcp_client.messages}\n{self.output}",
                "error": "User interrupted the execution"
            }))
        except Exception as e:
            tb_str = traceback.format_exc()
            print(json.dumps({
                "success": False,
                "output": f"{self.mcp_client.messages}\n{self.output}",
                "error": f"{type(e).__name__}: {str(e)}\n{tb_str}"
            }))

    def restricted_import_factory(self):
        """Create import filter bound to config"""
        def restricted_import(name, *args, **kwargs):
            if name in self.config.authorized_imports:
                return __import__(name, *args, **kwargs)
            authorized_imports_str = ""
            for item in self.config.authorized_imports:
                authorized_imports_str += f"{item}, "
                if item.endswith('.*'):
                    prefix = item[:-2]
                    if name == prefix or name.startswith(prefix + '.'):
                        return __import__(name, *args, **kwargs)
            authorized_imports_str = authorized_imports_str[:-2]
            message = f"Import of '{name}' is not allowed.\n"
            message += f"Authorized imports: {authorized_imports_str}"
            raise ImportError(message)
        return restricted_import

    def restricted_open_factory(self):
        allowed = [
            os.path.realpath(p)
            for p in self.config.allowed_directories
        ]

        def restricted_open(path, *args, **kwargs):
            real = os.path.realpath(path)
            for root in allowed:
                if (real == root
                        or real.startswith(root + os.sep)):
                    return open(real, *args, **kwargs)
            raise PermissionError(f"Unauthorized path: {path}")

        return restricted_open

    async def build_globals(self):
        builtins = safe_builtins.copy()
        builtins["open"] = self.restricted_open_factory()
        builtins['__import__'] = self.restricted_import_factory()
        tool_wrappers = await self.mcp_client.build_tool_wrappers()
        restricted_globals = {
            '__builtins__': builtins,
            'final_answer': self.handle_final_answer,
            'eval_script': self.eval_script,
            **tool_wrappers
        }
        return restricted_globals

    def handle_final_answer(self, answer: str):
        raise FinalAnswer(answer)


if __name__ == '__main__':
    sandbox = Sandbox()
    sandbox.execute()
