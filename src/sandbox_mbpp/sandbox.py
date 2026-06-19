import asyncio
import os
from .config import SandboxConfig, ExecutionResult
from .mcp_client import MCPClient
from .constants import safe_builtins
import resource
import io
import sys
import signal


class TimeoutError(Exception):
    pass


class FinalAnswer(BaseException):
    def __init__(self, answer):
        super().__init__()
        self.answer = answer


def timeout_handler(signum, frame):
    raise TimeoutError("Execution timed out")


class Sandbox:
    def __init__(self, config: SandboxConfig, server_path: str) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.config = config
        self.server_path = server_path
        self.mcp_client = MCPClient()
        self.exec_count: int = 0

    def configure(self):
        self.loop.run_until_complete(
            self.mcp_client.connect_to_server(self.server_path)
        )
        self.restricted_globals = self.loop.run_until_complete(
            self.build_globals()
        )
        print("Sandbox configuration successful")

    def execute(self, code: str) -> ExecutionResult:
        """Execute LLM-generated code in restricted environment"""
        self.exec_count += 1
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.config.max_execution_time_seconds)
        self.set_mem_limit()
        reg_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            exec(code, self.restricted_globals)
            output = buffer.getvalue()
            return ExecutionResult(
                success=True,
                output=output
            )
        except TimeoutError as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Sandbox caught TimeoutError: {str(e)}"
            )
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except PermissionError as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Sandbox caught PermissionError: {str(e)}"
            )
        except MemoryError as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Memory limit exceeded (\
                    {self.config.max_memory_mb}MB): {str(e)}"
            )
        except FinalAnswer as e:
            f_ans = e.answer
            return ExecutionResult(
                success=True,
                output="",
                final_answer=f_ans
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {str(e)}"
            )
        finally:
            sys.stdout = reg_stdout

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
            **tool_wrappers
        }
        return restricted_globals

    def set_mem_limit(self):
        max_mem_bytes = self.config.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))

    def handle_final_answer(self, answer: str):
        raise FinalAnswer(answer)


# if __name__ == '__main__':
#     inputs = json.loads(sys.stdin.read())
#     config = SandboxConfig.model_validate(inputs["config"])
#     code = inputs["code"]
#     sandbox = Sandbox(config=config)
#     result = sandbox.execute(code)
#     print(result.model_dump_json())
