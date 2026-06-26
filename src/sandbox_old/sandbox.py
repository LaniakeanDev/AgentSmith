# # import sys
# import json
# # from typing import List
# from pydantic import BaseModel
# from ..models import SandboxConfig, ExecutionResult
# import subprocess


# class Sandbox(BaseModel):
#     config: SandboxConfig
#     mcp_client: str | None = None
#     exec_count: int = 0

#     def execute(self, code: str) -> ExecutionResult:
#         """Execute LLM-generated code in restricted environment"""
#         self.exec_count += 1
#         result = subprocess.run(
#             ["python3.13", "sandbox_worker.py"],
#             input=json.dumps({
#                 "config": self.config.model_dump(),
#                 "code": code
#             }),
#             text=True,
#             capture_output=True,
#             timeout=self.config.max_execution_time_seconds
#         )
#         if result.success:
#             pass  # to be implemented later


# # if __name__ == '__main__':
# #     inputs = json.loads(sys.stdin.read())
# #     config = SandboxConfig.model_validate(inputs["config"])
# #     code = inputs["code"]
# #     sandbox = Sandbox(config=config)
# #     result = sandbox.execute(code)
# #     print(result.model_dump_json())
