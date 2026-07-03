
import fnmatch
import os
import re


cwd = os.getcwd()


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
    search_dir = cwd
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


print(search_code("encoding=", "*.py"))
