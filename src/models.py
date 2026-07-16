from typing import List

from pydantic import BaseModel, Field
# from typing import List


class ExecutionResult(BaseModel):
    success: bool
    output: str
    final_answer: str | None = None
    error: str | None = None


class CallMetrics(BaseModel):
    """Metrics for a single LLM call."""
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    api_url: str
    model_name: str
    llm_output: str
    retries: int
    prompt: str
