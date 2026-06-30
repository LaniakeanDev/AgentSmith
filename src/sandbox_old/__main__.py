import json
import sys
from .config import SandboxConfig
import subprocess


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
                "error": result.stderr or "No error from execution"
            }))
    except SystemExit as e:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": f"Caught SystemExit Exception: {e}"
        }))
    except KeyboardInterrupt as e:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": f"Caught KeyboardInterrupt Exception: {e}"
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
