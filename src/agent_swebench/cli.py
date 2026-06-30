import json
import sys
from typing import Optional
import fire

from src.agent_mbpp.agent_mbpp import MBPPAgent
from src.agent_mbpp.mbpp_models import MBPPTaskInput


class SWEBenchCli:
    """Command-line interface for SWEBenchCli"""

    def __call__(
        self,
        task_file: str,
        output: str,
        model_name: str,
        provider_url: str,
        max_iterations: Optional[int] = 30
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
            task = MBPPTaskInput.model_validate(task_data)
            agent = MBPPAgent(
                provider_model=model_name, provider_url=provider_url,
                max_iterations=max_iterations)
            solution = agent.solve_task(task)
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
