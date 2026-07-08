import subprocess
import sys
import re
import time
from typing import List
from abstract_agent import AbstractAgent
from sandbox.spawner import Spawner
from models import CallMetrics
from sandbox.mcp_client import MCPClient
from sandbox.sandbox_models import ExecutionResult, SandboxConfig
from .swebench_models import StepMetrics, SWEBenchTaskInput, SolutionOutput
from llm_caller import LLMCaller


class SWEBenchAgent(AbstractAgent):
    def __init__(
            self,
            provider_model: str,
            provider_url: str,
            max_iterations: int,
            config: SandboxConfig,
            task: SWEBenchTaskInput,
            mcp_command: str | None = None):
        super().__init__(provider_model, provider_url, max_iterations)
        self.task = task
        self.mcp_manual: str | None = None
        self.authorized_imports = ""
        self.config = config
        self.og_prompt = ""
        self.prompt_ext = ""
        self.image_name: str | None = None
        self.container_name: str | None = None
        self.iteration = 0
        if mcp_command is None:
            self.mcp_command = "uv run python sandbox/swebench_server.py"
        else:
            self.mcp_command = mcp_command
        self.spawner = Spawner(
            config=config,
            task=task,
            mcp_command=self.mcp_command
        )
        self.all_tests_passed = False
        self.caller = LLMCaller(
            provider="groq",
            max_retries_per_key=3
            )

    async def get_sandbox_manual(self):
        await self.get_mcp_manual()
        authorized_imports = self.config.authorized_imports
        for item in authorized_imports:
            self.authorized_imports += f"{item}, "
        self.authorized_imports = self.authorized_imports[:-2]

    async def get_mcp_manual(self):
        client = MCPClient(self.mcp_command, "")
        try:
            await client.connect_server()
        except Exception as e:
            print(e)
            sys.exit(1)
        await client.get_tools()
        self.mcp_manual = client.generate_sandbox_manual()
        # print(f"Manual retrieved:\n{manual}")
        await client.cleanup()

    def extract_code(self, llm_output: str) -> str | None:
        pattern = r'```python\n(.*?)```'
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            code = match.group(1)
            code = self.sanitize_code(code)
            return code
        else:
            return None

    def build_image(self) -> None:
        print("building Image...")
        base_image = self.task.docker_image
        if not base_image.startswith(("docker.io/", "quay.io/", "ghcr.io/", "gcr.io/")):
            base_image = f"docker.io/{base_image}"
        self.image_name = f"swebench_{self.task.instance_id}_{int(time.time())}"
        self.container_name = f"{self.image_name}_container"
        build_result = subprocess.run([
            "docker", "build",
            "--build-arg", f"BASE_IMAGE={base_image}",
            "--network=host",
            "-t", self.image_name,
            "-f", "./src/sandbox/Dockerfile.swebench",
            "./src/sandbox"
        ], capture_output=True, text=True)
        if build_result.returncode != 0:
            raise RuntimeError(f"Build failed: {build_result.stderr}")
        print(f"Image built: {self.image_name}")

    def start_container(self):
        docker_cmd = [
            "docker", "run", "-d",  # detached, long-lived
            "--name", self.container_name,
            "--network=none", "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            f"--memory={self.config.max_memory_mb}m", "--cpus=1",
            self.image_name,
            "sleep", "infinity"
        ]
        subprocess.run(docker_cmd, check=True)

    def stop_container(self) -> None:
        if self.container_name:
            subprocess.run(["docker", "rm", "-f", self.container_name],
                           capture_output=True, text=True)
        if self.image_name:
            subprocess.run(["docker", "rmi", "-f", self.image_name],
                           capture_output=True, text=True)

    def no_extracted_code_retry(self, prompt: str, llm_output: str) -> str:
        message = "No code block was detected in your previous response"
        prompt = self.get_new_prompt(
            prompt=prompt,
            code="No code could be extracted",
            iteration=self.iteration,
            message=message,
            llm_output=llm_output
            )
        self.iteration += 1
        print(f"\n\nIteration {self.iteration}")
        # print(f"prompt: {prompt}")
        # print(f"Calling {self.provider}...")
        call_metrics = self.caller.call_llm(prompt)
        print("Response received")
        llm_output = call_metrics.llm_output.strip()
        print(f"llm_output:\n{llm_output}\n")
        extracted_code = self.extract_code(llm_output)
        print(f"extracted_code:\n{extracted_code}")
        return extracted_code

    def sandbox_exec(
            self,
            extracted_code: str
            ) -> ExecutionResult:
        print("DEBUG: sandbox_exec called")
        exec_cmd = [
            "docker", "exec", "-i", self.container_name, "python",
            "-m", "sandbox"]
        return self.spawner.spawn(
            code=extracted_code,
            docker_cmd=exec_cmd,
        )

    def handle_task(self):
        print("DEBUG: handle_task launched")
        self.step_metrics_list: List[StepMetrics] = []
        self.task_start = time.time()
        prompt = self.get_prompt()
        # print(f"\n\nprompt:\n\n{prompt}\n\n")
        # sys.exit(0)
        print("\n\nIteration 1")
        # print(f"Calling {self.provider}...")
        call_metrics = self.caller.call_llm(prompt)
        print("Response received")
        llm_output = call_metrics.llm_output.strip()
        print(f"\n\nllm_output:\n{llm_output}\n")
        extracted_code = self.extract_code(llm_output)
        print(f"extracted_code:\n{extracted_code}")
        self.iteration = 1
        while extracted_code is None and \
                self.iteration < self.max_iterations:
            extracted_code = self.no_extracted_code_retry(
                prompt, llm_output)
        if extracted_code is None:
            task_duration = time.time() - self.task_start
            return SolutionOutput(
                task_id=str(self.task.instance_id),
                benchmark="swebench",
                success=False,
                solution="Maximum number of iterations hit, no extracted code",
                system_prompt=prompt,
                iterations=self.iteration,
                total_requests=sum(
                    met.retries + 1 for met in self.step_metrics_list),
                total_input_tokens=sum(
                    met.input_tokens for met in self.step_metrics_list),
                total_output_tokens=sum(
                    met.output_tokens for met in self.step_metrics_list),
                total_time_seconds=task_duration,
                steps=self.step_metrics_list,
                error="No extracted code"
            )
        try:
            self.build_image()
            self.start_container()
        except Exception as e:
            print(f"Agent: {type(e).__name__}: {str(e)}")
            sys.exit(1)
        try:
            print("Executing in sandbox...")
            result = self.sandbox_exec(extracted_code)
            if "'all_tests_passed': True" in result.output:
                self.all_tests_passed = True
            print(f"\nresult_{self.iteration}:")
            # import pprint
            # pprint.pprint(result)
            step_metrics = self.get_step_metrics(
                code=extracted_code,
                result=result,
                call_metrics=call_metrics,
                iteration=self.iteration
            )
            self.step_metrics_list.append(step_metrics)
            while result.final_answer is None and \
                    self.iteration < self.max_iterations:
                exec_output = result.output
                if result.success:
                    message = f"Execution completed:"\
                            f"{exec_output}"
                else:
                    message = f"Execution could not complete:\n{result.error}"
                print(message)
                prompt = self.get_new_prompt(
                    prompt=prompt,
                    code=extracted_code,
                    iteration=self.iteration,
                    message=message,
                    llm_output=llm_output
                    )
                self.iteration += 1
                print(f"\n\nIteration {self.iteration}")
                # print(f"prompt: {prompt}")
                # print(f"Calling {self.provider}...")
                call_metrics = self.caller.call_llm(prompt)
                print("Response received")
                llm_output = call_metrics.llm_output.strip()
                print(f"llm_output:\n{llm_output}\n")
                extracted_code = self.extract_code(llm_output)
                print(f"extracted_code:\n{extracted_code}")
                while extracted_code is None and \
                        self.iteration < self.max_iterations:
                    extracted_code = self.no_extracted_code_retry(
                        prompt, llm_output)
                if extracted_code is None:
                    task_duration = time.time() - self.task_start
                    return SolutionOutput(
                        task_id=str(self.task.instance_id),
                        benchmark="swebench",
                        success=False,
                        solution="Maximum number of iterations hit, no extracted \
                            code",
                        system_prompt=prompt,
                        iterations=self.iteration,
                        total_requests=sum(
                            met.retries + 1 for met in self.step_metrics_list),
                        total_input_tokens=sum(
                            met.input_tokens for met in self.step_metrics_list),
                        total_output_tokens=sum(
                            met.output_tokens for met in self.step_metrics_list),
                        total_time_seconds=task_duration,
                        steps=self.step_metrics_list,
                        error="No extracted code"
                    )
                print("Executing in sandbox...")
                result = self.sandbox_exec(extracted_code)
                if "'all_tests_passed': True" in result.output:
                    self.all_tests_passed = True
                    self.all_tests_passed_iteration = self.iteration
                # print(f"result_{self.iteration}:\n{result}")
                # result, code = self.sandbox_exec(
                #     llm_output=llm_output, test_list=task.test_list)
                step_metrics = self.get_step_metrics(
                    code=extracted_code,
                    result=result,
                    call_metrics=call_metrics,
                    iteration=self.iteration
                )
                self.step_metrics_list.append(step_metrics)
            task_duration = time.time() - self.task_start
            # subprocess.run(
            #     ["docker", "rm", "-f", self.container_name],
            #     capture_output=True, text=True)
            if not result.final_answer or not self.all_tests_passed:
                print("Could not solve this problem")
                return SolutionOutput(
                    task_id=str(self.task.instance_id),
                    benchmark="swebench",
                    success=False,
                    solution="Solution not found",
                    system_prompt=prompt,
                    iterations=self.iteration,
                    total_requests=sum(
                        met.retries + 1 for met in self.step_metrics_list),
                    total_input_tokens=sum(
                        met.input_tokens for met in self.step_metrics_list),
                    total_output_tokens=sum(
                        met.output_tokens for met in self.step_metrics_list),
                    total_time_seconds=task_duration,
                    steps=self.step_metrics_list,
                    error=result.error
                )
            else:
                print("\nProblem solved! The solution is:\n")
                print(result.final_answer)
                print(result.output)
                return SolutionOutput(
                    task_id=str(self.task.instance_id),
                    benchmark="swebench",
                    success=True,
                    solution=result.final_answer,
                    system_prompt=prompt,
                    iterations=self.iteration,
                    total_requests=sum(
                        met.retries + 1 for met in self.step_metrics_list),
                    total_input_tokens=sum(
                        met.input_tokens for met in self.step_metrics_list),
                    total_output_tokens=sum(
                        met.output_tokens for met in self.step_metrics_list),
                    total_time_seconds=task_duration,
                    steps=self.step_metrics_list,
                )
        finally:
            self.stop_container()

    def get_prompt(self):
        return f"""
Fix a bug in /testbed. The functions below are PRE-LOADED—call them directly.
Do NOT import the library you are fixing. Do NOT define functions with def.
Files are in /testbed. Use search_code to find exact paths—do not guess.
The Evaluation Script shows how your fix will be tested. Do NOT run it yourself.
When using edit_file, match the exact indentation of old_str in new_str.
When editing, include enough context in old_str to match only ONE location.
Once print(run_tests()) indicates success, call final_answer(get_patch()) immediately.
Check for commented-out fixes in the traceback.
Output only one code block per response.
Never write edit_file, run_tests, or final_answer calls based on an assumed
or guessed prior result. Only reference a file's exact content, path, or line
number after you have seen it in a tool's actual printed output in a previous
turn. Submit one tool call's result before writing code that depends on it.
final_answer(get_patch()) is only valid immediately after run_tests() has
printed "all_tests_passed": True in this same session — never call it otherwise.

{self.mcp_manual}

Format:
Thought: [reasoning]
Code:
```python
result = tool_name(arg1="val1")
print(result)
```

After verifying your solution (next iteration):
final_answer(patch) must be called alone

## Task
### Problem Statement
{self.task.problem_statement}

### Hints
{self.task.hints_text}

### Evaluation Script
```python
{self.task.eval_script}
```
"""

    def get_step_metrics(
            self,
            result: ExecutionResult,
            code: str,
            call_metrics: CallMetrics,
            iteration: int
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
            step=iteration,
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
