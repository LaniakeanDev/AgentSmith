import json
import sys
from .config import SandboxConfig
import subprocess


# def restricted_import_factory(config: SandboxConfig):
#     """Create import filter bound to config"""
#     def restricted_import(name, *args, **kwargs):
#         if name in config.authorized_imports:
#             return __import__(name, *args, **kwargs)
#         authorized_imports_list = ""
#         for item in config.authorized_imports:
#             authorized_imports_list += f"{item}, "
#             if item.endswith('.*'):
#                 prefix = item[:-2]
#                 if name == prefix or name.startswith(prefix + '.'):
#                     return __import__(name, *args, **kwargs)
#         authorized_imports_list = authorized_imports_list[:-2]
#         message = f"Import of '{name}' is not allowed.\n"
#         message += f"Authorized imports: {authorized_imports_list}"
#         raise ImportError(message)

#     return restricted_import


# def build_globals(config: SandboxConfig):
#     builtins = safe_builtins.copy()
#     builtins['__import__'] = restricted_import_factory(config)
#     return {
#         '__builtins__': builtins,
#         'final_answer': handle_final_answer
#     }


# def set_mem_limit(config: SandboxConfig):
#     max_mem_bytes = config.max_memory_mb * 1024 * 1024
#     resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))


# def execute(code: str, config: SandboxConfig) -> ExecutionResult:
#     set_mem_limit(config)
#     restricted_globals = build_globals(config)
#     reg_stdout = sys.stdout
#     sys.stdout = buffer = io.StringIO()
#     try:
#         exec(code, restricted_globals)
#         # output = buffer.getvalue() if hasattr(buffer, "getvalue") else ""
#         output = buffer.getvalue()
#         return ExecutionResult(
#             success=True,
#             output=output
#         )
#     except RuntimeError as e:
#         msg = str(e)

#         if msg.startswith("FINAL_ANSWER::"):
#             return ExecutionResult(
#                 success=True,
#                 output="",
#                 final_answer=msg.replace("FINAL_ANSWER::", "")
#             )

#         return ExecutionResult(
#             success=False,
#             output="",
#             error=msg
#         )
#     except Exception as e:
#         return ExecutionResult(
#             success=False,
#             output="",
#             error=str(e)
#         )
#     finally:
#         sys.stdout = reg_stdout


# def handle_final_answer(answer: str):
#     raise RuntimeError(f"FINAL_ANSWER::{answer}")


if __name__ == '__main__':
    input_data = sys.stdin.read()
    try:
        inputs = json.loads(input_data)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": f"Invalid JSON input to the sandbox container: {e}"
        }))
        sys.exit(1)
    config = SandboxConfig.model_validate(inputs["config"])
    try:
        result = subprocess.run(
            ["python", "-m", "sandbox.execute"],
            input=input_data,
            text=True,
            capture_output=True,
            timeout=config.max_execution_time_seconds
        )
        if result.stdout:
            try:
                execution_result = json.loads(result.stdout)
                print(json.dumps(execution_result))
            except json.JSONDecodeError:
                print(json.dumps({
                    "success": False,
                    "output": "",
                    "error": f"Invalid output from execution: {result.stdout}"
                }))
        else:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": result.stderr or "No output from execution"
            }))
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": f"Execution timed out after \
                {config.max_execution_time_seconds} seconds"
        }))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": str(e)
        }))
