"""Build the effective environment and Claude CLI arguments for a launch."""

from __future__ import annotations

import json
import os
import tempfile


def build_effective_env(
    base_env: dict[str, str],
    project_env: dict[str, str],
) -> dict[str, str]:
    """Merge base Claude env with project-specific env (project wins on conflict)."""
    return {**base_env, **project_env}


def build_settings_args(env: dict[str, str]) -> list[str]:
    """Return ``--settings <json>`` args that pass env vars to Claude inline."""
    return ["--settings", json.dumps({"env": env})]


def build_temp_file_args(env: dict[str, str]) -> tuple[list[str], str]:
    """Write env to a 0600 temp file and return ``(--settings <path>, path)``.

    The caller is responsible for deleting the file after the child process exits.
    The file is written atomically via ``os.fdopen`` so it is never world-readable.
    """
    fd, path = tempfile.mkstemp(prefix="claudio-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump({"env": env}, fh)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return ["--settings", path], path
