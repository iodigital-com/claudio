"""Secret resolution — currently 1Password via `op read`."""

from __future__ import annotations

import subprocess
import sys


def resolve_op_references(env: dict[str, str]) -> dict[str, str]:
    """Replace any `op://` values in *env* with their resolved secrets."""
    resolved = {}
    for key, value in env.items():
        if value.startswith("op://"):
            result = subprocess.run(
                ["op", "read", value],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(
                    f"claudio: failed to read 1Password secret for {key}: {result.stderr.strip()}",
                    file=sys.stderr,
                )
                sys.exit(1)
            resolved[key] = result.stdout.strip()
        else:
            resolved[key] = value
    return resolved
