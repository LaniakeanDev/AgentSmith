import sys
from .sandbox_models import SandboxConfig, ExecutionResult, FinalAnswer
import resource
import io
import traceback


def set_mem_limit(config: SandboxConfig):
    max_mem_bytes = config.max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))


def execute(
        code: str,
        config: SandboxConfig,
        restricted_globals: dict) -> ExecutionResult:
    set_mem_limit(config)
    reg_stdout = sys.stdout
    # capture untrusted code's output
    sys.stdout = buffer = io.StringIO()
    output = "No output generatedy"
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
        output = buffer.getvalue()
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


# def execute_old(code: str, config: SandboxConfig) -> ExecutionResult:
#     set_mem_limit(config)
#     restricted_globals = build_globals(config)
#     reg_stdout = sys.stdout
#     sys.stdout = buffer = io.StringIO()
#     try:
#         exec(code, restricted_globals)
#         output = buffer.getvalue()
#         return ExecutionResult(
#             success=True,
#             output=output
#         )
#     except SystemExit:
#         raise
#     except KeyboardInterrupt:
#         raise
#     except PermissionError as e:
#         return ExecutionResult(
#             success=False,
#             output="",
#             error=f"Sandbox caught PermissionError: \
#                 {type(e).__name__}: {str(e)}"
#         )
#     except MemoryError as e:
#         return ExecutionResult(
#             success=False,
#             output="",
#             error=f"Memory limit exceeded ({config.max_memory_mb}MB): {str(e)}"
#         )
#     except FinalAnswer as e:
#         f_ans = e.answer
#         return ExecutionResult(
#             success=True,
#             output="",
#             final_answer=f_ans
#         )
#     except Exception as e:
#         return ExecutionResult(
#             success=False,
#             output="",
#             error=f"{type(e).__name__}: {str(e)}"
#         )
#     finally:
#         sys.stdout = reg_stdout


# def handle_final_answer(answer: str):
#     raise FinalAnswer(answer)


# if __name__ == '__main__':
#     inputs = json.loads(sys.stdin.read())
#     config = SandboxConfig.model_validate(inputs["config"])
#     code = inputs["code"]
#     result = execute(code, config)
#     print(result.model_dump_json())
