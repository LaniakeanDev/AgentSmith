import subprocess
import json
from .config import SandboxConfig


def launch_sandbox(config: SandboxConfig, code: str):
    inputs = {
        "config": config.model_dump(),
        "code": code
    }
    try:
        result = subprocess.run(
            ["python", "-m", "sandbox"],
            input=json.dumps(inputs),
            text=True,
            capture_output=True,
            timeout=config.max_execution_time_seconds
        )
        try:
            # The container should output JSON
            output_data = json.loads(result.stdout)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "parsed_output": output_data
            }
        except json.JSONDecodeError:
            # If not JSON, return as is
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "parsed_output": None
            }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Sandbox execution timed out after \
                {config.max_execution_time_seconds} seconds",
            "parsed_output": None
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Sandbox execution failed: {str(e)}",
            "parsed_output": None
        }
