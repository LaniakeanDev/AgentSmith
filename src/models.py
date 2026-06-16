from pydantic import BaseModel
# from typing import List


class ExecutionResult(BaseModel):
    success: bool
    output: str
    final_answer: str | None = None
    error: str | None = None
