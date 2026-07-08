"""Launch the `claude` binary, replacing the current process."""

from __future__ import annotations

import os
import subprocess
import sys


def exec_claude(claude_args: list[str], claude_path: str = "claude") -> None:
    """Replace the current process with *claude_path*."""
    if sys.platform == "win32":
        result = subprocess.run([claude_path, *claude_args], shell=True)
        sys.exit(result.returncode)
    else:
        os.execvp(claude_path, [claude_path, *claude_args])
