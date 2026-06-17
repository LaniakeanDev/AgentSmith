import sys
from .config import SandboxConfig, ExecutionResult
from .constants import safe_builtins
import resource
import io
import json


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


def build_globals(config: SandboxConfig):
    builtins = safe_builtins.copy()
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
    sys.stdout = buffer = io.StringIO()
    try:
        exec(code, restricted_globals)
        output = buffer.getvalue()
        return ExecutionResult(
            success=True,
            output=output
        )
    except RuntimeError as e:
        msg = str(e)

        if msg.startswith("FINAL_ANSWER::"):
            return ExecutionResult(
                success=True,
                output="",
                final_answer=msg.replace("FINAL_ANSWER::", "")
            )

        return ExecutionResult(
            success=False,
            output="",
            error=msg
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            output="",
            error=str(e)
        )
    finally:
        sys.stdout = reg_stdout


def handle_final_answer(answer: str):
    raise RuntimeError(f"FINAL_ANSWER::{answer}")


if __name__ == '__main__':
    inputs = json.loads(sys.stdin.read())
    config = SandboxConfig.model_validate(inputs["config"])
    code = inputs["code"]
    result = execute(code, config)
    print(result.model_dump_json())
