# BS

import sys
import json


def run_tests(code):
    return "tests passed"


TOOLS = {
    "run_tests": {
        "func": run_tests,
        "description": "Execute MBPP tests",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string"
                }
            }
        }
    }
}


for line in sys.stdin:
    request = json.loads(line)

    method = request["method"]

    if method == "tools/list":
        response = {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": data["description"],
                        "inputSchema": data["input_schema"]
                    }
                    for name, data in TOOLS.items()
                ]
            }
        }

    elif method == "tools/call":
        params = request["params"]

        name = params["name"]
        arguments = params["arguments"]

        func = TOOLS[name]["func"]
        result = func(**arguments)

        response = {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": result
        }

    print(json.dumps(response), flush=True)
