


# General

- Your project must follow clean software architecture principles.
- All errors must be handled gracefully
- Your code must be readable, structured, and documented.

## Makefile

- clean or fclean removes containers


# Agentic Framework

- Implement a Thought → Code → Observation loop
- Your sandbox must provide explicit feedback to the LLM in all of these situations:
    - No valid code block was found in the model’s response
    - A code block was malformed but was interpreted anyway (explain how)
    - Execution hit the timeout and output is partial
    - Tool output was truncated due to size limits
    - An edit introduced a syntax error or lint violation



# Sandbox


## Misc

- The MCP tool files (mcp_tools_mbpp.py, mcp_tools_swebench.py) should be located at the root of your repository


# MBPP

All good!


# SWEBench

All Good!?

List:
    django__django-11066
    pydata__xarray-4629
    scikit-learn__scikit-learn-13439
    sympy__sympy-13480
    sympy__sympy-18189
    django__django-11880
    pydata__xarray-4094


| Task | llama-3 | compound | compound-mini | gemma-4-31b | openrouter | gemini | issue |
|-------|------|--------|------------|--------------|---------------|---------------|---------------|
|sympy__sympy-14711|✅|✅|✅|✅|✅|||
|pydata__xarray-4629||||✅||||
|django__django-11066|✅||✅|✅|✅|||
|django__django-13112|❌||||||test doesn't fully run|
|sympy__sympy-18189||||✅||||
|pydata__xarray-4629||||✅||||
|sympy__sympy-18189||||✅||||
|sympy__sympy-13480||||✅||||
|django__django-11066||||✅||||
|sympy__sympy-13480||||✅||||
|scikit-learn__scikit-learn-13439||||||||
|xxxxxxxxx||||||||
|xxxxxxxxx||||||||
|xxxxxxxxx||||||||
|xxxxxxxxx||||||||
|xxxxxxxxx||||||||
|xxxxxxxxx||||||||


Agent system descriptions — how do the top-performing systems design their agent loop, tools, and prompts?




