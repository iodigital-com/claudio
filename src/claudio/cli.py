"""claudio CLI entry point."""

from __future__ import annotations

import sys

from claudio.config import (
    ConfigError,
    highest_claude_env,
    merged_claudio_config,
    validate_projects,
)
from claudio.launcher import exec_claude
from claudio.runtime import build_effective_env, build_settings_args
from claudio.secrets import resolve_op_references
from claudio.selector import select_project


def main() -> None:
    import argparse
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
        exec_claude(claude_args)
        return

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
        effective_env = build_effective_env(base_env, project_env)
        effective_env = resolve_op_references(effective_env)
        extra_settings_args = build_settings_args(effective_env)

    print(f"Using project: {selected['name']}")
    exec_claude(extra_settings_args + claude_args)
