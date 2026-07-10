from dataclasses import dataclass
from typing import Optional, List
import os
import time
import requests


# ==================== Custom Exceptions ====================

class LLMError(Exception):
    """Base exception for LLM errors"""
    pass


class RateLimitError(LLMError):
    """Rate limit exceeded - should try next key or provider"""
    pass


class ProviderExhaustedError(LLMError):
    """All keys for this provider exhausted"""
    pass


class AllProvidersFailedError(LLMError):
    """All providers failed"""
    pass


# ==================== Data Classes ====================

@dataclass
class CallMetrics:
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    api_url: str
    model_name: str
    llm_output: str
    retries: int
    prompt: str


# ==================== Configuration ====================

PROVIDERS_KEY_CONST_MAP = {
    "groq": {
        "key_name": 'GROQ_API_KEY',
        "url": 'https://api.groq.com/openai/v1/chat/completions',
        "model": 'llama-3.3-70b-versatile',
        "num_keys": 3
    },
    "qwen": {
        "key_name": 'QWEN_API_KEY',
        "url": 'https://router.huggingface.co/v1/chat/completions',
        "model": 'Qwen/Qwen3-32B',
        "num_keys": 3
    },
    "openrouter": {
        "key_name": 'OPENROUTER_API_KEY',
        "url": 'https://openrouter.ai/api/v1/chat/completions',
        "model": 'openrouter/free',
        "num_keys": 4
    },
    "cerebras": {
        "key_name": 'CEREBRAS_API_KEY',
        "url": 'cerebras_url',
        "model": 'cerebras/zai-glm-4.7',
        "num_keys": 3
    },
    "gemini": {
        "key_name": 'GEMINI_API_KEY',
        "url": 'gemini_url',
        "model": 'gemini-3.5-flash',
        "num_keys": 3
    },
}

# Default priority order for provider rotation
DEFAULT_PROVIDER_PRIORITY = ["gemini", "cerebras", "groq", "qwen", "openrouter"]


# ==================== Main LLM Caller Class ====================

class LLMCaller:
    def __init__(
        self,
        provider: str = "groq",
        max_retries_per_key: int = 3,
        provider_priority: Optional[List[str]] = None
    ):
        self.provider = provider
        self.max_retries_per_key = max_retries_per_key
        self.provider_priority = provider_priority or DEFAULT_PROVIDER_PRIORITY
        self._initial_provider = provider
        self._initial_provider_index = self.provider_priority.index(provider)
        self.current_provider_index = self._initial_provider_index

    def reset_provider(self):
        """Reset to initial provider (useful for multiple independent calls)"""
        self.provider = self._initial_provider
        self.current_provider_index = self._initial_provider_index

    def _get_api_key(self, provider: str, key_num: int) -> Optional[str]:
        """Get API key for a specific provider and key number"""
        config = PROVIDERS_KEY_CONST_MAP[provider]
        base_key = config["key_name"]
        num_keys = config.get("num_keys", 1)

        if key_num > num_keys:
            return None

        key_name = base_key if num_keys == 1 else f"{base_key}_{key_num}"
        return os.environ.get(key_name)

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if an error indicates rate limiting"""
        error_msg = str(error).lower()
        return "429" in error_msg or "rate limit" in error_msg or "quota" in error_msg

    # ==================== Provider-Specific Single Call Methods ====================

    def _call_gemini_single(self, prompt: str, key_num: int) -> CallMetrics:
        """Single Gemini API call with specific key"""
        print("Calling Gemini...")
        from google import genai

        api_key = self._get_api_key("gemini", key_num)
        if not api_key:
            raise RateLimitError(f"No API key for gemini_{key_num}")

        config = PROVIDERS_KEY_CONST_MAP["gemini"]
        client = genai.Client(api_key=api_key)

        start_time = time.time()
        response = client.interactions.create(
            model=config["model"],
            input=prompt,
            extra_body={
                "stopSequences": ["\n```\n"],
                "maxOutputTokens": 256,
            }
        )
        elapsed_time_ms = (time.time() - start_time) * 1000
        llm_output = response.output_text
        if llm_output is None or llm_output == 'None':
            raise Exception("llm_output is None")
        return CallMetrics(
            input_tokens=response.usage.total_input_tokens,
            output_tokens=response.usage.total_output_tokens,
            request_time_ms=elapsed_time_ms,
            api_url=config["url"],
            model_name=response.model,
            llm_output=f"{llm_output}\n```\n",
            retries=0,
            prompt=prompt
        )

    def _call_groq_single(self, prompt: str, key_num: int) -> CallMetrics:
        """Single Groq API call with specific key"""
        print("Calling Groq...")
        from groq import Groq

        api_key = self._get_api_key("groq", key_num)
        if not api_key:
            raise RateLimitError(f"No API key for groq_{key_num}")

        config = PROVIDERS_KEY_CONST_MAP["groq"]
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=config["model"],
            stop=["\n```\n"]
        )
        llm_output = response.choices[0].message.content
        if llm_output is None or llm_output == 'None':
            raise Exception("llm_output is None")
        return CallMetrics(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            request_time_ms=response.usage.total_time * 1000,
            api_url=config["url"],
            model_name=response.model,
            llm_output=f"{llm_output}\n```\n",
            retries=0,
            prompt=prompt
        )

    def _call_cerebras_single(self, prompt: str, key_num: int) -> CallMetrics:
        """Single Cerebras API call with specific key"""
        print("Calling Cerebras...")
        from cerebras.cloud.sdk import Cerebras
        api_key = self._get_api_key("cerebras", key_num)
        if not api_key:
            raise RateLimitError(f"No API key for cerebras_{key_num}")
        config = PROVIDERS_KEY_CONST_MAP["cerebras"]
        client = Cerebras(api_key=api_key)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=config["model"],
            stop=["\n```\n"]
        )
        # Handle None response (Cerebras-specific issue)
        none_retries = 0
        while response.choices[0].message.content is None:
            none_retries += 1
            if none_retries >= 3:
                raise LLMError("Cerebras returned None after 3 retries")
            print(f"[cerebras] Response None, retry {none_retries}/3")
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=config["model"],
                max_completion_tokens=256,
                stream=False,
            )
        llm_output = response.choices[0].message.content
        if llm_output is None or llm_output == 'None':
            raise Exception("llm_output is None")
        return CallMetrics(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            request_time_ms=response.time_info.total_time * 1000,
            api_url=config["url"],
            model_name=response.model,
            llm_output=f"{llm_output}\n```\n",
            retries=0,
            prompt=prompt
        )

    def _call_generic_single(
        self, prompt: str, provider: str, key_num: int, timeout: int = 30
    ) -> CallMetrics:
        """Generic OpenAI-compatible API call via requests"""
        print(f"Calling {provider}...")
        config = PROVIDERS_KEY_CONST_MAP[provider]
        api_key = self._get_api_key(provider, key_num)

        if not api_key:
            raise RateLimitError(f"No API key for {provider}_{key_num}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            'Content-Type': 'application/json'
        }

        payload = {
            'model': config["model"],
            'messages': [{'role': 'user', 'content': prompt}],
            'stop': ["\n```\n"],
            'max_tokens': 256
        }

        start_time = time.time()
        response = requests.post(
            config["url"],
            json=payload,
            headers=headers,
            timeout=timeout
        )

        # Check for rate limiting before raise_for_status
        if response.status_code == 429:
            raise RateLimitError(f"Rate limited: {response.text}")

        response.raise_for_status()
        elapsed_time_ms = (time.time() - start_time) * 1000

        result = response.json()
        llm_output = result['choices'][0]['message']['content']
        if llm_output is None or llm_output == 'None':
            raise Exception("llm_output is None")

        return CallMetrics(
            input_tokens=result['usage']['prompt_tokens'],
            output_tokens=result['usage']['completion_tokens'],
            request_time_ms=elapsed_time_ms,
            api_url=config["url"],
            model_name=result.get('model', config["model"]),
            llm_output=f"{llm_output}\n```\n",
            retries=0,
            prompt=prompt
        )

    # ==================== Dispatch ====================

    def _call_provider_single(
        self, prompt: str, provider: str, key_num: int, timeout: int = 30
    ) -> CallMetrics:
        """Route to appropriate single-call method based on provider"""
        dispatch = {
            "gemini": lambda: self._call_gemini_single(prompt, key_num),
            "groq": lambda: self._call_groq_single(prompt, key_num),
            "cerebras": lambda: self._call_cerebras_single(prompt, key_num),
        }
        
        if provider in dispatch:
            return dispatch[provider]()
        else:
            return self._call_generic_single(prompt, provider, key_num, timeout)

    # ==================== Key Rotation with Retries ====================

    def _try_provider_with_key_rotation(
        self, prompt: str, provider: str, timeout: int = 30
    ) -> CallMetrics:
        """
        Try calling a provider, rotating through its keys with retries per key.

        Flow for each key:
        - On rate limit: immediately try next key
        - On other error: retry up to max_retries_per_key, then try next key

        Raises ProviderExhaustedError if all keys are exhausted.
        """
        config = PROVIDERS_KEY_CONST_MAP[provider]
        num_keys = config.get("num_keys", 1)
        total_retries = 0

        for key_num in range(1, num_keys + 1):
            for attempt in range(self.max_retries_per_key):
                try:
                    result = self._call_provider_single(
                        prompt, provider, key_num, timeout
                    )
                    result.retries = total_retries
                    return result

                except RateLimitError:
                    total_retries += 1
                    print(f"[{provider}] Key {key_num} rate limited, rotating key")
                    break  # Move to next key immediately

                except requests.exceptions.HTTPError as e:
                    total_retries += 1
                    if self._is_rate_limit_error(e):
                        print(f"[{provider}] Key {key_num} rate limited (HTTP), rotating key")
                        break
                    elif attempt < self.max_retries_per_key - 1:
                        print(f"[{provider}] Key {key_num} error {attempt+1}/\
                            {self.max_retries_per_key}: {e}")
                        time.sleep(1)
                        continue
                    else:
                        print(f"[{provider}] Key {key_num} exhausted after {self.max_retries_per_key} retries: {e}")
                        break

                except Exception as e:
                    total_retries += 1
                    if self._is_rate_limit_error(e):
                        print(f"[{provider}] Key {key_num} rate limited, \
                            rotating key")
                        break
                    elif attempt < self.max_retries_per_key - 1:
                        print(f"[{provider}] Key {key_num} error {attempt+1}/\
                            {self.max_retries_per_key}: {e}")
                        time.sleep(1)
                        continue
                    else:
                        print(f"[{provider}] Key {key_num} exhausted after {self.max_retries_per_key} retries: {e}")
                        break

        raise ProviderExhaustedError(
            f"{provider} exhausted all {num_keys} keys after {total_retries} attempts"
        )

    # ==================== Provider Rotation ====================

    def rotate_provider(self) -> bool:
        """Rotate to the next provider in priority list. Returns False if no more providers."""
        self.current_provider_index += 1
        if self.current_provider_index < len(self.provider_priority):
            self.provider = self.provider_priority[self.current_provider_index]
            print(f"[LLM] Rotating to provider: {self.provider}")
            return True
        return False

    # ==================== Main Entry Point ====================

    def call_llm(self, prompt: str, timeout: int = 30) -> CallMetrics:
        """
        Main entry point for calling LLMs.

        Handles (in order):
        1. Retries with same key (up to max_retries_per_key)
        2. Key rotation within provider (KEY_1 → KEY_2 → ...)
        3. Provider rotation when all keys exhausted (groq → qwen → ...)

        Args:
            prompt: The prompt to send to the LLM
            timeout: Request timeout in seconds

        Returns:
            CallMetrics with response data and metadata

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        errors = []

        while True:
            try:
                return self._try_provider_with_key_rotation(prompt, self.provider, timeout)

            except ProviderExhaustedError as e:
                errors.append(str(e))
                if self.rotate_provider():
                    continue
                else:
                    break

            except Exception as e:
                errors.append(f"{self.provider}: {e}")
                if self.rotate_provider():
                    continue
                else:
                    break

        error_summary = "\n  - ".join(errors)
        raise AllProvidersFailedError(
            f"All {len(self.provider_priority)} providers failed:\n  - {error_summary}"
        )