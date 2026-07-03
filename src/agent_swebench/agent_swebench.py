import asyncio
# import re
import subprocess
import sys
# from typing import List
import re
import time
from typing import List
from abstract_agent import AbstractAgent
# from agent_mbpp.mbpp_models import (
#     CallMetrics, MBPPTaskInput, SolutionOutput, StepMetrics)
# import requests
# import time
# import os
# from dotenv import load_dotenv
from abstract_spawner import Spawner
from models import CallMetrics
from sandbox.mcp_client import MCPClient
from sandbox.sandbox_models import ExecutionResult, SandboxConfig
from .swebench_models import StepMetrics, SWEBenchTaskInput, SolutionOutput
# from sandbox.sandbox_models import ExecutionResult, SandboxConfig
# from sandbox.spawner import Spawner
# from groq import Groq


class SWEBenchAgent(AbstractAgent):
    def __init__(
            self,
            provider_model: str,
            provider_url: str,
            max_iterations: int,
            config: SandboxConfig):
        super().__init__(provider_model, provider_url, max_iterations)
        self.mcp_manual: str | None = None
        self.authorized_imports = ""
        self.config = config
        self.og_prompt = ""
        self.prompt_ext = ""
        # self.get_sandbox_manual()

    async def get_sandbox_manual(self):
        await self.get_mcp_manual()
        authorized_imports = self.config.authorized_imports
        for item in authorized_imports:
            self.authorized_imports += f"{item}, "
        self.authorized_imports = self.authorized_imports[:-2]

    async def get_mcp_manual(self):
        client = MCPClient("python sandbox/swebench_server.py")
        try:
            await client.connect_server()
        except Exception as e:
            print(e)
            sys.exit(1)
        await client.get_tools()
        self.mcp_manual = client.generate_sandbox_manual()
        # print(f"Manual retrieved:\n{manual}")
        await client.cleanup()

    # def extract_code(self, llm_output: str) -> str | None:
    #     pattern = r'```python\n(.*?)```'
    #     matches = re.findall(pattern, llm_output, re.DOTALL)
    #     if matches:
    #         code = self.sanitize_code(matches[-1])  # Take the last one
    #         return code
    #     return None
    def extract_code(self, llm_output: str) -> str | None:
        pattern = r'```python\n(.*?)```'
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            code = match.group(1)
            code = self.sanitize_code(code)
            return code
        else:
            return None

    def build_image(self, task: SWEBenchTaskInput):
        container_name = f"swebench_{task.instance_id}_{int(time.time())}"
        base_image = task.docker_image
        if not base_image.startswith(("docker.io/", "quay.io/", "ghcr.io/", "gcr.io/")):
            base_image = f"docker.io/{base_image}"
        build_result = subprocess.run([
            "docker", "build",
            "--build-arg", f"BASE_IMAGE={base_image}",
            "--network=host",
            "-t", container_name,
            "-f", "Dockerfile.swebench",
            "./src/sandbox"
        ], capture_output=True, text=True)
        if build_result.returncode != 0:
            raise RuntimeError(f"Build failed: {build_result.stderr}")
        print(f"Image built: {container_name}")
        return container_name

    def sandbox_exec(
            self,
            extracted_code: str,
            container_name: str):
        server_path = 'src/swebench_server.py'
        docker_cmd = [
            "docker", "run", "--rm",
            # "--network=none"
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            f"--memory={self.config.max_memory_mb}m",
            "--cpus=1",
            "-i",
            container_name,
            "python", "-m", "sandbox_swebench"
        ]
        spawner = Spawner(self.config, server_path)
        return spawner.spawn(
            code=extracted_code,
            docker_cmd=docker_cmd,
            task_type="swebench")

    def handle_task(self, task: SWEBenchTaskInput):
        task_start = time.time()
        prompt = self.get_prompt(task)
        # print(f"\n\nprompt:\n\n{prompt}\n\n")
        # sys.exit(0)
        print("\n\nIteration 1")
        print(f"Calling {self.provider}...")
        call_metrics = self.call_llm(prompt)
        print("Response received")
        llm_output = call_metrics.llm_output.strip()
        print(f"\n\nllm_output:\n{llm_output}\n")
        extracted_code = self.extract_code(llm_output)
        print(f"extracted_code:\n{extracted_code}")
        # sys.exit(0)
        iteration_count = 1
        while extracted_code is None and \
                iteration_count <= self.max_iterations:
            # no python code found in answer
            # send feedback, retry
            print("Extracted code is None")
            return None
        try:
            container_name = self.build_image(task)
        except Exception as e:
            print(f"Agent: {type(e).__name__}: {str(e)}")
            sys.exit(1)
        print("Executing in sandbox...")
        result = self.sandbox_exec(extracted_code, container_name)
        import pprint
        print(f"\nresult_{iteration_count}:")
        pprint.pprint(result)
        step_metrics_list: List[StepMetrics] = []
        step_metrics = self.get_step_metrics(
            code=extracted_code,
            result=result,
            call_metrics=call_metrics,
            iteration_count=iteration_count
        )
        step_metrics_list.append(step_metrics)
        code = extracted_code
        while result.final_answer is None and \
                iteration_count < self.max_iterations:
            exec_output = result.output
            if result.success:
                message = f"Execution completed:"\
                        f"{exec_output}"
            else:
                message = f"Execution could not complete:\n{result.error}"
            print(message)
            prompt = self.get_new_prompt(
                prompt=prompt,
                code=code,
                exec_output=exec_output,
                iteration_count=iteration_count,
                message=message
                )
            iteration_count += 1
            print(f"\n\nIteration {iteration_count}")
            print(f"Calling {self.provider}...")
            call_metrics = self.call_llm(prompt)
            print("Response received")
            llm_output = call_metrics.llm_output.strip()
            print(f"llm_output:\n{llm_output}\n")
            extracted_code = self.extract_code(llm_output)
            print(f"extracted_code:\n{extracted_code}")
            while extracted_code is None and \
                    iteration_count <= self.max_iterations:
                # no python code found in answer
                # send feedback, retry
                print("Extracted code is None")
                return None
            print("Executing in sandbox...")
            result = self.sandbox_exec(extracted_code, container_name)
            # print(f"result_{iteration_count}:\n{result}")
            # result, code = self.sandbox_exec(
            #     llm_output=llm_output, test_list=task.test_list)
            step_metrics = self.get_step_metrics(
                code=extracted_code,
                result=result,
                call_metrics=call_metrics,
                iteration_count=iteration_count
            )
            step_metrics_list.append(step_metrics)
        task_duration = time.time() - task_start
        if not result.final_answer:
            print("Could not solve this problem")
            return SolutionOutput(
                task_id=str(task.instance_id),
                benchmark="swebench",
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
            print(result.output)
            return SolutionOutput(
                task_id=str(task.instance_id),
                benchmark="swebench",
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

    def get_prompt(self, task: SWEBenchTaskInput):
#         return f"""
# # SWE-bench Agent System Prompt

# **Role:** You are an expert software engineer AI, specialized in debugging, navigating, and fixing code in large, unfamiliar codebases. Your goal is to resolve the given issue by producing a correct and minimal `git` patch.

# **Context:** You have been given a task from the SWE-bench dataset. You are working inside a Docker container that contains the target repository. You have a set of tools available to you to explore the codebase, run tests, and make changes.

# ---

# ## Core Principles

# 1.  **Iterative Reasoning:** You must follow a strict **Thought -> Code -> Observation** loop. In each iteration, you will:
#     - **Thought:** Provide a clear, concise explanation of your plan for this step. What are you trying to learn or achieve?
#     - **Code:** Write Python code that uses the available tools to execute your plan.
#     - **Observation:** (Provided automatically by the system) You will then receive the output of your code. Use this to inform your next thought.

# 2.  **Persistence & Exploration:** Do not give up. If a plan fails, analyze the output, adjust your hypothesis, and try a new approach. Be methodical and persistent.

# 3.  **Efficiency:** Be mindful of resource limits (iterations, tokens, time). Each action should have a clear purpose. Avoid aimless searching.

# 4.  **Self-Correction:** If you encounter an error (syntax error, tool failure, etc.), you will receive the error output. Acknowledge the error, analyze its cause, and correct it in your next step. Do not ignore errors.

# 5.  **Minimalism:** When you find the fix, make the smallest change possible to resolve the issue. The goal is to create a clean, minimal patch that passes the test suite.

# ---

# ## Tools Available

# You have access to the following tools, which you can call as Python functions in your code block. For details on parameters, refer to the generated manual.

# {self.mcp_manual}


# ## Authorized Imports

# You are authorized to use only the following imports:

# {self.authorized_imports}

# ---

# ## Workflow & Strategy Recommendations

# 1.  **Understand the Problem:** Start by carefully reading the `problem_statement`. Identify the core issue. What is the expected behavior? What is the actual behavior?

# 2.  **Initial Exploration:**
#     - Use `search_code` to find keywords from the problem statement (e.g., function names, error messages).
#     - Use `read_file` to examine any suspect files you find.
#     - Use `run_command` to understand the repository structure (e.g., `ls -la`, `git log --oneline`).
#     - Your goal in the first few iterations is to locate the most relevant file(s) and the specific function(s) likely to be the source of the bug.

# 3.  **Formulate a Hypothesis:**
#     - Based on your exploration, what do you think is wrong with the code?
#     - Is it a logic error? A type mismatch? A missing edge case? An incorrect API call?
#     - Plan a specific change to test your hypothesis.

# 4.  **Test and Iterate:**
#     - You can test your hypothesis without running the full test suite.
#     - For example, use `read_file` to view the logic around a suspected area.
#     - If your hypothesis suggests a simple fix, use `edit_file` to apply the change.
#     - **Do not run `run_tests()` prematurely.** It can be slow and consume resources. It is a last step for verification of a complete fix.

# 5.  **Finalize and Submit:**
#     - Once you have a change that you believe fixes the issue, run `run_tests()`.
#     - If the tests pass, immediately call `get_patch()` and then `final_answer()` with the patch string.
#     - **DO NOT GENERATE CODE THAT IS NOT YOUR OWN.** If you find a solution in a PR or issue, you must use the `edit_file` tool to implement the change yourself, demonstrating exploration and reasoning.

# ---

# ## Response Format

# Your response must be structured as follows. The **Thought** and **Code** sections are required in every iteration.

# ```
# Thought:
# [Your clear, concise reasoning for this step. What do you plan to do and why?]

# Code:
# ```python
# # Your Python code using the available tools.
# # Example:
# result = search_code("validate_email")
# print(result)
# ```
# ```

# **Crucial Rules for the Code Block:**
# - The entire code block must be valid Python code. Everything inside the ````python ... ```` block is what will be executed.
# - **Do not include any commentary outside of the `Thought:` and `Code:` blocks.**
# - **Do not include prompts, additional instructions, or conversational text.**
# - Your final code block must end with a line that provides a useful observation, like printing a variable or the result of a function call. This will be captured and provided back to you as the "Observation".

# ---

# ## Example of a Good Turn

# **Thought:**
# The problem statement mentions an error when parsing dates in `YYYY-MM-DD` format. I will search for the function named `parse_date` to see its implementation, as it is likely the source of the bug.

# **Code:**
# ```python
# definition = search_function_or_class_definition_in_code("parse_date")
# print(definition)
# ```

# ## Task
# ### Problem Statement
# {task.problem_statement}

# ### Hints
# {task.hints_text}

# ### Evaluation Script
# ```python
# {task.eval_script}
# ```
# """


#         return f"""
# # SWE-bench Agent

# You are an expert software engineer. Produce the smallest correct git patch.

# Workflow:
# 1. Read the problem statement, traceback, and failing code.
# 2. Form a concrete hypothesis.
# 3. Make the smallest plausible patch immediately.
# 4. Search elsewhere only if the hypothesis fails.
# 5. Run the provided tests and submit the patch.

# Rules:
# - Keep changes minimal.
# - Strictly one Python code block per response.
# - A plausible hypothesis is sufficient for the first patch.
# - Prefer modifying existing logic over adding new code.
# - Use the traceback and regression test as primary clues.
# - Avoid broad repository exploration.
# - Do not repeat searches or reread unchanged code.

# Each response must contain:

# Thought:
# Observation:
# Hypothesis:
# Next action:

# Code:
# ```python
# # valid Python
# ...

# When the tests pass, call:
# final_answer(get_patch())

# **Tools:**
# {self.mcp_manual}

# **Authorized imports:**
# {self.authorized_imports}

# ---

# ## Task
# ### Problem Statement
# {task.problem_statement}

# ### Hints
# {task.hints_text}

# ### Evaluation Script
# ```python
# {task.eval_script}
# ```
# """
        return f"""
Fix a bug in /testbed. The functions below are PRE-LOADED—call them directly.
Do NOT import the library you are fixing. Do NOT define functions with def.
Always print() the result of every tool call.
Files are in /testbed. Use search_code to find exact paths—do not guess.
The Evaluation Script shows how your fix will be tested. Do NOT run it yourself.

{self.mcp_manual}

Format:
Thought: [reasoning]
Code:
```python
result = tool_name(arg1="val1")
print(result)
```

When tests pass: final_answer(get_patch())

## Task
### Problem Statement
{task.problem_statement}

### Hints
{task.hints_text}

### Evaluation Script
```python
{task.eval_script}
```
"""

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
            if result.error:
                sandbox_output = result.output + '\n' + result.error
            else:
                sandbox_output = result.output
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


if __name__ == '__main__':
    task_data = {
        "instance_id": "django__django-12125",
        "problem_statement": "makemigrations produces incorrect path for inner classes\nDescription\n\t\nWhen you define a subclass from django.db.models.Field as an inner class of some other class, and use this field inside a django.db.models.Model class, then when you run manage.py makemigrations, a migrations file is created which refers to the inner class as if it were a top-level class of the module it is in.\nTo reproduce, create the following as your model:\nclass Outer(object):\n\tclass Inner(models.CharField):\n\t\tpass\nclass A(models.Model):\n\tfield = Outer.Inner(max_length=20)\nAfter running manage.py makemigrations, the generated migrations file contains the following:\nmigrations.CreateModel(\n\tname='A',\n\tfields=[\n\t\t('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),\n\t\t('field', test1.models.Inner(max_length=20)),\n\t],\n),\nNote the test1.models.Inner, which should have been test1.models.Outer.Inner.\nThe real life case involved an EnumField from django-enumfields, defined as an inner class of a Django Model class, similar to this:\nimport enum\nfrom enumfields import Enum, EnumField\nclass Thing(models.Model):\n\t@enum.unique\n\tclass State(Enum):\n\t\ton = 'on'\n\t\toff = 'off'\n\tstate = EnumField(enum=State)\nThis results in the following migrations code:\nmigrations.CreateModel(\n\tname='Thing',\n\tfields=[\n\t\t('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),\n\t\t('state', enumfields.fields.EnumField(enum=test1.models.State, max_length=10)),\n\t],\n),\nThis refers to test1.models.State, instead of to test1.models.Thing.State.\n",
        "docker_image": "swebench/sweb.eval.x86_64.django_1776_django-12125:latest",
        "eval_script": "#!/bin/bash\nset -uxo pipefail\nsource /opt/miniconda3/bin/activate\nconda activate testbed\ncd /testbed\nsed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen\nexport LANG=en_US.UTF-8\nexport LANGUAGE=en_US:en\nexport LC_ALL=en_US.UTF-8\ngit config --global --add safe.directory /testbed\ncd /testbed\ngit status\ngit show\ngit -c core.fileMode=false diff 89d41cba392b759732ba9f1db4ff29ed47da6a56\nsource /opt/miniconda3/bin/activate\nconda activate testbed\npython -m pip install -e .\ngit checkout 89d41cba392b759732ba9f1db4ff29ed47da6a56 tests/migrations/test_writer.py\ngit apply -v - <<'EOF_114329324912'\ndiff --git a/tests/migrations/test_writer.py b/tests/migrations/test_writer.py\n--- a/tests/migrations/test_writer.py\n+++ b/tests/migrations/test_writer.py\n@@ -26,6 +26,11 @@\n from .models import FoodManager, FoodQuerySet\n \n \n+class DeconstructibleInstances:\n+    def deconstruct(self):\n+        return ('DeconstructibleInstances', [], {})\n+\n+\n class Money(decimal.Decimal):\n     def deconstruct(self):\n         return (\n@@ -188,6 +193,10 @@ class NestedEnum(enum.IntEnum):\n         A = 1\n         B = 2\n \n+    class NestedChoices(models.TextChoices):\n+        X = 'X', 'X value'\n+        Y = 'Y', 'Y value'\n+\n     def safe_exec(self, string, value=None):\n         d = {}\n         try:\n@@ -383,6 +392,18 @@ class DateChoices(datetime.date, models.Choices):\n             \"default=datetime.date(1969, 11, 19))\"\n         )\n \n+    def test_serialize_nested_class(self):\n+        for nested_cls in [self.NestedEnum, self.NestedChoices]:\n+            cls_name = nested_cls.__name__\n+            with self.subTest(cls_name):\n+                self.assertSerializedResultEqual(\n+                    nested_cls,\n+                    (\n+                        \"migrations.test_writer.WriterTests.%s\" % cls_name,\n+                        {'import migrations.test_writer'},\n+                    ),\n+                )\n+\n     def test_serialize_uuid(self):\n         self.assertSerializedEqual(uuid.uuid1())\n         self.assertSerializedEqual(uuid.uuid4())\n@@ -726,10 +747,6 @@ def test_deconstruct_class_arguments(self):\n         # Yes, it doesn't make sense to use a class as a default for a\n         # CharField. It does make sense for custom fields though, for example\n         # an enumfield that takes the enum class as an argument.\n-        class DeconstructibleInstances:\n-            def deconstruct(self):\n-                return ('DeconstructibleInstances', [], {})\n-\n         string = MigrationWriter.serialize(models.CharField(default=DeconstructibleInstances))[0]\n         self.assertEqual(string, \"models.CharField(default=migrations.test_writer.DeconstructibleInstances)\")\n \n\nEOF_114329324912\n: '>>>>> Start Test Output'\n./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 migrations.test_writer\n: '>>>>> End Test Output'\ngit checkout 89d41cba392b759732ba9f1db4ff29ed47da6a56 tests/migrations/test_writer.py\n",
        "hints_text": "This should be possible to do by relying on __qualname__ (instead of __name__) now that master is Python 3 only.\n​PR\nI think we should focus on using __qualname__ during migration serialization as well instead of simply solving the field subclasses case.\nIn fb0f987: Fixed #27914 -- Added support for nested classes in Field.deconstruct()/repr().\nIn 451b585: Refs #27914 -- Used qualname in model operations' deconstruct().\nI am still encountering this issue when running makemigrations on models that include a django-enumfields EnumField. From tracing through the code, I believe the Enum is getting serialized using the django.db.migrations.serializer.TypeSerializer, which still uses the __name__ rather than __qualname__. As a result, the Enum's path gets resolved to app_name.models.enum_name and the generated migration file throws an error \"app_name.models has no 'enum_name' member\". The correct path for the inner class should be app_name.models.model_name.enum_name. ​https://github.com/django/django/blob/master/django/db/migrations/serializer.py#L266\nReopening it. Will recheck with nested enum field.\n​PR for fixing enum class as an inner class of model.\nIn d3030dea: Refs #27914 -- Moved test enum.Enum subclasses outside of WriterTests.test_serialize_enums().\nIn 6452112: Refs #27914 -- Fixed serialization of nested enum.Enum classes in migrations.\nIn 1a4db2c: [3.0.x] Refs #27914 -- Moved test enum.Enum subclasses outside of WriterTests.test_serialize_enums(). Backport of d3030deaaa50b7814e34ef1e71f2afaf97c6bec6 from master\nIn 30271a47: [3.0.x] Refs #27914 -- Fixed serialization of nested enum.Enum classes in migrations. Backport of 6452112640081ac8838147a8ba192c45879203d8 from master\ncommit 6452112640081ac8838147a8ba192c45879203d8 does not resolve this ticket. The commit patched the EnumSerializer with __qualname__, which works for Enum members. However, the serializer_factory is returning TypeSerializer for the Enum subclass, which is still using __name__ With v3.0.x introducing models.Choices, models.IntegerChoices, using nested enums will become a common pattern; serializing them properly with __qualname__ seems prudent. Here's a patch for the 3.0rc1 build ​https://github.com/django/django/files/3879265/django_db_migrations_serializer_TypeSerializer.patch.txt\nAgreed, we should fix this.\nI will create a patch a soon as possible.\nSubmitted PR: ​https://github.com/django/django/pull/12125\nPR: ​https://github.com/django/django/pull/12125",
        "repo": "django/django"
        }
    agent = SWEBenchAgent("", "", 2)
    asyncio.run(agent.get_sandbox_manual())
    task = SWEBenchTaskInput.model_validate(task_data)
    agent.handle_task(task)
