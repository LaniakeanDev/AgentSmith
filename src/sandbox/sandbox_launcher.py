import subprocess
import json
from .config import SandboxConfig


def launch_sandbox(config: SandboxConfig, code: str):
    payload = {
        "config": config.model_dump(),
        "code": code
    }
    docker_cmd = [
        "docker", "run",
        "--rm",
        "--network=none",
        f"--memory={config.max_memory_mb}m",
        "--cpus=1",
        "-i",
        "sandbox-image",
        "uv", "run", "python", "-m", "sandbox"
    ]
    result = subprocess.run(
        docker_cmd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=config.max_execution_time_seconds + 5
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr
    }
