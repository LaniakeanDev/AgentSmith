*This activity has been created as part of the 42 curriculum by rzins*

# Agent Smith: Autonomous Code Agent Framework

## Description

Agent Smith is an autonomous agentic framework designed to solve coding challenges through iterative reasoning, code generation, and execution. The system implements a Thought → Code → Observation loop, allowing it to:

- Reason about programming tasks
- Generate executable Python code
- Execute code in a sandboxed environment
- Observe results and refine approaches
- Iterate until finding a solution

The framework supports two benchmarks:
- **MBPP (Mostly Basic Python Problems)**: Algorithmic Python problem solving
- **SWE-bench**: Real-world bug fixing in production repositories

Built around the Model Context Protocol (MCP) for tool integration and controlled code execution, Agent Smith demonstrates how AI systems can move beyond static prompts to become autonomous problem-solving agents.

## System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       Agent/Orchestrator                       │
│                    Central Loop & Control Flow                 │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────────┐
│                      Code Extraction Layer                     │
│   Parses LLM response, extracts code blocks, converts formats  │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 ▼
┌───────────────────────────────────────────────────────────────┐
│                         Sandbox                               │
│  ┌─────────────────────┐    ┌────────────────────────────┐    │
│  │  Security Layer     │    │   MCP Client               │    │
│  │  - Import controls  │    │   - Tool discovery         │    │
│  │  - Path restrictions│    │   - Tool execution         │    │
│  │  - Timeouts/Memory  │    │   - stdio & HTTP support   │    │
│  └─────────────────────┘    └──────────┬─────────────────┘    │
└─────────────────────────────────────────┼─────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────┐
│                        MCP Server(s)                         │
│   ┌─────────────────────┐    ┌────────────────────────────┐  │
│   │ MBPP Tools          │    │ SWE-bench Tools            │  │
│   │ - run_tests()       │    │ - run_tests()              │  │
│   │                     │    │ - read_file()              │  │
│   │                     │    │ - edit_file()              │  │
│   │                     │    │ - search_code()            │  │
│   │                     │    │ - run_command()            │  │
│   │                     │    │ - get_patch()              │  │
│   └─────────────────────┘    └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Agent/Orchestrator**: Central loop managing LLM calls, code extraction, sandbox execution, and iteration

2. **Code Extraction Layer**: Transforms LLM responses into executable Python code, supporting multiple formats:
   - Python code blocks (` ```python ... ``` `)
   - XML tool calls (Anthropic-style)
   - JSON/Hermes tool calls
   - ReAct format

3. **Sandbox**: Secure execution environment with:
   - Import allowlisting
   - Filesystem path restrictions
   - Execution timeouts
   - Memory limits
   - Network isolation

4. **MCP Integration**: Dynamic tool discovery and execution via Model Context Protocol, supporting both stdio and streamable HTTP transports

## Agent Loop Explanation

The agent operates through a structured iterative cycle:

### 1. **Thought Phase**
- LLM receives system prompt with tool documentation and task context
- Model reasons about the current state and plans next actions
- Outputs structured response containing reasoning and code

### 2. **Code Phase**
- Extract Python code from LLM response
- Support multiple extraction formats:
  - Primary: ` ```python ... ``` ` code blocks
  - Alternative: Convert XML/JSON/ReAct to Python function calls
- Inject final_answer() function and MCP tool wrappers into namespace

### 3. **Observation Phase**
- Execute extracted code in sandbox
- Capture stdout, stderr, and return values
- Enforce security constraints (imports, paths, timeout, memory)
- Format results for LLM feedback

### 4. **Iteration**
- Feed observation back to LLM with conversation history
- Repeat until final_answer() is called or iteration limit reached
- Track tokens, time, and progress metrics

### Key Design Decisions

- **Code-based Tool Calling**: More expressive than JSON, allowing persistent variables, loops, and complex multi-step reasoning
- **Security Boundaries**: Sandbox and MCP tools are independent security domains
- **Transparent Feedback**: Explicit messages for all failure modes (no valid code, timeout, truncation, syntax errors)
- **Format Agnostic**: Extraction layer handles multiple model output formats

## Sandbox Design

### Security Implementation

**Import Controls**: Allowlist approach using Python's built-in import system
```python
class SandboxConfig(BaseModel):
    authorized_imports: List[str] = [
        "math", "collections", "itertools", "re", "json",
        "typing", "functools", "operator", "heapq", "bisect",
        "copy", "string", "random", "datetime", "array", "cmath"
    ]
```

**Filesystem Restrictions**: Limited to allowed directories (e.g., /testbed, /tmp/agent)

**Resource Limits**:
- Execution timeout: Configurable (default: 30s for MBPP, 900s for SWE-bench)
- Memory limit: Configurable (default: 512MB)
- Network access: Blocked entirely

**Builtin Overrides**: Dangerous builtins removed or restricted

### Sandbox CLI Interface

```bash
# Launch interactive sandbox
uv run sandbox

# With custom configuration
uv run sandbox sandbox_template.json

# With MBPP tools (stdio)
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json

# With SWE-bench tools
uv run sandbox --mcp-stdio "python mcp_tools_swebench.py" sandbox_template.json
```

### final_answer Tool

The sandbox injects `final_answer()` into the execution namespace:
- **MBPP**: `final_answer(solution_code)` — passes Python code as argument
- **SWE-bench**: `final_answer(get_patch())` — passes git patch from get_patch()

This signals task completion to the agent loop, unlike MCP tools which operate outside the sandbox.

## Tool Implementation Details

### File System Tools

- **read_file(filepath, start_line, end_line)**: Reads file with line numbers (cat -n format)
- **edit_file(filepath, old_str, new_str)**: Exact string replacement in files
- **list_files(directory, pattern)**: Lists files matching pattern

### Code Search Tools

- **search_code(pattern, file_pattern)**: Grep-like search across codebase
- **search_function_or_class_definition_in_code(name)**: Finds definition location
- **find_references(name, filepath, line)**: Finds all usages of symbol

### Execution Tools

- **run_tests()**: Executes evaluation script (MBPP)
- **get_patch()**: Retrieves unified git diff (SWE-bench)
- **run_command(command, workdir)**: Executes shell command with stdout/stderr/exit code

### MCP Integration

Tools are exposed via Model Context Protocol servers:
- Dynamic discovery from connected MCP server
- Callable as Python functions from sandbox
- Both stdio and streamable HTTP transports supported
- Mandatory tools tested independently during evaluation

## Instructions

### Prerequisites

- Python 3.10
- uv package manager
- Docker
- LLM API keys (OpenRouter, Cerebras, Groq, etc.)

### Installation

```bash
# Clone repository
git clone [your-repo-url]
cd [repo-name]

# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running MBPP Agent

```bash
# Dump task
cd moulinette
uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json

# Run agent
cd ../student
uv run python -m agent_mbpp \
    --task-file ../cache/mbpp_task.json \
    --output ../cache/mbpp_solution.json \
    --model-name "model/name" \
    --provider-url "https://provider.api/v1"

# Validate solution
cd ../moulinette
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

### Running SWE-bench Agent

```bash
# Dump task
cd moulinette
uv run moulinette_eval dump swebench --output ../cache/swebench_task.json

# Run agent
cd ../student
uv run python -m agent_swebench \
    --task-file ../cache/swebench_task.json \
    --output ../cache/swebench_solution.json \
    --model-name "model/name" \
    --provider-url "https://provider.api/v1"

# Validate solution
cd ../moulinette
uv run moulinette_eval validate swebench ../cache/swebench_task.json ../cache/swebench_solution.json
```

### Evaluation

```bash
# Run MBPP evaluation
./exam_mbpp.sh --student-path ./student --moulinette-path ./moulinette --env-file /path/to/.env

# Run SWE-bench evaluation
./exam_swebench.sh --student-path ./student --moulinette-path ./moulinette --env-file /path/to/.env

# Run sandbox security tests
./exam_sandbox.sh --student-path ./student --moulinette-path ./moulinette --env-file /path/to/.env
```

### Limits

**MBPP**:
- 10 iterations max
- 6,000 input tokens (cumulative)
- 1,500 output tokens (cumulative)
- 120 seconds timeout

**SWE-bench**:
- 30 iterations max
- 300,000 input tokens (cumulative)
- 10,000 output tokens (cumulative)
- 900 seconds timeout

## Benchmark Results and Analysis

### Model Comparison

Five models were evaluated on three SWE-bench tasks. Results are documented in `BENCHMARK_REPORT.md`.

| Model | Task | Status | Iterations | Input Tokens | Output Tokens | Wall Time (s) |
|-------|------|--------|------------|--------------|---------------|---------------|
| **llama-3.3-70b-versatile** | pydata__xarray-4629 | ✅ PASS | 4 | 11,701 | 246 | 12 |
| | django__django-11066 | ✅ PASS | 3 | 9,823 | 208 | 10 |
| | sympy__sympy-18189 | ✅ PASS | 6 | 20,942 | 392 | 49 |
| **openrouter/free** | pydata__xarray-4629 | ✅ PASS | 15 | 49,941 | 2,012 | 231 |
| | django__django-11066 | ✅ PASS | 9 | 17,759 | 530 | 54 |
| | sympy__sympy-18189 | ❌ FAIL | 10 | 30,862 | 2712 | 317 |
| **qwen3.6-27b** | pydata__xarray-4629 | ✅ PASS | 4 | 14,030 | 583 | 54 |
| | django__django-11066 | ✅ PASS | 5 | 19,613 | 567 | 95 |
| | sympy__sympy-18189 | ✅ PASS | 6 | 23,097 | 928 | 124 |
| **gemma-4-31b** | pydata__xarray-4629 | ✅ PASS | 5 | 19,409 | 532 | 15 |
| | django__django-11066 | ✅ PASS | 6 | 27,771 | 791 | 14 |
| | sympy__sympy-18189 | ✅ PASS | 6 | 30,031 | 747 | 44 |
| **gemini-3.1-flash-lite** | pydata__xarray-4629 | ✅ PASS | 8 | 29,278 | 531 | 29 |
| | django__django-11066 | ❌ FAIL | 11 | 51,240 | 684 | 31 |
| | sympy__sympy-18189 | ✅ PASS | 6 | 20,251 | 277 | 34 |


**Analysis**

- Best Overall Model: gemma-4-31b achieved a perfect 3/3 success rate with the most balanced performance—fast execution (15-44s), moderate token usage (19k-30k input tokens), and low iterations (5-6 per task).

- Highest Efficiency: llama-3.3-70b-versatile solved 3/3 tasks with exceptional efficiency—fewest iterations (3-6), lowest token consumption (9.8k-20.9k input), and fastest wall times (10-49s). The model demonstrates superior reasoning efficiency and is ideal for cost-sensitive deployments.

- Most Prolific but Inconsistent: openrouter/free attempted the most iterations (9-15) and consumed the most tokens (17.7k-49.9k input) but failed on sympy__sympy-18189, suggesting poor reasoning efficiency or struggles with complex tasks.

- Surprise Contender: qwen3.6-27b achieved 3/3 success with moderate performance across all metrics, outperforming more established models on the difficult sympy task where openrouter/free failed.

- Mixed Performer: gemini-3.1-flash-lite failed on django__django-11066 despite being the fastest model for xarray and sympy tasks (29-34s), indicating potential weaknesses in certain problem domains.

### Key Findings

- Model selection significantly impacts success - 3/5 models achieved 100% success rate, while 2/5 failed on at least one task

- Openrouter/free demonstrated poor cost-efficiency, requiring 2-4x more resources than other successful models while still failing on one task

- gemma-4-31b is the clear winner for production deployment, offering the best balance of speed, token efficiency, and reliability

- Complexity matters - all models struggled most with sympy tasks (highest token usage and iterations)

### Selected Pipeline

The final pipeline uses:
```yaml
primary_model: gemma-4-31b
fallback_models:
    qwen3.6-27b
    llama-3.3-70b-versatile
```

## Resources

### Documentation
- [Model Context Protocol (MCP) Specification](https://modelcontextprotocol.io)
- [SWE-bench Dataset](https://swe-bench.github.io)
- [MBPP Dataset](https://huggingface.co/datasets/google-research-datasets/mbpp)

### Articles & Tutorials
- "Building Effective Agents" - Anthropic
- "The Thought-Action-Observation Loop" - ReAct Paper
- "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"

### LLM Providers (Free Tier)
- [Cerebras](https://cloud.cerebras.ai)
- [OpenRouter](https://openrouter.ai)
- [Groq](https://groq.com)
- [Google AI Studio (Gemini)](https://ai.google.dev)

### AI Usage
This project was developed with AI assistance for:
- **Code Generation**: Initial scaffolding of MCP client/server implementation
- **Documentation**: README structure and technical writing
- **Debugging**: Troubleshooting complex issues in sandbox and MCP integration
- **Testing**: Generating test cases for tool validation

All AI-generated code was reviewed, understood, and verified before inclusion. Peer review was used as a quality checkpoint throughout development.













































------------



## MBPP Moulinette

[terminal 1 (moulinette venv activated)]
```bash
systemctl --user start podman.socket
podman system service --time=0
```

[terminal 2 (moulinette venv activated)]
```bash
podman pull python:3.11-slim
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

## SWEBench Moulinette

```bash
make socket
```

```bash
uv run moulinette_eval validate swebench ../cache/swebench_task.json ../cache/swebench_solution.json
```
makefile rule

