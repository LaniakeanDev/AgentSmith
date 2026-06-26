import fire
from .config import SandboxConfig
# from .sandbox_launcher import launch_sandbox
import json
import sys
from .sandbox import Sandbox


class SandboxCLI:
    """Command-line interface for the sandbox tool"""

    # def execute(self, code, config_file=None):
    #     """Execute code in the sandbox"""
    #     if config_file is None:
    #         config = SandboxConfig()
    #     else:
    #         try:
    #             with open(config_file, 'r') as f:
    #                 data = json.loads(f.read())
    #                 config = SandboxConfig.model_validate(data)
    #         except Exception as e:
    #             print(f"WARNING: {e}")
    #             config = SandboxConfig()
    #     result = launch_sandbox(config, code)
    #     stdout = result["stdout"]
    #     if stdout:
    #         stdout_data = json.loads(stdout)
    #         if "success" not in stdout_data:
    #             print("stdout data invalid")
    #             return None
    #         if stdout_data["success"]:
    #             print("\n\nYoury result:")
    #             print("-" * 12)
    #             print(stdout_data["output"])
    #     else:
    #         print(f'stderr: {result["stderr"]}')

    # def execute_without_subprocess(
    #         self, code,
    #         config_file=None,
    #         server_path='src/fastmcp_server.py'):
    #     """Execute code in the sandbox"""
    #     if config_file is None:
    #         config = SandboxConfig()
    #     else:
    #         try:
    #             with open(config_file, 'r') as f:
    #                 data = json.loads(f.read())
    #                 config = SandboxConfig.model_validate(data)
    #         except Exception as e:
    #             print(f"WARNING: {e}")
    #             config = SandboxConfig()
    #     sandbox = Sandbox(config, server_path)
    #     sandbox.configure()
    #     result = sandbox.execute(code)
    #     if result.success:
    #         print("Your result:")
    #         print("-" * 12)
    #         print(result.output)
    #     else:
    #         print(f'error: {result.error}')

    def execute(
            self, code,
            config_path=None,
            server_path='src/fastmcp_server.py'):
        """Execute code in the sandbox"""
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
        sandbox = Sandbox(config, server_path)
        sandbox.configure()
        result = sandbox.execute(code)
        if result.success:
            print("\n\nYour result:")
            print("-" * 12)
            print(result.output)
        else:
            print(f'error: {result.error}')


def handle_input(config_path: str | None = None):
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
    cli.execute(code=code, config_path=config_path)


def main():
    # if len(sys.argv) == 1 and sys.argv[0] == 'sandbox':
    if len(sys.argv) == 1:
        if sys.argv[0].split('/').pop() != 'sandbox':
            print(f"Invalid command: {sys.argv[0]}")
            sys.exit(1)
        handle_input(None)
        # print("Enter your code below to have it executed in the sandbox")
        # print("Press Ctrl+D when done")
        # print("-" * 50)
        # lines = []
        # try:
        #     while True:
        #         try:
        #             line = input()
        #             lines.append(line)
        #         except EOFError:
        #             break
        # except KeyboardInterrupt:
        #     print("\nExiting...")
        #     return
        # if not lines:
        #     print("No code entered. Exiting.")
        #     return
        # code = '\n'.join(lines)
        # print("\n" + "=" * 50)
        # print(" " * 18 + "Executing code...")
        # print("=" * 50)
        # cli = SandboxCLI()
        # cli.execute(code)
    elif len(sys.argv) == 2:
        if sys.argv[0].split('/').pop() != 'sandbox':
            fire.Fire(SandboxCLI)
            return
        config_path = sys.argv[1]
        handle_input(config_path)
        # try:
        #     with open(config_path, 'r') as f:
        #         data = json.load(f)
        #         config = SandboxConfig.model_validate(data)
        # except Exception as e:
        #     print(f"WARNING: {type(e).__name__}: {str(e)}")
        #     print("Using default config instead")
        #     config = SandboxConfig()
        
    else:
        fire.Fire(SandboxCLI)


if __name__ == "__main__":
    main()
