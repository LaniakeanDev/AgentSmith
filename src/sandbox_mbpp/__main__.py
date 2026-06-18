import json
import sys
from .config import SandboxConfig
from .execute import execute
import subprocess
from pydantic import ValidationError
from .sandbox import Sandbox


def main():
    input_data = sys.stdin.read()
    try:
        inputs = json.loads(input_data)
        config = SandboxConfig.model_validate(inputs["config"])
        code = inputs["code"]
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": f"Invalid JSON input to the sandbox container: {e}"
        }))
        sys.exit(1)
    except ValidationError as e:
        print(f"Caught ValidationError while parsing configuration: {e}")
        sys.exit(1)
    except KeyError as e:
        print(f"Mandatory key not present: {e}")
    except Exception as e:
        print(f"Caught unexpected Exception: {e}")
    sandbox = Sandbox(config)
    result = sandbox.execute(code)
    print(result)


if __name__ == '__main__':
    input_data = sys.stdin.read()
    try:
        inputs = json.loads(input_data)
        config = SandboxConfig.model_validate(inputs["config"])
        code = inputs["code"]
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "output": "",
            "error": f"Invalid JSON input to the sandbox container: {e}"
        }))
        sys.exit(1)
    except ValidationError as e:
        print(f"Caught ValidationError while parsing configuration: {e}")
        sys.exit(1)
    except KeyError as e:
        print(f"Mandatory key not present: {e}")
    except Exception as e:
        print(f"Caught unexpected Exception: {e}")
    try:
        result = execute(code=code, config=config)
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
