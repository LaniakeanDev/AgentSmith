from typing import Any

from mcp.server.fastmcp import FastMCP
import fnmatch
from pathlib import Path
import os
import re
import subprocess

# Create an MCP server
mcp = FastMCP("SWEBench", json_response=True)


# Add an addition tool
@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str | None:
    """
    Read the content of a file with line numbers.
    The output format must be similar to cat -n

    Args:
        filepath: Path to the file
        start_line: First line number (1-indexed)
        end_line: Last line number (inclusive, 1-indexed)

    Returns:
        Formatted string with line numbers, or None on error
    """
    # Validate parameters
    if start_line < 1 or end_line < start_line:
        return None

    try:
        lines = []
        with open(filepath, 'r') as f:
            for i, line in enumerate(f, 1):
                if i > end_line:
                    break
                if i >= start_line:
                    lines.append(f"{i}: {line.rstrip()}")
        return '\n'.join(lines) if lines else None
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return None
    except PermissionError:
        print(f"Permission denied: {filepath}")
        return None
    except Exception as e:
        print(f"{type(e).__name__}: {str(e)}")
        return None


@mcp.tool()
def list_files(directory: str, pattern: str = "*") -> dict[str, Any] | None:
    """
    List files in a directory matching a given pattern.

    Args:
        directory: Path to the directory to search
        pattern: File pattern to match (e.g., "*.txt", "test_*.py", "*")
                 Uses glob-style pattern matching

    Returns:
        Dict with 'files' list and 'count', or None on error
    """
    # Validate directory
    if not directory:
        return {
            'success': False,
            'message': "Directory path cannot be empty"
        }
    try:
        # Convert to Path object for better handling
        dir_path = Path(directory)
        if not dir_path.exists():
            return {
                'success': False,
                'message': f"Directory does not exist: {directory}"
            }
        if not dir_path.is_dir():
            return {
                'success': False,
                'message': f"Path is not a directory: {directory}"
            }
        # Get all files matching the pattern
        files = []
        for item in dir_path.iterdir():
            if item.is_file():
                # Check if filename matches pattern
                if fnmatch.fnmatch(item.name, pattern):
                    file_info = {
                        'name': item.name,
                        'path': str(item.absolute()),
                        'size': item.stat().st_size,
                        'modified': item.stat().st_mtime
                    }
                    files.append(file_info)
        # Sort files alphabetically
        files.sort(key=lambda x: x['name'])
        return {
            'success': True,
            'directory': str(dir_path.absolute()),
            'pattern': pattern,
            'count': len(files),
            'files': files
        }

    except PermissionError:
        return {
            'success': False,
            'message': f"Permission denied accessing: {directory}"
        }
    except OSError as e:
        return {
            'success': False,
            'message': f"OS error: {str(e)}"
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"{type(e).__name__}: {str(e)}"
        }


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*") -> str | None:
    """
    Perform a grep-like search in the codebase.

    Args:
        pattern: The search pattern (regex or plain text)
        file_pattern: File pattern to search in (e.g., "*.py", "*.js,*.ts")

    Returns:
        Formatted string with matches following the format:
        /absolute/path/to/file.py:<line_number> <line_content>
    """
    if not pattern:
        return None
    # Default to current directory if no file_pattern specified
    search_dir = os.getcwd()
    # Parse file patterns
    file_patterns = [p.strip() for p in file_pattern.split(',') if p.strip()]
    if not file_patterns:
        file_patterns = ["*"]
    results = []
    try:
        # Compile regex pattern
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # If invalid regex, treat as literal string
            regex = re.compile(re.escape(pattern), re.IGNORECASE)
        # Walk through directory
        for root, dirs, files in os.walk(search_dir):
            # Skip hidden directories and common exclusions
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ['node_modules', '__pycache__', 'venv', 'env', '.git',
                       'dist', 'build']]
            for file in files:
                # Check if file matches pattern
                matches_file_pattern = False
                for fp in file_patterns:
                    if fnmatch.fnmatch(file, fp):
                        matches_file_pattern = True
                        break
                if not matches_file_pattern:
                    continue
                filepath = os.path.join(root, file)
                abs_path = os.path.abspath(filepath)
                try:
                    # Read file with error handling for binary files
                    with open(
                            filepath, 'r',
                            encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(
                                    f"{abs_path}:{line_num} {line.rstrip()}")
                except (UnicodeDecodeError, PermissionError, OSError):
                    # Skip binary files, permission denied, etc.
                    continue
        if not results:
            return None
        return '\n'.join(results)
    except Exception as e:
        print(f"Search error: {type(e).__name__}: {str(e)}")
        return None


@mcp.tool()
def edit_file(filepath: str,
              old_str: str, new_str: str) -> dict[str, Any] | None:
    """
    Replace an exact string in a file with a new string.

    Args:
        filepath: Path to the file
        old_str: The exact string to replace (must exist in the file)
        new_str: The string to replace it with

    Returns:
        Dict with 'success' and 'message', or None on critical error
    """
    # Validate inputs
    if not old_str:
        return {
            'success': False,
            'message': "old_str cannot be empty"
        }
    try:
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Check if old_str exists
        if old_str not in content:
            return {
                'success': False,
                'message': f"'{old_str}' not found in {filepath}"
            }
        # Count occurrences
        count = content.count(old_str)
        # Perform replacement
        new_content = content.replace(old_str, new_str)
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        message = f"Replaced {count} occurrence(s) of '{old_str}' with "\
                  f"'{new_str}' in {filepath}"
        return {
            'success': True,
            'message': message,
            'count': count
        }
    except FileNotFoundError:
        return {
            'success': False,
            'message': f"File not found: {filepath}"
        }
    except PermissionError:
        return {
            'success': False,
            'message': f"Permission denied: {filepath}"
        }
    except UnicodeDecodeError:
        message = f"File appears to be binary or has encoding issues: "\
                  f"{filepath}"
        return {
            'success': False,
            'message': message
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"{type(e).__name__}: {str(e)}"
        }


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str | None:
    """
    Find the definition of a function or class in Python files.

    Args:
        name: The name of the function or class to find

    Returns:
        Formatted string with definitions following the format:
        /absolute/path/to/file.py:<line_number> <line_content>
    """
    if not name:
        return None
    search_dir = os.getcwd()
    results = []
    patterns = [
        # Function definitions
        re.compile(
            rf'^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\(', re.MULTILINE),
        # Class definitions
        re.compile(rf'^\s*class\s+{re.escape(name)}\s*[:\(]', re.MULTILINE),
    ]
    try:
        # Walk through directory
        for root, dirs, files in os.walk(search_dir):
            # Skip common exclusions
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ['node_modules', '__pycache__', 'venv', 'env', '.git',
                       'dist', 'build', '.pytest_cache', 'mypy_cache']]
            for file in files:
                # Only process Python files
                if not file.endswith('.py'):
                    continue
                filepath = os.path.join(root, file)
                abs_path = os.path.abspath(filepath)
                try:
                    with open(filepath, 'r',
                              encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    # Search each line for definition
                    for i, line in enumerate(lines, 1):
                        for pattern in patterns:
                            if pattern.search(line):
                                results.append(
                                    f"{abs_path}:{i} {line.rstrip()}")
                                break  # Only add once per line
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
        if not results:
            return None
        return '\n'.join(results)
    except Exception as e:
        print(f"Search error: {type(e).__name__}: {str(e)}")
        return None


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str | None:
    """Find all usages of a symbol using regex."""
    if not name:
        return None
    search_dir = os.getcwd()
    results = []
    # Patterns to match references
    patterns = [
        # Function calls: name( or name (
        re.compile(rf'\b{re.escape(name)}\s*\('),
        # Method calls: .name(
        re.compile(rf'\.{re.escape(name)}\s*\('),
        # Attribute access: .name
        re.compile(rf'\.{re.escape(name)}\b'),
        # Decorators: @name
        re.compile(rf'@\s*{re.escape(name)}\b'),
        # Imports: import name, from x import name
        re.compile(
            rf'(?:from\s+\S+\s+import|import)\s+.*\b{re.escape(name)}\b'),
        # Class inheritance: class X(name):
        re.compile(rf'class\s+\w+\s*\(\s*.*\b{re.escape(name)}\b'),
    ]
    try:
        def_filepath = os.path.abspath(filepath)
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ['node_modules', '__pycache__', 'venv', 'env', '.git',
                       'dist', 'build', '.pytest_cache']]
            for file in files:
                if not file.endswith('.py'):
                    continue
                filepath_full = os.path.join(root, file)
                abs_path = os.path.abspath(filepath_full)
                # Skip the definition file itself
                if abs_path == def_filepath:
                    continue
                try:
                    with open(filepath_full, 'r',
                              encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    for i, line in enumerate(lines, 1):
                        # Skip if it's a definition
                        if re.match(
                            rf'^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\(',
                            line) or \
                           re.match(
                               rf'^\s*class\s+{re.escape(name)}\s*[:\(]',
                               line):
                            continue
                        for pattern in patterns:
                            if pattern.search(line):
                                results.append(
                                    f"{abs_path}:{i} {line.rstrip()}")
                                break
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
        return '\n'.join(results) if results else None
    except Exception as e:
        print(f"Search error: {type(e).__name__}: {str(e)}")
        return None


@mcp.tool()
def get_patch() -> str | None:
    """
    Retrieve the unified git diff of all changes made to the repository.

    Returns:
        Unified git diff string showing all changes, or None if not a git repo
    """
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None
        # Get the diff of all changes (staged and unstaged)
        result = subprocess.run(
            ["git", "diff", "--unified=3", "--no-color"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True
        )
        diff_output = result.stdout
        # If no unstaged changes, check for staged changes
        if not diff_output:
            result = subprocess.run(
                ["git", "diff", "--cached", "--unified=3", "--no-color"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True
            )
            diff_output = result.stdout
        # If still no changes, check for untracked files
        if not diff_output:
            # Get list of untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True
            )
            untracked = result.stdout.strip()
            if untracked:
                diff_output = f"Untracked files:\n{untracked}\n"
                diff_output += "\nTo include untracked files, "
                diff_output += "use 'git add' first."
        # If still no output, return empty message
        if not diff_output:
            return "No changes detected in the repository."
        # Add a header with repository info
        repo_name = os.path.basename(os.getcwd())
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True
        )
        branch = branch_result.stdout.strip() \
            if branch_result.returncode == 0 else "unknown"
        header = f"Repository: {repo_name}\n"
        header += f"Branch: {branch}\n"
        header += f"Date: {subprocess.run(
            ['date'], capture_output=True, text=True).stdout.strip()}\n"
        header += "=" * 80 + "\n"
        return header + diff_output
    except FileNotFoundError:
        return None  # Git not installed
    except Exception as e:
        print(f"Error getting patch: {type(e).__name__}: {str(e)}")
        return None


@mcp.tool()
def run_command(
        command: str, workdir: str = "") -> dict[str, Any] | None:
    """
    Execute a shell command in the specified working directory.

    Args:
        command: The shell command to execute
        workdir: Working directory (defaults to current directory)

    Returns:
        Dict with 'stdout', 'stderr', 'exit_code', and 'command' fields
    """
    # Validate inputs
    if not command:
        return {
            'success': False,
            'error': 'Command cannot be empty',
            'command': command,
            'stdout': '',
            'stderr': '',
            'exit_code': -1
        }
    # Set working directory
    if workdir:
        workdir_path = Path(workdir)
        if not workdir_path.exists():
            return {
                'success': False,
                'error': f'Working directory does not exist: {workdir}',
                'command': command,
                'stdout': '',
                'stderr': '',
                'exit_code': -1
            }
        if not workdir_path.is_dir():
            return {
                'success': False,
                'error': f'Path is not a directory: {workdir}',
                'command': command,
                'stdout': '',
                'stderr': '',
                'exit_code': -1
            }
        cwd = str(workdir_path.absolute())
    else:
        cwd = os.getcwd()
    try:
        # Execute the command with shell=True for flexibility
        # Using shell=True allows for pipes, redirects, etc.
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ}  # Pass current environment
        )
        # Set a timeout to prevent hanging (300 seconds = 5 minutes)
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return {
                'success': False,
                'error': 'Command timed out after 300 seconds',
                'command': command,
                'stdout': stdout,
                'stderr': stderr,
                'exit_code': -1
            }
        exit_code = process.returncode
        return {
            'success': exit_code == 0,
            'command': command,
            'workdir': cwd,
            'stdout': stdout,
            'stderr': stderr,
            'exit_code': exit_code
        }
    except FileNotFoundError:
        return {
            'success': False,
            'error': f'Command not found: {command}',
            'command': command,
            'stdout': '',
            'stderr': '',
            'exit_code': -1
        }
    except PermissionError:
        return {
            'success': False,
            'error': f'Permission denied executing: {command}',
            'command': command,
            'stdout': '',
            'stderr': '',
            'exit_code': -1
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}',
            'command': command,
            'stdout': '',
            'stderr': '',
            'exit_code': -1
        }


# Run with streamable HTTP transport
if __name__ == "__main__":
    # mcp.run(transport="streamable-http")
    mcp.run(transport="stdio")
