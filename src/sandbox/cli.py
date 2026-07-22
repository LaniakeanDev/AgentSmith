#!/usr/bin/env python3
"""
Sandbox CLI - A secure code execution environment with Docker isolation.
"""

import json
import sys
import subprocess
from typing import Optional, NoReturn
from dataclasses import dataclass

import fire

from .sandbox_models import SandboxConfig
from .spawner import Spawner


# ============================================================================
# Exceptions
# ============================================================================

class SandboxError(Exception):
    """Base exception for sandbox-related errors."""
    pass


class BuildError(SandboxError):
    """Raised when Docker image build fails."""
    pass


class CodeExecutionError(SandboxError):
    """Raised when code execution fails."""
    pass


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class SandboxPaths:
    """Container for file system paths used by the sandbox."""
    server_path: str = 'src/default_server.py'
    dockerfile_dir: str = './src/sandbox'
    image_name: str = 'sandbox-image'
    sandbox_module: str = 'sandbox'


# ============================================================================
# Docker Image Builder
# ============================================================================

class ImageBuilder:
    """Handles building the Docker image for the sandbox."""

    def __init__(self, paths: SandboxPaths):
        self.paths = paths

    def build(self) -> None:
        """Build the Docker image."""
        try:
            result = subprocess.run([
                "docker", "build",
                "--network=host",
                "-t", self.paths.image_name,
                self.paths.dockerfile_dir
            ], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise BuildError(f"Build failed: {result.stderr}")
            print(f"✓ Image built: {self.paths.image_name}")
        except FileNotFoundError:
            raise BuildError("Docker not found. Please ensure Docker is installed and in your PATH.")
        except Exception as e:
            raise BuildError(f"Unexpected error during build: {e}")


# ============================================================================
# Configuration Loader
# ============================================================================

class ConfigLoader:
    """Loads and validates sandbox configuration."""

    @staticmethod
    def load(config_path: Optional[str] = None) -> SandboxConfig:
        """
        Load configuration from file or create default.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            SandboxConfig instance
        """
        if config_path is None:
            return SandboxConfig()
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return SandboxConfig.model_validate(data)
        except FileNotFoundError:
            print(f"\n⚠️  Configuration file not found: {config_path}")
            print("Using default configuration\n")
            return SandboxConfig()
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\n⚠️  Invalid configuration: {e}")
            print("Using default configuration\n")
            return SandboxConfig()
        except Exception as e:
            print(f"\n⚠️  Unexpected error loading config: {e}")
            print("Using default configuration\n")
            return SandboxConfig()


# ============================================================================
# Code Executor
# ============================================================================

class CodeExecutor:
    """Executes code in the sandbox environment."""

    def __init__(self, spawner: Spawner, builder: ImageBuilder):
        self.spawner = spawner
        self.builder = builder

    def execute(self, code: str) -> None:
        """
        Execute code in the sandbox.

        Args:
            code: Python code to execute

        Raises:
            CodeExecutionError: If execution fails
        """
        if not code or not code.strip():
            print("No code to execute.")
            return
        # Build the Docker image
        print("🔨 Building Docker image...")
        self.builder.build()
        print("✓ Image ready\n")
        # Prepare Docker command
        docker_cmd = [
            "docker", "run",
            "--rm",
            "--network=none",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            f"--memory={self.spawner.config.max_memory_mb}m",
            "--cpus=1",
            "-i",
            self.builder.paths.image_name,
            "uv", "run", "python", "-m", self.builder.paths.sandbox_module
        ]
        # Execute
        result = self.spawner.spawn(code, docker_cmd)
        # Display result
        self._display_result(result)
        if not result.success:
            raise CodeExecutionError(f"Execution failed: {result.error}")

    @staticmethod
    def _display_result(result) -> None:
        """Display execution result."""
        if result.success:
            print("\n📤 Result:")
            print("-" * 40)
            print(result.output)
        else:
            print(f"\n❌ Error: {result.error}")


# ============================================================================
# Interactive REPL
# ============================================================================

class SandboxREPL:
    """Interactive REPL for sandbox code execution."""

    def __init__(self, executor: CodeExecutor):
        self.executor = executor
        self.running = True

    def run(self) -> None:
        """Run the interactive REPL."""
        print("\n" + "=" * 60)
        print("🐚  Sandbox REPL")
        print("=" * 60)
        print("Type Python code to execute in the sandbox.")
        print("Enter 'exit' or press Ctrl+D to quit.")
        print("-" * 60)
        while self.running:
            try:
                code = self._read_code()
                if code is None:
                    break
                if self._should_exit(code):
                    break
                self._execute_code(code)
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'exit' or press Ctrl+D to quit.")
                continue
            except EOFError:
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
        print("\n👋 Goodbye!")

    def _read_code(self) -> Optional[str]:
        """Read code from user input."""
        print("\n>>> ", end="", flush=True)
        lines = []
        try:
            while True:
                line = input()
                if line.strip() == "":
                    # Empty line might be part of multi-line input
                    if lines and not lines[-1].strip().endswith((':', '(', '[', '{')):
                        # Treat as submission if not in multi-line mode
                        break
                lines.append(line)
        except EOFError:
            return None
        return '\n'.join(lines)

    def _should_exit(self, code: str) -> bool:
        """Check if code indicates exit."""
        return code.strip().lower() in ('exit', 'quit', 'exit()', 'quit()')

    def _execute_code(self, code: str) -> None:
        """Execute a single code block."""
        print("\n" + "=" * 60)
        print("Executing code...")
        print("=" * 60)
        self.executor.execute(code)


# ============================================================================
# Main CLI
# ============================================================================

class SandboxCLI:
    """
    Command-line interface for the sandbox tool.

    Examples:
        # Interactive REPL
        sandbox

        # Start REPL with config
        sandbox sandbox_template.json

        # Execute single code block
        sandbox execute "print('Hello World')"

        # Execute with custom config
        sandbox execute --config_path=config.json "print('Hello')"

        # MCP stdio mode
        sandbox --mcp-stdio "python -m mcp_server" "print('test')"
    """

    def __init__(self):
        self.paths = SandboxPaths()
        self.builder = ImageBuilder(self.paths)

    def execute(self, code: str, config_path: Optional[str] = None) -> None:
        """
        Execute code in the sandbox.

        Args:
            code: Python code to execute
            config_path: Path to configuration file (optional)
        """
        if not code or not code.strip():
            print("❌ Error: No code provided for execution")
            sys.exit(1)
        config = ConfigLoader.load(config_path)
        spawner = Spawner(config=config, server_path=self.paths.server_path)
        executor = CodeExecutor(spawner, self.builder)
        try:
            executor.execute(code)
        except (BuildError, CodeExecutionError) as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    def execute_mcp_stdio(
        self,
        code: str,
        mcp_command: str,
        config_path: Optional[str] = None
    ) -> None:
        """
        Execute code with MCP stdio server.

        Args:
            code: Python code to execute
            mcp_command: MCP server command
            config_path: Path to configuration file (optional)
        """
        if not code or not code.strip():
            print("❌ Error: No code provided for execution")
            sys.exit(1)
        # Sanitize MCP command path
        split_cmd = mcp_command.split(' ')
        if len(split_cmd) > 1:
            split_cmd[1] = f'sandbox/{split_cmd[1]}'
            mcp_command = ' '.join(split_cmd)
        config = ConfigLoader.load(config_path)
        spawner = Spawner(
            config=config,
            server_path=None,
            mcp_command=mcp_command
        )
        executor = CodeExecutor(spawner, self.builder)
        try:
            executor.execute(code)
        except (BuildError, CodeExecutionError) as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    def repl(self, config_path: Optional[str] = None) -> None:
        """Start the interactive REPL."""
        config = ConfigLoader.load(config_path)
        spawner = Spawner(config=config, server_path=self.paths.server_path)
        executor = CodeExecutor(spawner, self.builder)
        repl = SandboxREPL(executor)
        repl.run()

    def execute_mcp_http(
        self,
        code: str,
        mcp_url: str,
        config_path: Optional[str] = None
    ) -> None:
        """
        Execute code with MCP HTTP server.

        Args:
            code: Python code to execute
            mcp_url: MCP server URL (e.g., http://localhost:8000)
            config_path: Path to configuration file (optional)
        """
        print("execute_mcp_http")
        if not code or not code.strip():
            print("❌ Error: No code provided for execution")
            sys.exit(1)
        # Validate URL format
        if not mcp_url.startswith(('http://', 'https://')):
            print(f"❌ Error: Invalid MCP URL format: {mcp_url}")
            print("URL should start with http:// or https://")
            sys.exit(1)
        # Remove trailing slash if present
        if mcp_url.endswith('/'):
            mcp_url = mcp_url[:-1]
        config = ConfigLoader.load(config_path)
        config.transport = 'http'
        config.mcp_url = mcp_url
        # Create spawner with HTTP MCP server
        # You'll need to modify Spawner to accept mcp_url as well
        spawner = Spawner(
            config=config,
            server_path=None,
            mcp_command=None
        )
        executor = CodeExecutor(spawner, self.builder)
        try:
            executor.execute(code)
        except (BuildError, CodeExecutionError) as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

# ============================================================================
# CLI Entry Points
# ============================================================================


def handle_input(
    config_path: Optional[str] = None,
    mcp_command: Optional[str] = None,
    mcp_url: Optional[str] = None
) -> None:
    """Handle interactive input mode."""
    print(f"handle input: mcp_url={mcp_url}")
    cli = SandboxCLI()
    if mcp_command or mcp_url:
        print("📝 Enter your code below (press Ctrl+D when done):")
        code = _read_multiline_input()
        if code and mcp_url is None:
            cli.execute_mcp_stdio(
                code=code, mcp_command=mcp_command, config_path=config_path)
        elif code:
            cli.execute_mcp_http(
                code=code, mcp_url=mcp_url, config_path=config_path)
    else:
        cli.repl(config_path)


def _read_multiline_input() -> Optional[str]:
    """Read multiline input from stdin."""
    lines = []
    try:
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
    except KeyboardInterrupt:
        print("\n⚠️  Input cancelled.")
        return None
    if not lines:
        print("No code entered.")
        return None
    return '\n'.join(lines)


def main() -> NoReturn:
    """Main entry point."""
    try:
        # Check for MCP stdio mode
        if len(sys.argv) >= 2 and sys.argv[1] == '--mcp-stdio':
            if len(sys.argv) < 3:
                print("❌ Error: --mcp-stdio requires a command")
                sys.exit(1)
            mcp_command = sys.argv[2]
            config_path = sys.argv[3] if len(sys.argv) > 3 else None
            handle_input(config_path=config_path, mcp_command=mcp_command)
            sys.exit(0)
        elif len(sys.argv) >= 2 and sys.argv[1] == '--mcp-server':
            print("mcp_server detected")
            if len(sys.argv) < 3:
                print("❌ Error: --mcp-server requires an URL")
                sys.exit(1)
            mcp_url = sys.argv[2]
            config_path = sys.argv[3] if len(sys.argv) > 3 else None
            handle_input(config_path=config_path, mcp_url=mcp_url)
            sys.exit(0)
        # Handle the case: uv run sandbox config.json
        if len(sys.argv) == 2:
            arg = sys.argv[1]
            # Check if it's a JSON file (config)
            if arg.endswith('.json') or arg.endswith('.yaml') or arg.endswith('.yml'):
                # Start REPL with config
                handle_input(config_path=arg)
                sys.exit(0)
            else:
                # Try to use fire for command dispatch
                fire.Fire(SandboxCLI)
                sys.exit(0)
        # No arguments - start REPL
        if len(sys.argv) == 1:
            handle_input()
            sys.exit(0)
        # Use fire for command dispatch
        fire.Fire(SandboxCLI)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()






# import fire
# from .sandbox_models import SandboxConfig
# import json
# import sys
# from .spawner import Spawner
# import subprocess


# class SandboxCLI:
#     """Command-line interface for the sandbox tool"""

#     def execute_mcp_stdio(
#             self,
#             code,
#             mcp_command: str,
#             config_path=None
#             ):
#         if code == "":
#             print("You did not enter any code for the sandbox")
#             sys.exit(0)
#         config = get_config(config_path)
#         split_cmd = mcp_command.split(' ')
#         if len(split_cmd) > 1:
#             split_cmd[1] = f'sandbox/{split_cmd[1]}'
#             mcp_command = (' ').join(split_cmd)
#         spawner = Spawner(
#             config=config, server_path=None, mcp_command=mcp_command)
#         # sandbox.configure()
#         exec_through_sandbox(spawner=spawner, code=code)

#     def execute(
#             self, code,
#             config_path=None,
#             server_path='src/fastmcp_server.py'):
#         """Execute code in the sandbox"""
#         if code == "":
#             print("You did not enter any code for the sandbox")
#             sys.exit(0)
#         config = get_config(config_path)
#         spawner = Spawner(config=config, server_path=server_path)
#         # sandbox.configure()
#         exec_through_sandbox(spawner=spawner, code=code)


# def build_image() -> None:
#     build_result = subprocess.run([
#         "docker", "build",
#         "--network=host",
#         "-t", "sandbox-image",
#         "./src/sandbox"
#     ], capture_output=True, text=True)
#     if build_result.returncode != 0:
#         raise RuntimeError(f"Build failed: {build_result.stderr}")
#     print(f"Image built: sandbox-image")


# def exec_through_sandbox(spawner: Spawner, code: str):
#     docker_cmd = [
#         "docker", "run",
#         "--rm",
#         "--network=none",
#         "--cap-drop=ALL",
#         "--security-opt=no-new-privileges",
#         "--pids-limit=64",
#         f"--memory={spawner.config.max_memory_mb}m",
#         "--cpus=1",
#         "-i",
#         "sandbox-image",
#         "uv", "run", "python", "-m", "sandbox"
#     ]
#     print("Building image...")
#     build_image()
#     print("Image built")
#     result = spawner.spawn(code, docker_cmd)
#     if result.success:
#         print("\n\nYour result:")
#         print("-" * 12)
#         print(result.output)
#     else:
#         print(f'error: {result.error}')


# def get_config(config_path: str | None) -> SandboxConfig:
#     if config_path is None:
#         config = SandboxConfig()
#     else:
#         try:
#             with open(config_path, 'r') as f:
#                 data = json.loads(f.read())
#                 config = SandboxConfig.model_validate(data)
#         except Exception as e:
#             print(f"\n\nWARNING: {type(e).__name__}: {str(e)}")
#             print("Using default configuration instead\n\n")
#             config = SandboxConfig()
#     return config


# def handle_input(
#         config_path: str | None = None,
#         mcp_command: str | None = None):
#     print("Enter your code below to have it executed in the sandbox")
#     print("Press Ctrl+D when done")
#     print("-" * 50)
#     lines = []
#     try:
#         while True:
#             try:
#                 line = input()
#                 lines.append(line)
#             except EOFError:
#                 break
#     except KeyboardInterrupt:
#         print("\nExiting...")
#         return
#     if not lines:
#         print("No code entered. Exiting.")
#         return
#     code = '\n'.join(lines)
#     print("\n" + "=" * 50)
#     print(" " * 18 + "Executing code...")
#     print("=" * 50)
#     cli = SandboxCLI()
#     if mcp_command:
#         cli.execute_mcp_stdio(
#             code=code, config_path=config_path, mcp_command=mcp_command)
#     else:
#         cli.execute(code=code, config_path=config_path)


# def main():
#     if len(sys.argv) >= 2 and sys.argv[1] == '--mcp-stdio':
#         if len(sys.argv) < 3:
#             print("Error: --mcp-stdio requires a command")
#             sys.exit(1)

#         mcp_command = sys.argv[2]
#         config_path = sys.argv[3] if len(sys.argv) > 3 else None
#         handle_input(config_path=config_path, mcp_command=mcp_command)

#     elif len(sys.argv) == 1:
#         if sys.argv[0].split('/').pop() != 'sandbox':
#             print(f"Invalid command: {sys.argv[0]}")
#             sys.exit(1)
#         handle_input(None)

#     elif len(sys.argv) == 2:
#         if sys.argv[0].split('/').pop() != 'sandbox':
#             fire.Fire(SandboxCLI)
#             return
#         config_path = sys.argv[1]
#         handle_input(config_path)

#     else:
#         fire.Fire(SandboxCLI)


# if __name__ == "__main__":
#     main()
