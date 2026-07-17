# import re
# import sys
# from typing import List
# from agent_mbpp.mbpp_models import (
#     CallMetrics, MBPPTaskInput, SolutionOutput, StepMetrics)
# import requests
# import time
# import os
import sys

from dotenv import load_dotenv
# from models import CallMetrics
# from sandbox.sandbox_models import ExecutionResult, SandboxConfig
# from sandbox.spawner import Spawner
# from groq import Groq
# from groq import Groq
# from cerebras.cloud.sdk import Cerebras
# from google import genai
from sandbox.mcp_client import MCPClient
import re
from constants import DEFAULT_PROVIDER_MODEL, PROVIDERS_KEY_CONST_MAP
from sandbox.sandbox_models import SandboxConfig

load_dotenv()


class AbstractAgent:
    def __init__(
            self,
            task_type: str,
            provider_model: str,
            provider_url: str,
            max_iterations: int,
            config: SandboxConfig,
            ) -> None:
        self.config = config
        self.task_type = task_type
        self.provider_url = provider_url
        split_provider_model = provider_model.split('/')
        if len(split_provider_model) != 2 or split_provider_model[0] \
                not in PROVIDERS_KEY_CONST_MAP:
            print(f"WARNING: Provider/model invalid: {provider_model}")
            self.provider = DEFAULT_PROVIDER_MODEL.split('/')[0]
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

    async def get_sandbox_manual(self):
        await self.get_mcp_manual()
        authorized_imports = self.config.authorized_imports
        for item in authorized_imports:
            self.authorized_imports += f"{item}, "
        self.authorized_imports = self.authorized_imports[:-2]

    async def get_mcp_manual(self):
        client = MCPClient(
            task_type=self.task_type,
            config=self.config
        )
        try:
            await client.connect_server()
        except Exception as e:
            print(e)
            sys.exit(1)
        await client.get_tools()
        self.mcp_manual = client.generate_sandbox_manual()
        # print(f"Manual retrieved:\n{manual}")
        await client.cleanup()

    def extract_code(self, llm_output: str) -> tuple[str | None, str | None]:
        pattern = r"```(?:python)?\s*\n(.*?)```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            code = match.group(1)
            code = self.sanitize_code(code)
            truncated_output = llm_output[:match.end(1)]
            return code, truncated_output
        # <tool_call>fn(args)</tool_call>
        pattern = (
            r"<tool_call>\s*"
            r"([a-zA-Z_]\w*\([^)]*\))"
            r"\s*(?:</tool_call>|$)"
        )
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            tool_call = match.group(1)
            truncated_output = llm_output[:match.end()]
            return tool_call, truncated_output
        pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            content = match.group(1)
            name_match = re.match(r"\s*([a-zA-Z_]\w*)", content)
            if not name_match:
                return None, None
            tool_name = name_match.group(1)
            args = dict(re.findall(
                r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>",
                content,
                re.DOTALL,
            ))
            truncated_output = llm_output[:match.end()]
            parts = []
            for k, v in args.items():
                v = v.strip()
                if not re.fullmatch(r"-?\d+(\.\d+)?|True|False|None", v):
                    v = repr(v)
                parts.append(f"{k}={v}")

            tool_call = f"{tool_name}({', '.join(parts)})"
            return tool_call, truncated_output
        return None, None

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
            self,
            prompt: str,
            llm_output: str,
            code: str,
            iteration: int,
            message: str
            ):
        new_prompt = f"{prompt}\n\nIteration {iteration}:\nYour output:\n\
            {llm_output}Extracted and executed code (first block only):\n"
        new_prompt += f"```python\n{code}\n```\n{message}\n"
        new_prompt += "Think for no more than 128 tokens, then generate one single code block"
        return new_prompt


if __name__ == '__main__':
    agent = AbstractAgent("", "", 5)
    agent.call_gemini("")
