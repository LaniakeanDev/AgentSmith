import fire
from .config import SandboxConfig
from .sandbox_launcher import launch_sandbox
import json
import sys


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
    if len(sys.argv) == 1:
        print("Enter your code below to have it executed in the sandbox")
        print("Press Ctrl+D when done")
        print("-" * 50)
        lines = []
        try:
            while True:
                try:
                    line = input()
                    lines.append(line)
                except EOFError:
                    break
        except KeyboardInterrupt:
            print("\nExiting...")
            return
        if not lines:
            print("No code entered. Exiting.")
            return
        code = '\n'.join(lines)
        print("\n" + "=" * 50)
        print(" " * 18 + "Executing code...")
        print("=" * 50)
        cli = SandboxCLI()
        cli.execute(code)
    else:
        fire.Fire(SandboxCLI)


if __name__ == "__main__":
    main()
