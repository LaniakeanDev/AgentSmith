import re
from typing import List
from agent_mbpp.mbpp_models import (
    CallMetrics, MBPPTaskInput, SolutionOutput, StepMetrics)
import requests
import time
import os
from dotenv import load_dotenv
from sandbox.config import ExecutionResult, SandboxConfig
from sandbox.sandbox import Sandbox
from groq import Groq

load_dotenv()

PROVIDERS = ["groq", "openrouter", "qwen"]


class MBPPAgent:
    def __init__(
            self,
            provider_model: str,
            provider_url: str,
            max_iterations: int) -> None:
        split_provider_model = provider_model.split('/')
        if len(split_provider_model) != 2 or split_provider_model[0] \
                not in PROVIDERS:
            print(f"WARNING: Provider/model invalid: {provider_model}")
            print("Switching to Groq/llama-3.3-70b-versatile instead")
            self.provider, self.model_name = "groq", "llama-3.3-70b-versatile"
        else:
            self.provider = split_provider_model[0].lower()
            self.model_name = split_provider_model[1]
        self.provider_url = provider_url
        self.max_iterations = max_iterations

    def call_qwen(
            self, prompt: str, model="Qwen/Qwen2.5-7B-Instruct"
            ) -> CallMetrics:
        retries = 0
        API_URL = "https://router.huggingface.co/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.environ['QWEN_API_KEY']}",
        }

        def query(payload):
            response = requests.post(API_URL, headers=headers, json=payload)
            return response.json()
        start_time = time.time()
        response = query({
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": model
        })
        elapsed_time_ms = (time.time() - start_time) * 1000
        response_data = response.json()
        call_metrics = CallMetrics(
            input_tokens=response_data['usage']['prompt_tokens'],
            output_tokens=response_data['usage']['completion_tokens'],
            request_time_ms=elapsed_time_ms,
            api_url=API_URL,
            model_name=response_data.get('model', model),
            llm_output=response_data['choices'][0]['message']['content'],
            retries=retries,
            prompt=prompt
            )
        return call_metrics

    def call_groq(
            self, prompt: str, model='llama-3.3-70b-versatile'
            ) -> CallMetrics:
        retries = 0
        client = Groq(
            api_key=os.environ.get("GROQ_API_KEY"),
        )
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model,
        )
        call_metrics = CallMetrics(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            request_time_ms=response.usage.total_time * 1000,
            api_url="https://api.groq.com/openai/v1/chat/completions",
            model_name=response.model,
            llm_output=response.choices[0].message.content,
            retries=retries,
            prompt=prompt
            )
        return call_metrics

    def call_openrouter(
            self, prompt: str, model='openrouter/free'
            ) -> CallMetrics | str:
        """Make a call to OpenRouter API"""
        retries = 0
        OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
        headers = {
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }
        start_time = time.time()
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            json=payload,
            headers=headers,
            timeout=30
        )
        elapsed_time_ms = (time.time() - start_time) * 1000
        result = response.json()
        call_metrics = CallMetrics(
            input_tokens=result['usage']['prompt_tokens'],
            output_tokens=result['usage']['completion_tokens'],
            request_time_ms=elapsed_time_ms,
            api_url='https://openrouter.ai/api/v1/chat/completions',
            model_name=result.get('model', model),
            llm_output=result['choices'][0]['message']['content'],
            retries=retries,
            prompt=prompt
            )
        return call_metrics

# task = {
#     "text": "Write a function to find the n-th rectangular number.",
#     "code": "def find_rect_num(n):\r\n  return n*(n + 1) ",
#     "task_id": 35,
#     "test_setup_code": "",
#     "test_list": ["assert find_rect_num(4) == 20", "assert find_rect_num(5) \
# == 30", "assert find_rect_num(6) == 42"],
#     "challenge_test_list": []
#     }

    def sanitize_code(self, code: str) -> str:
        """Replace problematic Unicode characters with ASCII equivalents."""
        replacements = {
            '‑': '-',  # Non-breaking hyphen
            '—': '-',  # Em dash
            '–': '-',  # En dash
            '‘': "'",  # Left single quote
            '’': "'",  # Right single quote
            '“': '"',  # Left double quote
            '”': '"',  # Right double quote
            '…': '...',  # Ellipsis
        }
        for unicode_char, ascii_char in replacements.items():
            code = code.replace(unicode_char, ascii_char)
        return code

    def call_llm(self, prompt: str) -> CallMetrics:
        if self.provider == 'openrouter':
            print("Sending request to Openrouter ...")
            metrics = self.call_openrouter(prompt)
        elif self.provider == 'qwen':
            print("Sending request to Qwen ...")
            metrics = self.call_qwen(prompt)
        else:
            print("Sending request to Groq ...")
            metrics = self.call_groq(prompt)
        return metrics

    def sandbox_exec(
            self, llm_output: str, test_list: List[str]
            ) -> ExecutionResult:
        pattern = r'```python\n(.*?)```'
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            code = match.group(1)
            code = self.sanitize_code(code)
        else:
            return ExecutionResult(
                success=False,
                output="No output",
                error="No valid code block was found in the model's response"
            ), ""
        split_code = code.split("\n")
        code = ""
        for line in split_code:
            if "assert" not in line and "test" not in line.lower() \
                    and "if __name__ ==" not in line:
                code += line + '\n'
        test_code = "\nsuccess = True"
        for test in test_list:
            func_call = test[6:].split('==')[0]
            test_code += f"""\ntry:\n    {test}\n    print(\"\"\"Passed test: \
'{test}'\"\"\")\nexcept AssertionError:\n    print(f\"\"\"Failed test: \
'{test}' got {{{func_call}}} instead\"\"\")\n    success = False\n"""
        test_code += f"""\nif success:\n    final_answer(\'\'\'{code}\'\'\')"""
        code += '\n\n' + test_code
        # print("\n\nafter generating the code:")
        # print(code)
        config = SandboxConfig()
        server_path = 'src/fastmcp_server.py'
        sandbox = Sandbox(config, server_path)
        sandbox.configure()
        result = sandbox.execute(code)
        return result, code

    def get_new_prompt(
            self, prompt: str, code: str, exec_output: str,
            iteration_count: int, message: str):
        new_prompt = f"{prompt}\n\nIteration {iteration_count}:\ncode: {code}"
        new_prompt += '\n' + message + '\n'
        new_prompt += f"execution output: {exec_output}\n"
        new_prompt += "Think, then make the next iteration"
        return new_prompt

    def solve_task(
            self,
            task: MBPPTaskInput) -> SolutionOutput:
        task_start = time.time()
        prompt = task.task_definition + "\nTest list: " + str(task.test_list)
        prompt += " reply with nothing but the code starting by '```python':"
        call_metrics = self.call_llm(prompt)
        llm_output = call_metrics.llm_output.strip()
        result, code = self.sandbox_exec(
            llm_output=llm_output, test_list=task.test_list)
        iteration_count = 1
        step_metrics_list: List[StepMetrics] = []
        step_metrics = self.get_step_metrics(
            code=code,
            result=result,
            call_metrics=call_metrics,
            iteration_count=iteration_count
        )
        step_metrics_list.append(step_metrics)
        # print(result)
        while result.final_answer is None and \
                iteration_count <= self.max_iterations:
            exec_output = result.output
            if result.success:
                message = "Execution completed but some tests failed"
            else:
                message = f"Execution could not complete: {result.error}"
            prompt = self.get_new_prompt(
                prompt=prompt,
                code=code,
                exec_output=exec_output,
                iteration_count=iteration_count,
                message=message
                )
            call_metrics = self.call_llm(prompt)
            llm_output = call_metrics.llm_output.strip()
            result, code = self.sandbox_exec(
                llm_output=llm_output, test_list=task.test_list)
            iteration_count += 1
            step_metrics = self.get_step_metrics(
                code=code,
                result=result,
                call_metrics=call_metrics,
                iteration_count=iteration_count
            )
            step_metrics_list.append(step_metrics)
        task_duration = time.time() - task_start
        if not result.final_answer:
            print("Could not solve this problem")
            return SolutionOutput(
                task_id=str(task.task_id),
                benchmark="mbpp",
                success=False,
                solution="Solution not found",
                system_prompt=prompt,
                iterations=iteration_count,
                total_requests=sum(
                    met.retries + 1 for met in step_metrics_list),
                total_input_tokens=sum(
                    met.input_tokens for met in step_metrics_list),
                total_output_tokens=sum(
                    met.output_tokens for met in step_metrics_list),
                total_time_seconds=task_duration,
                steps=step_metrics_list,
                error=result.error
            )
        else:
            print("\nProblem solved! The solution is:\n")
            print(result.final_answer)
            return SolutionOutput(
                task_id=str(task.task_id),
                benchmark="mbpp",
                success=True,
                solution=result.final_answer,
                system_prompt=prompt,
                iterations=iteration_count,
                total_requests=sum(
                    met.retries + 1 for met in step_metrics_list),
                total_input_tokens=sum(
                    met.input_tokens for met in step_metrics_list),
                total_output_tokens=sum(
                    met.output_tokens for met in step_metrics_list),
                total_time_seconds=task_duration,
                steps=step_metrics_list,
            )

    # if result.final_answer:
    #     print("Problem solved! The solution is:")
    #     print(result.final_answer)
    # elif result.success:
    #     print("Execution was able to complete but some tests failed")
    #     print(result.output)
    # else:
    #     print("\nExecution could not complete:")
    #     print(result.error)

    def get_step_metrics(
            self,
            result: ExecutionResult,
            code: str,
            call_metrics: CallMetrics,
            iteration_count: int
            ) -> StepMetrics:
        if result.final_answer:
            sandbox_output = result.final_answer
        elif result.success:
            sandbox_output = result.output + '\n' + result.error
        else:
            sandbox_output = result.error
        return StepMetrics(
            step=iteration_count,
            input_tokens=call_metrics.input_tokens,
            output_tokens=call_metrics.output_tokens,
            request_time_ms=call_metrics.request_time_ms,
            api_url=call_metrics.api_url,
            model_name=call_metrics.model_name,
            llm_output=call_metrics.llm_output,
            retries=call_metrics.retries,
            sandbox_input=code,
            sandbox_output=sandbox_output,
            prompt=call_metrics.prompt
        )


# if __name__ == '__main__':
#     solve_task(task, "Groq")
