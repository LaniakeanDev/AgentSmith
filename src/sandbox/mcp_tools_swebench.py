from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
import fnmatch
from pathlib import Path
import os
import re
import subprocess
from pathlib import PurePath
import ast


_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mK]')

_OK_RE = re.compile(
    r'^OK(\s*\((?:skipped|expected failures|unexpected successes)=\d+.*\))?\s*$',
    re.MULTILINE,
)
_FAILED_RE = re.compile(r'^FAILED\s*\(.*\)\s*$', re.MULTILINE)


class TestResultParser:
    """Parse test results from stdout/stderr and exit code."""
    def __init__(self, test_type: str) -> None:
        self.test_type = test_type

    def parse_pytest(self, stdout: str, exit_code: int) -> bool | None:
        """django (recent), requests, flask, scikit-learn, matplotlib, etc."""
        # anchor to the actual summary line, ignore earlier noise
        tail = stdout[-4000:]  # summary is always near the end
        passed_m = re.search(r'\b([1-9]\d*) passed\b', tail)
        failed_m = re.search(r'\b([1-9]\d*) failed\b', tail)
        error_m = re.search(r'\b([1-9]\d*) error(s)?\b', tail)
        no_tests = 'no tests ran' in tail or 'collected 0 items' in tail
        if no_tests:
            return False
        if failed_m or error_m:
            return False
        return bool(passed_m) and exit_code == 0

    def parse_sympy_bin_test(self, stdout: str, exit_code: int) -> bool | None:
        """sympy/sympy — custom runner (bin/test), not pytest."""
        tail = stdout[-4000:]
        if 'DO *NOT* COMMIT!' in tail:
            return False
        m = re.search(r'tests finished:\s*(\d+)\s*passed', tail)
        if not m:
            return False  # couldn't confirm anything ran
        n_passed = int(m.group(1))
        has_fail_or_exc = bool(
            re.search(r'\bfailed\b', tail, re.IGNORECASE) or
            re.search(r'exceptions?\s*=', tail, re.IGNORECASE))
        return n_passed > 0 and not has_fail_or_exc and exit_code == 0

    def parse_django_unittest(
            self, stdout: str, stderr: str, exit_code: int) -> bool | None:
        """django/django — uses its own unittest-based runner (runtests.py)."""
        combined = _ANSI_RE.sub('', stdout + '\n' + stderr).replace('\r', '')

        ok_matches = list(_OK_RE.finditer(combined))
        failed_matches = list(_FAILED_RE.finditer(combined))

        if not ok_matches and not failed_matches:
            return None  # ambiguous — fall back to exit_code only

        last_ok_pos = ok_matches[-1].start() if ok_matches else -1
        last_failed_pos = failed_matches[-1].start() if failed_matches else -1

        # Whichever marker appears LAST in the log wins — this handles
        # concatenated FAIL_TO_PASS / PASS_TO_PASS runs correctly.
        if last_failed_pos > last_ok_pos:
            return False
        if last_ok_pos > last_failed_pos:
            return exit_code == 0

        return None  # shouldn't happen, but stay conservative

    def parse_unittest_generic(
            self, stdout: str, stderr: str, exit_code: int) -> bool | None:
        """pylint, sphinx, some smaller repos on plain unittest."""
        return self.parse_django_unittest(stdout, stderr, exit_code)

    DISPATCH = {
        'sympy': parse_sympy_bin_test,
        'django': parse_django_unittest,
        'psf': parse_pytest,
        'pallets': parse_pytest,
        'flask': parse_pytest,
        'scikit-learn': parse_pytest,
        'matplotlib': parse_pytest,
        'pytest': parse_pytest,
        'pydata': parse_pytest,
        'xarray': parse_pytest,
        'sphinx': parse_pytest,
        'pylint': parse_pytest,
    }

    def parse_test_result(self, stdout: str, stderr: str, exit_code: int) -> bool:
        parser = self.DISPATCH.get(self.test_type, self.parse_pytest)  # default to pytest, most common
        try:
            result = parser(stdout, exit_code) if parser is not \
                self.parse_django_unittest \
                else parser(stdout, stderr, exit_code)
        except Exception:
            result = None
        if result is None:
            # last-resort fallback: exit code only, never trust text alone
            return exit_code == 0
        return result


# Create an MCP server
mcp = FastMCP("SWEBench", json_response=True)
allowed_dirs = os.environ.get("allowed_directories", "").split(":")
if '/testbed' in allowed_dirs:
    cwd = os.path.abspath(os.path.join(os.getcwd(), '..', 'testbed'))
else:
    cwd = os.path.abspath(os.path.join(os.getcwd(), '..', allowed_dirs[0]))

eval_script = os.environ.get('eval_script')


@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """
    Read the content of a file with line numbers (up to 50 lines from \
        start_line only).
    The output format must be similar to cat -n

    Args:
        filepath: Path to the file
        start_line: First line number (1-indexed)
        end_line: Last line number (inclusive, 1-indexed)

    Returns:
        Formatted string with line numbers, or a message on error
    """
    # Validate parameters
    if start_line < 1 or end_line < start_line:
        return "Invalid line range: start_line must be >= 1 and end_line must be >= start_line"
    MAX_LINES = 50
    truncated = False
    try:
        lines = []
        file_path = Path(cwd) / filepath
        with open(file_path, 'r') as f:
            for i, line in enumerate(f, 1):
                if i > end_line:
                    break
                if i >= start_line:
                    if len(lines) >= MAX_LINES:
                        truncated = True
                        break
                    lines.append(f"{i}: {line.rstrip()}")
        result = '\n'.join(lines) if lines else None
        if result and truncated:
            last_line = start_line + MAX_LINES - 1
            result += f"\n... (truncated at line {last_line}; call again with start_line={last_line + 1} to continue)"
            return result
        return result
    except FileNotFoundError:
        return f"File not found: {filepath}"
    except PermissionError:
        return f"Permission denied: {filepath}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


@mcp.tool()
def list_files(directory: str, pattern: str = "*") -> dict[str, Any]:
    """
    List files in a directory matching a given pattern.

    Args:
        directory: Path to the directory to search
        pattern: File pattern to match (e.g., "*.txt", "test_*.py", "*")
                 Uses glob-style pattern matching

    Returns:
        Dict with 'files' list and 'count', or error message
    """
    # Validate directory
    if not directory:
        return {
            'success': False,
            'message': "Directory path cannot be empty"
        }
    try:
        # Convert to Path object for better handling
        dir_path = Path(cwd) / directory
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


MAX_RESULTS = 50


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*") -> str:
    f"""
    Perform a grep-like search in the codebase.

    Args:
        pattern: The search pattern (regex or plain text)
        file_pattern: File pattern to search in. Uses glob syntax, e.g. "*.py" or "*diophantine*" — do NOT use regex anchors like $ or ^ here

    Returns:
        Formatted string with matches following the format:
        /absolute/path/to/file.py:<line_number>:<line_content>
        returns at most {MAX_RESULTS}
    """
    if not pattern:
        return "No search pattern given"

    search_dir = cwd
    file_patterns = [p.strip() for p in file_pattern.split(',') if p.strip()]
    if not file_patterns:
        file_patterns = ["*"]

    def _run_search(regex):
        """Runs the walk+match loop for a given compiled regex. Returns (results, matching_file_count)."""
        results = []
        matching_file_count = 0
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                       ['__pycache__', 'venv', '.git', 'dist', 'build']]
            for file in files:
                filepath = os.path.join(root, file)
                abs_path = os.path.abspath(filepath)
                rel_path = os.path.relpath(abs_path, search_dir)

                matches_file_pattern = False
                for fp in file_patterns:
                    if PurePath(rel_path).match(fp) or PurePath(file).match(fp):
                        matches_file_pattern = True
                        break
                if not matches_file_pattern:
                    continue
                matching_file_count += 1

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                if len(results) >= MAX_RESULTS:
                                    return results, matching_file_count, True  # truncated
                                results.append(f"{abs_path}:{line_num}:{line.rstrip()}")
                except (PermissionError, OSError):
                    continue
        return results, matching_file_count, False

    try:
        # First pass: try as-given (regex if valid, else literal fallback on compile failure)
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        results, matching_file_count, truncated = _run_search(regex)

        # If nothing matched, and the pattern wasn't already treated as literal,
        # retry once with the pattern fully escaped — handles cases where the
        # pattern compiled "successfully" as regex but the caller meant it literally
        # (e.g. brackets like "variable_attrs[0]" being read as a character class).
        if not results and matching_file_count > 0:
            escaped_pattern = re.escape(pattern)
            if escaped_pattern != pattern:
                literal_regex = re.compile(escaped_pattern, re.IGNORECASE)
                results, matching_file_count, truncated = _run_search(literal_regex)

        if matching_file_count == 0:
            return f"0 files matched file_pattern='{file_pattern}'. \
                remember to use glob syntax, e.g. '*.py' or '*diophantine*'\
                    — do NOT use regex anchors like $ or ^ here"

        if not results:
            return f"No results found for {pattern}"

        if truncated:
            tcall = f"search_code(pattern={pattern}, file_pattern={file_pattern})="
            return f"{tcall}{chr(10).join(results)} (truncated at {MAX_RESULTS} results)"

        return '\n'.join(results)

    except Exception as e:
        return f"Search error: {type(e).__name__}: {str(e)}"


@mcp.tool()
def edit_file(filepath: str,
              old_str: str, new_str: str) -> dict[str, Any]:
    """
    Replace an exact string in a file with a new string.

    Args:
        filepath: Path to the file
        old_str: The exact string to replace (must exist in the file)
        new_str: The string to replace it with

    Returns:
        Dict with 'success' and 'message'
    Usage:
        edit_file(filepath, old_str, new_str)
    """
    # Validate inputs
    if not old_str:
        return {
            'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
            'success': False,
            'message': "old_str cannot be empty"
        }
    try:
        # Read the file
        file_path = Path(cwd) / filepath
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Check if old_str exists
        if old_str not in content:
            if new_str in content:
                return {
                    'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
                    'success': True,
                    'message': f"no-op: this change is already applied, '{new_str}' is already in {filepath}"
                }
            variant1 = old_str.replace("'", '"')
            variant2 = old_str.replace('"', "'")
            if variant1 in content:
                old_str = variant1
            elif variant2 in content:
                old_str = variant2
            else:
                return {
                    'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
                    'success': False,
                    'message': f"'{old_str}' not found in {filepath}"
                }
        # Count occurrences
        count = content.count(old_str)
        # Perform replacement
        new_content = content.replace(old_str, new_str)
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        message = f"Replaced {count} occurrence(s) of '{old_str}' with "\
                  f"'{new_str}' in {filepath}"
        return {
            'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
            'success': True,
            'message': message,
            'count': count
        }
    except FileNotFoundError:
        return {
            'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
            'success': False,
            'message': f"File not found: {filepath}"
        }
    except PermissionError:
        return {
            'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
            'success': False,
            'message': f"Permission denied: {filepath}"
        }
    except UnicodeDecodeError:
        message = f"File appears to be binary or has encoding issues: "\
                  f"{filepath}"
        return {
            'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
            'success': False,
            'message': message
        }
    except Exception as e:
        return {
            'tool_call': f'edit_file({filepath}, {old_str}, {new_str})',
            'success': False,
            'message': f"{type(e).__name__}: {str(e)}"
        }


# @mcp.tool()
# def search_function_or_class_definition_in_code(name: str) -> str | None:
#     """
#     Find the definition of a function or class in Python files.

#     Args:
#         name: The name of the function or class to find
#         name must be the bare function or class name,
#         e.g. __add__, not a qualified path like ClassName.method_name.

#     Returns:
#         Formatted string with definitions following the format:
#         /absolute/path/to/file.py:<line_number> <line_content>
#         Returns None if no definition is found.
#     """
#     if not name:
#         return None
#     search_dir = cwd
#     results = []
#     patterns = [
#         # Function definitions
#         re.compile(
#             rf'^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\(', re.MULTILINE),
#         # Class definitions
#         re.compile(rf'^\s*class\s+{re.escape(name)}\s*[:\(]', re.MULTILINE),
#     ]
#     try:
#         # Walk through directory
#         for root, dirs, files in os.walk(search_dir):
#             # Skip common exclusions
#             dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
#                        ['node_modules', '__pycache__', 'venv', 'env', '.git',
#                        'dist', 'build', '.pytest_cache', 'mypy_cache']]
#             for file in files:
#                 # Only process Python files
#                 if not file.endswith('.py'):
#                     continue
#                 filepath = os.path.join(root, file)
#                 abs_path = os.path.abspath(filepath)
#                 try:
#                     with open(filepath, 'r',
#                               encoding='utf-8', errors='ignore') as f:
#                         lines = f.readlines()
#                     # Search each line for definition
#                     for i, line in enumerate(lines, 1):
#                         for pattern in patterns:
#                             if pattern.search(line):
#                                 results.append(
#                                     f"{abs_path}:{i} {line.rstrip()}")
#                                 break  # Only add once per line
#                 except (UnicodeDecodeError, PermissionError, OSError):
#                     continue
#         if not results:
#             return None
#         return '\n'.join(results)
#     except Exception as e:
#         print(f"Search error: {type(e).__name__}: {str(e)}")
#         return None


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """
    Find the definition of a function or class in Python files.
    Args:
        name: The name of the function or class to find
        name must be the bare function or class name,
        e.g. __add__, not a qualified path like ClassName.method_name.
    Returns:
        Formatted string with definitions following the format:
        /absolute/path/to/file.py:<line_number> <qualified_name> (<kind>)
        Returns a message if no definition is found.
    """
    if not name:
        return "No name provided for search"
    search_dir = cwd
    results = []

    def visit_node(node, filepath, abs_path, scope_stack):
        """Recursively walk the AST, tracking enclosing class/function scope
        so matches can be reported with a fully qualified name."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name == name:
                    qualified = ".".join(scope_stack + [child.name])
                    kind = "async function" if isinstance(child, ast.AsyncFunctionDef) else "function"
                    results.append(
                        f"{abs_path}:{child.lineno} {qualified} ({kind})"
                    )
                # Recurse into the function body (nested defs/classes),
                # extending scope so nested names get qualified too.
                visit_node(child, filepath, abs_path, scope_stack + [child.name])
            elif isinstance(child, ast.ClassDef):
                if child.name == name:
                    qualified = ".".join(scope_stack + [child.name])
                    results.append(
                        f"{abs_path}:{child.lineno} {qualified} (class)"
                    )
                visit_node(child, filepath, abs_path, scope_stack + [child.name])
            else:
                # Not a scope-creating node itself, but may contain one
                # (e.g. an `if` block with a `def` inside it).
                visit_node(child, filepath, abs_path, scope_stack)
    try:
        for root, dirs, files in os.walk(search_dir):
            # Skip common exclusions
            dirs[:] = [
                d for d in dirs
                if not d.startswith('.') and d not in
                ['node_modules', '__pycache__', 'venv', 'env', '.git',
                 'dist', 'build', '.pytest_cache', 'mypy_cache']
            ]
            for file in files:
                if not file.endswith('.py'):
                    continue
                filepath = os.path.join(root, file)
                abs_path = os.path.abspath(filepath)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        source = f.read()
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
                try:
                    tree = ast.parse(source, filename=filepath)
                except SyntaxError:
                    # Unparseable file (e.g. Python 2 source, corrupted file) — skip.
                    continue
                visit_node(tree, filepath, abs_path, [])
        if not results:
            return f"No definition found for '{name}'"
        return '\n'.join(results)
    except Exception as e:
        return f"Search error: {type(e).__name__}: {str(e)}"


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find all usages of a symbol using regex."""
    if not name:
        return f"No name provided for reference search"
    search_dir = cwd
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
        def_filepath = os.path.abspath(os.path.join(cwd, filepath))
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
        return f"Search error: {type(e).__name__}: {str(e)}"


@mcp.tool()
def get_patch() -> str:  # check L:642 and L:653
    """
    Retrieve the unified git diff of all changes made to the repository.

    Returns:
        Unified git diff string showing all changes, or error message
    """
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return f"Returncode: {result.returncode}"
        # Get the diff of all changes (staged and unstaged)
        result = subprocess.run(
            # ["git", "diff", "--unified=3", "--no-color"],
            ["git", "-c", "core.fileMode=false",
             "diff", "--unified=3", "--no-color"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        diff_output = result.stdout
        # If no unstaged changes, check for staged changes
        if not diff_output:
            result = subprocess.run(
                # ["git", "diff", "--cached", "--unified=3", "--no-color"],
                ["git", "-c", "core.fileMode=false", "diff",
                 "--cached", "--unified=3", "--no-color"],
                cwd=cwd,
                capture_output=True,
                text=True
            )
            diff_output = result.stdout
        # If still no changes, check for untracked files
        if not diff_output:
            # Get list of untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=cwd,
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
        repo_name = os.path.basename(cwd)
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        branch = branch_result.stdout.strip() \
            if branch_result.returncode == 0 else "unknown"
        header = f"Repository: {repo_name}\n"
        header += f"Branch: {branch}\n"
        header += "Date: "
        header += f"{subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}\n"
        header += "=" * 80 + "\n"
        return header + diff_output
    except FileNotFoundError as e:
        return f"Error: {type(e).__name__}: {str(e)}"
    except Exception as e:
        return f"Error getting patch: {type(e).__name__}: {str(e)}"


@mcp.tool()
def run_tests() -> Dict:
    """
    Execute bash script from eval_script env var.
    Returns {stdout, stderr, exit_code, success}.
    """
    MAX_LEN = 2048
    all_tests_passed = False
    clean_stdout = ""
    clean_stderr = ""
    exit_code = -1
    TEST_TYPES = [
        'pytest',
        'sympy',
        'django',
        'psf',
        'pallets',
        'flask',
        'scikit-learn',
        'matplotlib',
        'pydata',
        'xarray',
        'sphinx',
        'pylint',
    ]
    test_type = "pytest"
    if eval_script is not None:
        for test in TEST_TYPES:
            if test in eval_script:
                test_type = test
                break
    test_result_parser = TestResultParser(test_type)
    try:
        process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env={**os.environ}
        )
        # Send the script to bash's stdin with a timeout
        stdout, stderr = process.communicate(input=eval_script, timeout=60)
        exit_code = process.returncode
        test_result_parser.parse_test_result(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code)
        all_tests_passed = test_result_parser.parse_test_result(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code)
        clean_stdout = stdout[-MAX_LEN:]
        if exit_code != 0:
            # If it failed, grab only the last 30 lines of stderr. 
            # This skips the Conda export noise and grabs the actual crash
            stderr_lines = stderr.strip().splitlines()
            clean_stderr = "\n".join(stderr_lines[-30:])
        else:
            clean_stderr = ""
    except subprocess.TimeoutExpired:
        process.kill()  # Kill the hung process
        stdout, stderr = process.communicate()  # Get any remaining output
        clean_stdout = "ERROR: Script execution timed out"
        clean_stderr = stderr[-500:] if stderr else ""
    except Exception as e:
        clean_stdout = ""
        clean_stderr = f"Unexpected error executing script: {str(e)}"
    # Always return the exact same keys so the LLM doesn't get confused
    return {
        'tool_call': 'run_tests()',
        'stdout': clean_stdout,
        'stderr': clean_stderr,
        'exit_code': exit_code,
        'all_tests_passed': all_tests_passed
    }


@mcp.tool()
def run_command(
        command: str, workdir: str = "") -> dict[str, Any]:
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
        workdir_path = Path(cwd) / workdir
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
    else:
        workdir_path = Path(cwd)
    working_dir = str(workdir_path.absolute())
    try:
        # Execute the command with shell=True for flexibility
        # Using shell=True allows for pipes, redirects, etc.
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=working_dir,
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
            'workdir': working_dir,
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
