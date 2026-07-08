"""Build the effective environment and Claude CLI arguments for a launch."""

from __future__ import annotations

import json


def build_effective_env(
    base_env: dict[str, str],
    project_env: dict[str, str],
) -> dict[str, str]:
    """Merge base Claude env with project-specific env (project wins on conflict)."""
    return {**base_env, **project_env}


def build_settings_args(env: dict[str, str]) -> list[str]:
    """Return the `--settings <json>` args that pass env vars to Claude."""
    return ["--settings", json.dumps({"env": env})]
