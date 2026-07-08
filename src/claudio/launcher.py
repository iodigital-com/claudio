"""Launch the `claude` binary, optionally replacing the current process."""

from __future__ import annotations

import os
import subprocess
import sys


def exec_claude(claude_args: list[str], temp_file: str | None = None) -> None:
    """Launch ``claude`` with *claude_args*.

    If *temp_file* is given, ``subprocess.run`` is used so the file can be
    deleted after the child exits.  On Windows, ``subprocess.run`` is always
    used because ``os.execvp`` is unreliable there.  Otherwise the current
    process is replaced via ``os.execvp`` (fastest, no cleanup possible).
    """
    if sys.platform == "win32" or temp_file is not None:
        try:
            result = subprocess.run(["claude", *claude_args], shell=(sys.platform == "win32"))
        finally:
            if temp_file:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
        sys.exit(result.returncode)
    else:
        os.execvp("claude", ["claude", *claude_args])
