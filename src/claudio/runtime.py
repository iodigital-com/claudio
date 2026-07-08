"""Build the effective environment and Claude CLI arguments for a launch."""

from __future__ import annotations

import json
from typing import Any


def compile_anthropic_block(project: dict[str, Any]) -> dict[str, str]:
    """Compile the high-level `anthropic:` block to equivalent env vars.

    Mapping:
      anthropic.baseUrl          → ANTHROPIC_BASE_URL
      anthropic.auth.type=bearer → ANTHROPIC_AUTH_TOKEN (from auth.token)
      anthropic.auth.type=apiKey → ANTHROPIC_API_KEY   (from auth.apiKey)

    Values may contain op:// references; resolution happens later via
    resolve_op_references().
    """
    anthropic = project.get("anthropic")
    if not anthropic:
        return {}

    env: dict[str, str] = {}

    base_url = anthropic.get("baseUrl")
    if isinstance(base_url, str):
        env["ANTHROPIC_BASE_URL"] = base_url

    auth = anthropic.get("auth") or {}
    auth_type = auth.get("type")
    if auth_type == "bearer":
        token = auth.get("token")
        if isinstance(token, str):
            env["ANTHROPIC_AUTH_TOKEN"] = token
    elif auth_type == "apiKey":
        api_key = auth.get("apiKey")
        if isinstance(api_key, str):
            env["ANTHROPIC_API_KEY"] = api_key

    return env


def build_effective_env(
    base_env: dict[str, str],
    project_env: dict[str, str],
) -> dict[str, str]:
    """Merge base Claude env with project-specific env (project wins on conflict)."""
    return {**base_env, **project_env}


def build_settings_args(env: dict[str, str]) -> list[str]:
    """Return the `--settings <json>` args that pass env vars to Claude."""
    return ["--settings", json.dumps({"env": env})]
