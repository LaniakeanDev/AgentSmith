import fire
from .config import SandboxConfig
from .sandbox_launcher import launch_sandbox
import json


class SandboxCLI:
    """Command-line interface for the sandbox tool"""

    def execute(self, code, config_file=None):
        """Execute code in the sandbox"""
        if config_file is None:
            config = SandboxConfig()
        else:
            try:
                with open(config_file, 'r') as f:
                    data = json.loads(f.read())
                    config = SandboxConfig.model_validate(data)
            except Exception as e:
                print(f"WARNING: {e}")
                config = SandboxConfig()
        result = launch_sandbox(config, code)
        stdout = result["stdout"]
        if stdout:
            print(f'stdout: {stdout}')
        stderr = result["stderr"]
        if stderr:
            print(f'stderr: {stderr}')


def main():
    fire.Fire(SandboxCLI)


if __name__ == "__main__":
    main()
