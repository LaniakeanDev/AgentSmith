import sys
from .config import SandboxConfig, ExecutionResult
from .constants import safe_builtins
import resource
import io
import json
import os
import traceback


class FinalAnswer(BaseException):
    def __init__(self, answer):
        super().__init__()
        self.answer = answer


def restricted_import_factory(config: SandboxConfig):
    """Create import filter bound to config"""
    def restricted_import(name, *args, **kwargs):
        if name in config.authorized_imports:
            return __import__(name, *args, **kwargs)
        authorized_imports_str = ""
        for item in config.authorized_imports:
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


def restricted_open_factory(config):
    allowed = [
        os.path.realpath(p)
        for p in config.allowed_directories
    ]

    def restricted_open(path, *args, **kwargs):
        real = os.path.realpath(path)
        for root in allowed:
            if (real == root
                    or real.startswith(root + os.sep)):
                return open(real, *args, **kwargs)
        raise PermissionError(f"Unauthorized path: {path}")

    return restricted_open


def build_globals(config: SandboxConfig):
    builtins = safe_builtins.copy()
    builtins["open"] = restricted_open_factory(config)
    builtins['__import__'] = restricted_import_factory(config)
    return {
        '__builtins__': builtins,
        'final_answer': handle_final_answer
    }


def set_mem_limit(config: SandboxConfig):
    max_mem_bytes = config.max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))


def execute(code: str, config: SandboxConfig) -> ExecutionResult:
    set_mem_limit(config)
    restricted_globals = build_globals(config)
    reg_stdout = sys.stdout
    # capture untrusted code's output
    sys.stdout = buffer = io.StringIO()
    output = "No output generated"
    try:
        exec(code, restricted_globals)
        output = buffer.getvalue()
        return ExecutionResult(
            success=True,
            output=output
        )
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except FinalAnswer as e:
        f_ans = e.answer
        return ExecutionResult(
            success=True,
            output=output,
            final_answer=f_ans
        )
    except Exception as e:
        tb_str = traceback.format_exc()
        return ExecutionResult(
            success=False,
            output=output,
            error=f"{type(e).__name__}: {str(e)}\n{tb_str}"
        )
    finally:
        sys.stdout = reg_stdout


def execute_old(code: str, config: SandboxConfig) -> ExecutionResult:
    set_mem_limit(config)
    restricted_globals = build_globals(config)
    reg_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        exec(code, restricted_globals)
        output = buffer.getvalue()
        return ExecutionResult(
            success=True,
            output=output
        )
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except PermissionError as e:
        return ExecutionResult(
            success=False,
            output="",
            error=f"Sandbox caught PermissionError: \
                {type(e).__name__}: {str(e)}"
        )
    except MemoryError as e:
        return ExecutionResult(
            success=False,
            output="",
            error=f"Memory limit exceeded ({config.max_memory_mb}MB): {str(e)}"
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


def handle_final_answer(answer: str):
    raise FinalAnswer(answer)


if __name__ == '__main__':
    inputs = json.loads(sys.stdin.read())
    config = SandboxConfig.model_validate(inputs["config"])
    code = inputs["code"]
    result = execute(code, config)
    print(result.model_dump_json())
