import subprocess
import json
from .config import SandboxConfig


def launch_sandbox(config: SandboxConfig, code: str):
    inputs = {
        "config": config.model_dump(),
        "code": code
    }
    docker_cmd = [
        "docker", "run",
        "--rm",
        # "--network=none", removed because needs HTTP access
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        f"--memory={config.max_memory_mb}m",
        "--cpus=1",
        "-i",
        "sandbox-image",
        "uv", "run", "python", "-m", "sandbox"
    ]
    try:
        result = subprocess.run(
            docker_cmd,
            input=json.dumps(inputs),
            text=True,
            capture_output=True,
            timeout=config.max_execution_time_seconds + 5
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
            "stderr": f"Sandbox container execution timed out after \
                {config.max_execution_time_seconds + 5} seconds",
            "parsed_output": None
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Sandbox execution failed: {str(e)}",
            "parsed_output": None
        }
