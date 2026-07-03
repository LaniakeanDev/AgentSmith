# import re
# import sys
# from typing import List
# from agent_mbpp.mbpp_models import (
#     CallMetrics, MBPPTaskInput, SolutionOutput, StepMetrics)
import requests
import time
import os
from dotenv import load_dotenv
from models import CallMetrics
# from sandbox.sandbox_models import ExecutionResult, SandboxConfig
# from sandbox.spawner import Spawner
# from groq import Groq
from groq import Groq
from cerebras.cloud.sdk import Cerebras
from google import genai


load_dotenv()

PROVIDERS_KEY_CONST_MAP = {
    "groq": {
        "key_name": 'GROQ_API_KEY',
        "url": 'https://api.groq.com/openai/v1/chat/completions',
        "model": 'llama-3.3-70b-versatile'
        },
    "qwen": {
        "key_name": 'QWEN_API_KEY',
        "url": 'https://router.huggingface.co/v1/chat/completions',
        "model": 'Qwen/Qwen3-32B'
        },
    "openrouter": {
        "key_name": 'OPENROUTER_API_KEY',
        "url": 'https://openrouter.ai/api/v1/chat/completions',
        "model": 'openrouter/free'
        },
    "cerebras": {
        "key_name": 'CEREBRAS_API_KEY',
        "url": 'cerebras_url',
        "model": 'cerebras/gemma-4-31b'
        },
    "gemini": {
        "key_name": 'GEMINI_API_KEY',
        "url": 'gemini_url',
        "model": 'gemini-3.5-flash'
        },
}
# Cerebras


class AbstractAgent:
    def __init__(
            self,
            provider_model: str,
            provider_url: str,
            max_iterations: int) -> None:
        self.provider_url = provider_url
        split_provider_model = provider_model.split('/')
        if len(split_provider_model) != 2 or split_provider_model[0] \
                not in PROVIDERS_KEY_CONST_MAP:
            print(f"WARNING: Provider/model invalid: {provider_model}")
            self.provider = "gemini"
            print(f"Switching to {self.provider} instead")
            self.model_name = PROVIDERS_KEY_CONST_MAP[self.provider]["model"]
            self.provider_url = PROVIDERS_KEY_CONST_MAP[self.provider]["url"]
        else:
            self.provider = split_provider_model[0].lower()
            self.model_name = split_provider_model[1]
        self.key_name = PROVIDERS_KEY_CONST_MAP[self.provider]["key_name"]
        self.provider_model = PROVIDERS_KEY_CONST_MAP[self.provider]["model"]
        self.max_iterations = max_iterations
        self.max_retries = 3

    def rotate_providers(self):
        return False

    def call_gemini(self, prompt: str, model='gemini-3.5-flash'):
        retries = 0
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        start_time = time.time()
        response = client.interactions.create(
            model=model,
            input=prompt
        )
        elapsed_time_ms = (time.time() - start_time) * 1000
        call_metrics = CallMetrics(
            input_tokens=response.usage.total_input_tokens,
            output_tokens=response.usage.total_output_tokens,
            request_time_ms=elapsed_time_ms,
            api_url="gemini_url",
            model_name=response.model,
            llm_output=response.output_text,
            retries=retries,
            prompt=prompt
            )
        return call_metrics

    def call_groq(
        self, prompt: str, model='llama-3.3-70b-versatile'
    ) -> CallMetrics:
        number_of_keys = 2
        retries = 0
        max_retries_per_key = 3
        for key_num in range(1, number_of_keys + 1):
            for attempt in range(max_retries_per_key):
                try:
                    client = Groq(
                        api_key=os.environ.get(f"GROQ_API_KEY_{key_num}")
                    )
                    response = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model,
                    )
                    api_url = "https://api.groq.com/openai/v1/chat/completions"
                    return CallMetrics(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        request_time_ms=response.usage.total_time * 1000,
                        api_url=api_url,
                        model_name=response.model,
                        llm_output=response.choices[0].message.content,
                        retries=retries,
                        prompt=prompt
                    )
                except Exception as e:
                    retries += 1
                    error_msg = str(e).lower()
                    # If rate limit and we have retries left on this key, retry
                    if not ("429" in error_msg or "rate limit" in error_msg) \
                            and attempt < max_retries_per_key - 1:
                        time.sleep(1)  # Brief wait before retry
                        continue
                    # If rate limit and out of retries, try next key
                    elif ("429" in error_msg or "rate limit" in error_msg) or \
                            attempt == max_retries_per_key - 1:
                        break
                    else:
                        raise e
        # If we get here, all keys are rate limited
        raise Exception(f"All {number_of_keys} API keys rate limited after \
                        {retries} total attempts")

    def call_cerebras(self, prompt: str):
        # !pip install cerebras-cloud-sdk
        retries = 0
        client = Cerebras(
            api_key=os.environ.get("CEREBRAS_API_KEY")
        )
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }],
            model="gemma-4-31b",
            max_completion_tokens=1024,
            temperature=0.2,
            top_p=1,
            stream=False,
            reasoning_effort="medium"
        )
        call_metrics = CallMetrics(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            request_time_ms=response.time_info.total_time * 1000,
            api_url="cerebras_url",
            model_name=response.model,
            llm_output=response.choices[0].message.content,
            retries=retries,
            prompt=prompt
            )
        return call_metrics

    def call_llm(self, prompt: str, timeout: int = 30) -> CallMetrics:
        if self.provider == "groq":
            return self.call_groq(prompt)
        elif self.provider == "cerebras":
            return self.call_cerebras(prompt)
        elif self.provider == "gemini":
            return self.call_gemini(prompt)
        retries_count = 0
        headers = {
            "Authorization": f"Bearer {os.environ[self.key_name]}",
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.provider_model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }
        # import pprint
        # import sys
        # pprint.pprint(payload)
        # sys.exit(0)
        answered = False
        start_time = time.time()
        for i in range(self.max_retries):
            try:
                response = requests.post(
                    self.provider_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()
                answered = True
                break
            except requests.exceptions.RequestException as e:
                retries_count += 1
                print(f"Attempt {i+1}/{self.max_retries} failed: {e}")
                time.sleep(1)
        if answered:
            elapsed_time_ms = (time.time() - start_time) * 1000
            result = response.json()
            # Check if 'usage' and 'choices' exist in response
            call_metrics = CallMetrics(
                input_tokens=result['usage']['prompt_tokens'],
                output_tokens=result['usage']['completion_tokens'],
                request_time_ms=elapsed_time_ms,
                api_url=self.provider_url,
                model_name=self.provider_model,
                llm_output=result['choices'][0]['message']['content'],
                retries=retries_count,
                prompt=prompt
                )
            return call_metrics
        else:
            if self.rotate_provider():
                return self.call_llm(prompt, timeout)
            else:
                raise RuntimeError("All LLM providers failed")

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

    def get_new_prompt(
            self, prompt: str, code: str, exec_output: str,
            iteration_count: int, message: str):
        new_prompt = f"{prompt}\n\nIteration {iteration_count}:\ncode: {code}"
        new_prompt += '\n' + message + '\n'
        new_prompt += f"execution output: {exec_output}\n"
        new_prompt += "Think, then make the next iteration"
        return new_prompt


if __name__ == '__main__':
    agent = AbstractAgent("", "", 5)
    agent.call_gemini("")
