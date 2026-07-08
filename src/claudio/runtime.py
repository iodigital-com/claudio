"""Build the effective environment for a launch."""

from __future__ import annotations


def build_effective_env(
    base_env: dict[str, str],
    project_env: dict[str, str],
) -> dict[str, str]:
    """Merge base Claude env with project-specific env (project wins on conflict)."""
    return {**base_env, **project_env}
