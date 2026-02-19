"""claudio CLI entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys

from claudio.projects import select_project
from claudio.settings import (
    ConfigError,
    merged_claudio_config,
    highest_claude_env,
    validate_projects,
)


def main() -> None:
    from importlib.metadata import version

    parser = argparse.ArgumentParser(
        prog="claudio",
        description=(
            "Switch between Claude Code projects with different API keys. "
            "All extra arguments are forwarded to the `claude` CLI."
        ),
        add_help=True,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('claudio')}"
    )
    # We capture only our own flags; everything else goes to claude.
    args, claude_args = parser.parse_known_args()

    config = merged_claudio_config()

    if not config:
        # No claudio config at all — just launch claude directly.
        _exec_claude(claude_args)

    try:
        projects = validate_projects(config)
    except ConfigError as exc:
        print(f"claudio: config error: {exc}", file=sys.stderr)
        sys.exit(1)

    if len(projects) == 1:
        selected = projects[0]
    else:
        selected = select_project(projects)
        if selected is None:
            sys.exit(130)

    project_env = selected.get("env", {})
    extra_settings_args: list[str] = []
    if project_env:
        _, base_env = highest_claude_env()
        merged = {**base_env, **project_env}
        extra_settings_args = ["--settings", json.dumps({"env": merged})]

    print(f"Using project: {selected['name']}")
    _exec_claude(extra_settings_args + claude_args)


def _exec_claude(claude_args: list[str]) -> None:
    """Replace the current process with `claude`."""
    os.execvp("claude", ["claude", *claude_args])
