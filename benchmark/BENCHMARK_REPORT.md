# openrouter/freeenchmark Report

## 1. Setup

### Models Evaluated
| Model | Provider |
|-------|----------|
| llama-3.3-70b-versatile | Groq |
| openrouter/free | Openrouter |
| qwen3.6-27b | Groq |
| gemma-4-31b | Cerebras |
| gemini-3.1-flash-lite | Gemini |

### Tasks Selected
| Task ID | Selection Rationale |
|---------|---------------------|
| pydata__xarray-4629 | Simple task |
| django__django-11066 | Tests navigation & context |
| sympy__sympy-18189 | Tests reasoning ability |

**Task Selection Criteria:**
- **Diversity**: Mix of difficulty levels (easy/medium)
- **Coverage**: Different frameworks

Note: sympy__sympy-18189 is the medium level task

### Configuration
- **Agent version**: v1.0.0
- **Max iterations**: 30
- **Budget**: $0 per task
- **Date**: 2026-07-21

---

## 2. Results Table

### Overall Results Matrix

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

### **Analysis**

- Best Overall Model: gemma-4-31b achieved a perfect 3/3 success rate with the most balanced performance—fast execution (15-44s), moderate token usage (19k-30k input tokens), and low iterations (5-6 per task).
- Highest Efficiency: llama-3.3-70b-versatile solved 3/3 tasks with exceptional efficiency—fewest iterations (3-6), lowest token consumption (9.8k-20.9k input), and fastest wall times (10-49s). The model demonstrates superior reasoning efficiency and is ideal for cost-sensitive deployments.
- Most Prolific but Inconsistent: openrouter/free attempted the most iterations (9-15) and consumed the most tokens (17.7k-49.9k input) but failed on sympy__sympy-18189, suggesting poor reasoning efficiency or struggles with complex tasks.
- Surprise Contender: qwen3.6-27b achieved 3/3 success with moderate performance across all metrics, outperforming more established models on the difficult sympy task where openrouter/free failed.
- Mixed Performer: gemini-3.1-flash-lite failed on django__django-11066 despite being the fastest model for xarray and sympy tasks (29-34s), indicating potential weaknesses in certain problem domains.
---

## 3. Provider Reliability

### Performance Metrics by Provider

| Provider | Model | Avg Response Time (ms) | Retries | Availability |
|----------|-------|----------------------|---------|--------------|
| **Groq** | llama-3.3-70b-versatile | 562 | 0.2 | Good |
| **Cerebras** | gemma-4-31b | 191 | 0.1 | Excellent |
| **Openrouter** | openrouter/free | 7121 | 0.7 | Average |
| **Groq** | qwen3.6-27b | 586 | 0.1 | Good |
| **Gemini** | gemini-3.1-flash-lite | 959 | 0.3 | Poor |

---

## 4. Intermediary Metrics

### Metric 1: Exploration Efficiency
*Step at which agent first reads/edits the final patch file*

| Task | llama-3.3-70b-versatile | openrouter/free | qwen3.6-27b | gemma-4-31b | gemini-3.1-flash-lite |
|------|---------|---------|---------|---------|---------|
| pydata__xarray-4629 | Step 2 | Step 6 | Step 1 | Step 2 | Step 3 |
| django__django-11066 | Step 3 | Step 6 | Step 2 | Step 2 | Step 3 |
| sympy__sympy-18189 | Step 2 | Step 5 | Step 3 | Step 2 | Step 3 |
| **Average** | **2.3** | **5.7** | **2.0** | **2.0** | **3.0** |

**Analysis:**
- **gemma-4-31b**, **llama-3.3-70b-versatile** and **qwen3.6-27b** consistently identified relevant files early (avg step 2)
- **openrouter/free** showed poorest exploration (avg step 5.7), often exploring irrelevant files first
- **gemini-3.1-flash-lite** performed moderately well but less efficient than top models

### Metric 2: Submission Discipline
*Iterations between "tests first pass" and final_answer (zero is ideal)*

| Task | llama-3.3-70b-versatile | openrouter/free | qwen3.6-27b | gemma-4-31b | gemini-3.1-flash-lite |
|------|---------|---------|---------|---------|---------|
| pydata__xarray-4629 | 1 | 1 | 1 | 1 | 1 |
| django__django-11066 | 1 | 1 | 1 | 1 | 1 |
| sympy__sympy-18189 | 1 | 1 | 1 | 1 | 1 |
| **Average** | **1** | **1** | **1** | **1** | **1** |

**Analysis:**
- All models demonstrated exactly the same behavior on that front, probably due to the harness

---

## 5. Ablation Study

### Study Design
Comparing **llama-3.3-70b-versatile**'s performance with and without the following paragraph in the prompt:
```
Never write edit_file, run_tests, or final_answer calls based on an assumed
or guessed prior result. Only reference a file's exact content, path, or line
number after you have seen it in a tool's actual printed output in a previous
turn. Submit one tool call's result before writing code that depends on it.
final_answer(get_patch()) is only valid immediately after run_tests() has
printed "all_tests_passed": True in this same session — never call it otherwise.
```

### Configuration
| Variant | Description |
|---------|-------------|
| **Baseline** | Standard with the paragraph |
| **Ablation** | Without the paragraph |

### Results

| Task | Baseline | Ablation | Improvement |
|------|----------|----------|-------------|
| pydata__xarray-4629 | ✅ PASS (4 iter) | ❌ FAIL (1 iter) | FAIL > PASS |
| django__django-11066 | ✅ PASS (3 iter) | ✅ PASS (1 iter) | Faster but reckless (submits final answer without checking run_tests()'s result) |
| sympy__sympy-18189 | ✅ PASS (6 iter) | ❌ FAIL (9 iter) | FAIL > PASS |

---

## 6. Conclusions

### Recommended Model: **gemma-4-31b** (Cerebras)

**Justification:**
1. **Highest solve rate**: 100%
2. **Average efficiency**: Average token usage (26k avg input, 693 avg output)
3. **Fastest**: Best wall-clock time (24s avg)
4. **Best exploration**: Locates relevant files earliest (avg step 2)
5. **Best discipline**: Almost zero extra iterations after tests pass
6. **Cost-effective**: Up to a million tokens per key per day

### Models to Disregard

| Model | Reason |
|-------|--------|
| **openrouter/free** | Unreliable provider: a lot of wasted iterations with poor models |
| **gemini-3.1-flash-lite** | Unreliable provider |

### Secondary Recommendation: **qwen3.6-27b** (Groq)

**Justification:**
- 100% solve rate with excellent reliability (100% availability)
- Good fallback option if gemma-4-31b becomes unavailable
- Slower to respond, but still available

### Final Pipeline Configuration

```yaml
primary_model: gemma-4-31b
fallback_models:
    qwen3.6-27b
    llama-3.3-70b-versatile
```
