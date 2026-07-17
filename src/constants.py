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
        "url": 'https://api.cerebras.ai/v1',
        "model": 'cerebras/gemma-4-31b',
        "num_keys": 3
    },
    "gemini": {
        "key_name": 'GEMINI_API_KEY',
        "url": 'gemini_url',
        "model": 'gemini-3.5-flash',
        "num_keys": 3
    },
}

DEFAULT_PROVIDER_MODEL = 'groq/llama-3.3-70b-versatile'
