import json
import subprocess
import sys
from typing import List
from agent_mbpp.mbpp_models import (
    MBPPTaskInput, SolutionOutput, StepMetrics)
from sandbox.constants import DEFAULT_SERVER_NAME_MBPP
from src.abstract_agent import AbstractAgent
from src.llm_caller import LLMCaller
from ..models import CallMetrics
import time
from sandbox.sandbox_models import ExecutionResult, SandboxConfig
from sandbox.spawner import Spawner


class MBPPAgent(AbstractAgent):
    def __init__(
            self,
            task_type: str,
            provider_model: str,
            provider_url: str,
            max_iterations: int,
            config: SandboxConfig,
            task: MBPPTaskInput,
            mcp_command: str | None = None) -> None:
        super().__init__(
            task_type, provider_model, provider_url, max_iterations)
        self.task = task
        self.mcp_manual: str | None = None
        self.authorized_imports = ""
        self.config = config
        self.og_prompt = ""
        self.prompt_ext = ""
        self.image_name = "sandbox-image"
        self.container_name = f"{self.image_name}_container"
        self.remove_image()
        self.iteration = 0
        if mcp_command is None:
            self.mcp_command = DEFAULT_SERVER_NAME_MBPP
        else:
            self.mcp_command = mcp_command
        self.spawner = Spawner(
            config=config,
            task=task,
            mcp_command=self.mcp_command
        )
        self.all_tests_passed = False
        self.solution = ""
        self.caller = LLMCaller(
            provider="groq",
            max_retries_per_key=3
            )

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

    def image_exists(self):
        try:
            subprocess.run(
                ['docker', 'image', 'inspect', self.image_name],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def build_image(self) -> None:
        if not self.image_exists():
            print("building Image...")
            build_result = subprocess.run([
                "docker", "build",
                "--network=host",
                "-t", self.image_name,
                "-f", "./src/sandbox/Dockerfile.mbpp",
                "./src/sandbox"
            ], capture_output=True, text=True)
            if build_result.returncode != 0:
                raise RuntimeError(f"Build failed: {build_result.stderr}")
            print(f"Image built: {self.image_name}")
        else:
            print(f"Using pre-built image: {self.image_name}")

    def container_exists(self):
        try:
            subprocess.run(
                ['docker', 'container', 'inspect', self.container_name],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def container_is_running(self):
        check_cmd = [
            "docker", "inspect", "-f",
            "{{.State.Status}}", self.container_name
            ]
        try:
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            status = result.stdout.strip()
            return status == "running"
        except Exception as e:
            print(f"Container check failed: {e}")
            raise
            # Create/start container here if needed

    def start_container(self):
        # if not self.container_exists() or not self.container_is_running():
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
        # else:
        #     print(f"Using pre-built container: {self.image_name}")

    def remove_image(self) -> None:
        # print("Stopping container...")
        # if self.container_name:
        #     subprocess.run(["docker", "rm", "-f", self.container_name],
        #                    capture_output=True, text=True)
        print("Removing image...")
        if self.image_name:
            subprocess.run(["docker", "rmi", "-f", self.image_name],
                           capture_output=True, text=True)

    def sandbox_exec(
            self,
            extracted_code: str
            ) -> ExecutionResult:
        exec_cmd = [
            "docker", "exec", "-i", self.container_name, "python",
            "-m", "sandbox"]
        try:
            return self.spawner.spawn(
                code=extracted_code,
                docker_cmd=exec_cmd,
            )
        except Exception as e:
            print(f"Agent.sandbox_exec: {type(e).__name__}: {str(e)}")
            raise

    def get_prompt(self):
        prompt = f"# MCP manual\n{self.mcp_manual}\n"
        prompt += "### final_answer(function_definition: str)\n"
        prompt += "Submits the function's python code as a string\n"
        prompt += "Once print(run_tests()) indicates success, "
        prompt += "call final_answer('function_definition') "
        prompt += "on the next iteration.\n"
        prompt += "\n# Task definition\n"
        prompt += self.task.task_definition
        prompt += "\n# Function definition\n"
        prompt += self.task.function_definition
        prompt += "\n\n# Guideline"
        prompt += "\nReply with nothing but the code starting by '```python':"
        return prompt

    def get_new_prompt(
            self, prompt: str, code: str, exec_output: str,
            iteration_count: int, message: str):
        new_prompt = f"{prompt}\n\nIteration {iteration_count}:\ncode: {code}"
        new_prompt += '\n' + message + '\n'
        # new_prompt += f"execution output: {exec_output}\n"
        new_prompt += "Make the next iteration"
        return new_prompt

    def add_tests(self, code: str) -> str:
        if not self.all_tests_passed and 'run_tests()' not in code:
            return f"{code}\nrun_tests()"
        return code

    def solve_task(self) -> SolutionOutput:
        try:
            self.build_image()
            self.start_container()
        except Exception as e:
            print(f"Agent: {type(e).__name__}: {str(e)}")
            sys.exit(1)
        step_metrics_list: List[StepMetrics] = []
        task_start = time.time()
        prompt = self.get_prompt()
        # print(prompt)
        # sys.exit(0)
        self.iteration += 1
        print("\nIteration 1")
        call_metrics = self.caller.call_llm(prompt)
        print("Response received")
        llm_output = call_metrics.llm_output.strip()
        # print(f"\nllm_output:\n{llm_output}\n")
        extracted_code, _ = self.extract_code(llm_output)
        print(f"extracted_code:\n{extracted_code}")
        while extracted_code is None and \
                self.iteration < self.max_iterations:
            extracted_code = self.no_extr_code_retry(
                prompt, llm_output)
        if extracted_code is None:
            task_duration = time.time() - self.task_start
            return SolutionOutput(
                task_id=str(self.task.instance_id),
                benchmark="mbpp",
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
        code = self.add_tests(extracted_code)
        print(f"\ncode:\n{code}\n")
        try:
            print("Executing in sandbox...")
            result = self.sandbox_exec(code)
            step_metrics = self.get_step_metrics(
                code=extracted_code,
                result=result,
                call_metrics=call_metrics,
                iteration_count=self.iteration
            )
            step_metrics_list.append(step_metrics)
            print(f"\nresult:\n{str(result)}\n\n")
            # sys.exit(0)
            while result.final_answer is None and \
                    self.iteration < self.max_iterations:
                exec_output = result.output
                if not self.all_tests_passed:
                    output_data = json.loads(exec_output)
                    if result.success and output_data['success']:
                        message = "Ran run_tests() and got the results:\n"
                        message += str(output_data)
                        message += "\nIt's time to call final_answer()\n"
                        self.all_tests_passed = True
                    else:
                        message = f"\nExecution could not complete:\n{result.error}"
                # print(message)
                # sys.exit(0)
                else:
                    message = "All tests have passed."
                    message += "\nIt's time to call final_answer()\n"
                print("making new prompt...")
                prompt = self.get_new_prompt(
                    prompt=prompt,
                    code=code,
                    exec_output=exec_output,
                    iteration_count=self.iteration,
                    message=message
                    )
                # print(prompt)
                # sys.exit(0)
                print("new prompt made")
                self.iteration += 1
                print(f"\nIteration {self.iteration}")
                call_metrics = self.caller.call_llm(prompt)
                print("Response received")
                llm_output = call_metrics.llm_output.strip()
                print(f"\nllm_output:\n{llm_output}\n")
                extracted_code, _ = self.extract_code(llm_output)
                while extracted_code is None and \
                        self.iteration < self.max_iterations:
                    extracted_code = self.no_extr_code_retry(
                        prompt, llm_output)
                if extracted_code is None:
                    task_duration = time.time() - self.task_start
                    return SolutionOutput(
                        task_id=str(self.task.instance_id),
                        benchmark="mbpp",
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
                code = self.add_tests(extracted_code)
                print(f"\ncode:\n{code}\n")
                result = self.sandbox_exec(code)
                print(f"\nresult:\n{str(result)}\n\n")
                step_metrics = self.get_step_metrics(
                    code=code,
                    result=result,
                    call_metrics=call_metrics,
                    iteration_count=self.iteration
                )
                step_metrics_list.append(step_metrics)
            task_duration = time.time() - task_start
            print()
            if not result.final_answer:
                print("Could not solve this problem")
                return SolutionOutput(
                    task_id=str(self.task.task_id),
                    benchmark="mbpp",
                    success=False,
                    solution="Solution not found",
                    system_prompt=prompt,
                    iterations=self.iteration,
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
                    task_id=str(self.task.task_id),
                    benchmark="mbpp",
                    success=True,
                    solution=result.final_answer,
                    system_prompt=prompt,
                    iterations=self.iteration,
                    total_requests=sum(
                        met.retries + 1 for met in step_metrics_list),
                    total_input_tokens=sum(
                        met.input_tokens for met in step_metrics_list),
                    total_output_tokens=sum(
                        met.output_tokens for met in step_metrics_list),
                    total_time_seconds=task_duration,
                    steps=step_metrics_list,
                )
        except Exception as e:
            print(f"Agent: {type(e).__name__}: {str(e)}")
        finally:
            self.remove_image()

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
            sandbox_output = result.output + '\n'
            if result.error is not None:
                sandbox_output += result.error
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
