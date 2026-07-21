import os
from typing import Dict
from mcp.server.fastmcp import FastMCP
import ast


mcp = FastMCP("AgentSmith", json_response=True)


@mcp.tool()
def run_tests() -> Dict:
    """Execute the tests from the test list"""
    # print("run_tests() executes")
    test_list_str = os.environ.get('test_list')
    code_str = os.environ.get('code')
    code_str = code_str.replace("run_tests()", "")
    if test_list_str is None:
        return {
            "success": False,
            "error": "test_list environment variable not set"
            }
    if code_str is None:
        return {
            "success": False,
            "error": "code environment variable not set"
            }
    test_list = ast.literal_eval(test_list_str)
    namespace = {}
    exec(code_str, namespace)
    results = []
    passed = 0
    failed = 0
    try:
        for test in test_list:
            test_result = {
                "test": test,
                "passed": False,
                "result": None,
                "error": None
            }
            try:
                exec(test, namespace)
                result = True
                test_result["result"] = result
                test_result["passed"] = True
                passed += 1
            except Exception as e:
                test_result["error"] = f"{type(e).__name__}: {str(e)}\ncode_str:\n{code_str}"
                test_result["passed"] = False
                failed += 1
            results.append(test_result)
        return {
            "success": True,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "results": results
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}\ncode_str:\n{code_str}",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "results": []
        }


# Run with streamable HTTP transport
if __name__ == "__main__":
    # mcp.run(transport="streamable-http")
    mcp.run(transport="stdio")
