import re
from typing import Optional


class TestResultParser:

    def parse(self, stdout: str, exit_code: int, repo: str = "") -> Optional[bool]:
        """Dispatch to the right parser based on detected test runner."""
        if self._looks_like_sympy(stdout):
            return self.parse_sympy(stdout, exit_code)
        return self.parse_pytest(stdout, exit_code)

    def _looks_like_sympy(self, stdout: str) -> bool:
        return "tests finished" in stdout.lower() or "test process starts" in stdout.lower()

    def parse_sympy(self, stdout: str, exit_code: int) -> Optional[bool]:
        """sympy's bin/test runner, not pytest."""
        summary_match = re.search(
            r"tests finished:\s*(?P<body>.+?)\s*(?:,\s*in\s+[\d.]+\s*seconds)?\s*==",
            stdout,
            re.IGNORECASE,
        )
        if not summary_match:
            # No summary line at all -> runner probably crashed before finishing
            return False if exit_code != 0 else None

        body = summary_match.group("body")

        # Grab counts, being careful "expected to fail" doesn't get counted as "failed"
        failed = re.search(r"(\d+)\s+failed\b", body)
        expected_fail = re.search(r"(\d+)\s+expected to fail\b", body)
        passed = re.search(r"(\d+)\s+passed\b", body)

        n_failed = int(failed.group(1)) if failed else 0
        n_expected_fail = int(expected_fail.group(1)) if expected_fail else 0
        n_passed = int(passed.group(1)) if passed else 0

        # Also check for sympy's explicit per-file bracket status and the
        # "DO *NOT* COMMIT!" banner it prints on genuine failures.
        if "do *not* commit" in stdout.lower():
            return False
        if "[fail]" in stdout.lower():
            return False

        if n_failed > 0:
            return False
        if n_passed > 0:
            return True

        # Nothing definitive parsed
        return None

    def parse_pytest(self, stdout: str, exit_code: int) -> Optional[bool]:
        """django (recent), requests, flask, scikit-learn, matplotlib, etc."""
        if exit_code != 0:
            return False
        low_stdout = stdout.lower()
        # Pytest's real failure signal is a summary token, not the bare
        # substring "fail" (which also matches "xfailed", "failed: 0", etc.)
        if re.search(r"\b\d+\s+failed\b", low_stdout):
            return False
        if re.search(r"\berror(s)?\b", low_stdout) and "0 errors" not in low_stdout:
            # be conservative; adjust per-framework if this over-triggers
            pass
        if re.search(r"\b\d+\s+passed\b", low_stdout):
            return True
        return None