import asyncio
import json
import sys
from typing import Optional
from agent_swebench.agent_swebench import SWEBenchAgent
import fire
from sandbox.sandbox_models import SandboxConfig
from .swebench_models import SWEBenchTaskInput


class SWEBenchCli:
    """Command-line interface for SWEBenchCli"""

    def __call__(
        self,
        task_file: str,
        output: str,
        model_name: str,
        provider_url: str,
        # max_iterations: Optional[int] = 30,
        max_iterations: Optional[int] = 10,
        config: Optional[SandboxConfig] = SandboxConfig()
    ):
        """
        Run SWEBench agent on a given task.

        Args:
            task_file: Path to the MBPP task JSON file
            output: Path where solution output will be saved
            model_name: Name of the model to use (e.g., "openai/gpt-4")
            provider_url: API endpoint URL (e.g., "https://openrter.ai/api/v1")
        """
        try:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
            task = SWEBenchTaskInput.model_validate(task_data)
            agent = SWEBenchAgent(
                provider_model=model_name, provider_url=provider_url,
                max_iterations=max_iterations, config=config)
            print("agent created")
            asyncio.run(
                agent.get_sandbox_manual()
            )
            print("about to ask for solution")
            solution = agent.handle_task(task)
            with open(output, 'w') as f:
                f.write(solution.model_dump_json(indent=2))
        except Exception as e:
            print(f"CLI: {type(e).__name__}: {str(e)}")
            sys.exit(1)
        print(f"Solution saved to {output}")


def main():
    fire.Fire(SWEBenchCli)


if __name__ == "__main__":
    main()
