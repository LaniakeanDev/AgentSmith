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
