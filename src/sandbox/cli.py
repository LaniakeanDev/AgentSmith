import fire
from .sandbox_models import SandboxConfig
# from .sandbox_launcher import launch_sandbox
import json
import sys
from .spawner import Spawner
import subprocess

class SandboxCLI:
    """Command-line interface for the sandbox tool"""

    def execute_mcp_stdio(
            self,
            code,
            mcp_command: str,
            config_path=None
            ):
        if code == "":
            print("You did not enter any code for the sandbox")
            sys.exit(0)
        config = get_config(config_path)
        spawner = Spawner(
            config=config, server_path=None, mcp_command=mcp_command)
        # sandbox.configure()
        exec_through_sandbox(spawner=spawner, code=code)

    def execute(
            self, code,
            config_path=None,
            server_path='src/fastmcp_server.py'):
        """Execute code in the sandbox"""
        if code == "":
            print("You did not enter any code for the sandbox")
            sys.exit(0)
        config = get_config(config_path)
        spawner = Spawner(config=config, server_path=server_path)
        # sandbox.configure()
        exec_through_sandbox(spawner=spawner, code=code)


def build_image() -> None:
    build_result = subprocess.run([
        "docker", "build",
        "--network=host",
        "-t", "sandbox-image",
        "./src/sandbox"
    ], capture_output=True, text=True)
    if build_result.returncode != 0:
        raise RuntimeError(f"Build failed: {build_result.stderr}")
    print(f"Image built: sandbox-image")


def exec_through_sandbox(spawner: Spawner, code: str):
    docker_cmd = [
        "docker", "run",
        "--rm",
        "--network=none",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        f"--memory={spawner.config.max_memory_mb}m",
        "--cpus=1",
        "-i",
        "sandbox-image",
        "uv", "run", "python", "-m", "sandbox"
    ]
    print("Building image...")
    build_image()
    print("Image built")
    result = spawner.spawn(code, docker_cmd)
    if result.success:
        print("\n\nYour result:")
        print("-" * 12)
        print(result.output)
    else:
        print(f'error: {result.error}')


def get_config(config_path: str | None) -> SandboxConfig:
    if config_path is None:
        config = SandboxConfig()
    else:
        try:
            with open(config_path, 'r') as f:
                data = json.loads(f.read())
                config = SandboxConfig.model_validate(data)
        except Exception as e:
            print(f"\n\nWARNING: {type(e).__name__}: {str(e)}")
            print("Using default configuration instead\n\n")
            config = SandboxConfig()
    return config


def handle_input(
        config_path: str | None = None,
        mcp_command: str | None = None):
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
    if mcp_command:
        cli.execute_mcp_stdio(
            code=code, config_path=config_path, mcp_command=mcp_command)
    else:
        cli.execute(code=code, config_path=config_path)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--mcp-stdio':
        if len(sys.argv) < 3:
            print("Error: --mcp-stdio requires a command")
            sys.exit(1)

        mcp_command = sys.argv[2]
        config_path = sys.argv[3] if len(sys.argv) > 3 else None
        handle_input(config_path=config_path, mcp_command=mcp_command)

    elif len(sys.argv) == 1:
        if sys.argv[0].split('/').pop() != 'sandbox':
            print(f"Invalid command: {sys.argv[0]}")
            sys.exit(1)
        handle_input(None)

    elif len(sys.argv) == 2:
        if sys.argv[0].split('/').pop() != 'sandbox':
            fire.Fire(SandboxCLI)
            return
        config_path = sys.argv[1]
        handle_input(config_path)

    else:
        fire.Fire(SandboxCLI)


if __name__ == "__main__":
    main()
