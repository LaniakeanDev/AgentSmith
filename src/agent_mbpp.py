import sys
import re
import requests
import os
from dotenv import load_dotenv
from sandbox_mbpp.config import SandboxConfig
from sandbox_mbpp.sandbox import Sandbox
from groq import Groq


def call_groq(prompt, model='llama-3.3-70b-versatile'):
    load_dotenv()
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=model,
    )
    return chat_completion.choices[0].message.content


def call_openrouter(prompt, model='openrouter/free'):
    """Make a call to OpenRouter API"""
    # Usage
    # response = call_openrouter("4 + 2 =")
    # print(response)
    load_dotenv()
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

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()  # Raises exception for bad status codes

        result = response.json()
        return result['choices'][0]['message']['content']

    except requests.exceptions.Timeout:
        return "Error: Request timed out"
    except requests.exceptions.HTTPError as e:
        return f"HTTP Error: {e}"
    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"
    except KeyError:
        return "Error: Unexpected API response format"


task = {
    "text": "Write a function to find the n-th rectangular number.",
    "code": "def find_rect_num(n):\r\n  return n*(n + 1) ",
    "task_id": 35,
    "test_setup_code": "",
    "test_list": ["assert find_rect_num(4) == 20", "assert find_rect_num(5) \
== 30", "assert find_rect_num(6) == 42"],
    "challenge_test_list": []
    }


def sanitize_code(code: str) -> str:
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


def solve_task(task: dict):
    task_def = task["text"]
    test_list = task["test_list"]
    prompt = task_def + "\nTest list: " + str(test_list)
    prompt += " reply with nothing but the code starting by '```python':"
    print("Sending request...")
    # response = call_openrouter(prompt)
    response = call_groq(prompt)
    response = response.strip()
    pattern = r'```python\n(.*?)```'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        code = match.group(1)
        code = sanitize_code(code)
    else:
        print(f"response doesn't have a ```python declaration:\n{response}")
        sys.exit(1)
    split_code = code.split("\n")
    code = ""
    for line in split_code:
        if "assert" not in line and "test" not in line.lower() \
                and "if __name__ ==" not in line:
            code += line + '\n'
    test_code = "\nsuccess = True"
    for test in test_list:
        func_call = test[6:].split('==')[0]
        test_code += f"""\ntry:\n    {test}\n    print("Passed test: \
'{test}'")\nexcept AssertionError:\n    print(f"Failed test: '{test}' got \
{{{func_call}}} instead")\n    success = False\n"""
    test_code += f"""\nif success:\n    final_answer(\'\'\'{code}\'\'\')"""
    code += '\n\n' + test_code
    # print("\n\nafter generating the code:")
    # print(code)
    config = SandboxConfig()
    server_path = 'src/fastmcp_server.py'
    sandbox = Sandbox(config, server_path)
    sandbox.configure()
    result = sandbox.execute(code)
    iteration_count = 1
    if result.success and result.final_answer is not None:
        print("Problem solved! The solution is:")
        print(result.final_answer)
    elif result.success:
        print("Execution was able to complete but some tests failed")
        print(result.output)
    else:
        print("\nExecution could not complete:")
        print(result.error)


if __name__ == '__main__':
    solve_task(task)
