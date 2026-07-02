"""claudio CLI entry point."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from claudio.projects import select_project
from claudio.settings import (
    ConfigError,
    load_user_settings,
    merged_claudio_config,
    highest_claude_env,
    validate_projects,
)


def main() -> None:
    from importlib.metadata import version

    if len(sys.argv) > 1 and sys.argv[1] == "get-key":
        _get_key_main(sys.argv[2:])
        return

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
        merged = _resolve_op_references(merged)
        extra_settings_args = ["--settings", json.dumps({"env": merged})]

    print(f"Using project: {selected['name']}")
    _exec_claude(extra_settings_args + claude_args)


def _resolve_op_value(value: str) -> str:
    """Resolve a value that may be a 1Password reference (op://...)."""
    if not value.startswith("op://"):
        return value
    result = subprocess.run(
        ["op", "read", value],
        capture_output=True,
        text=True,
        shell=sys.platform == "win32",
    )
    if result.returncode != 0:
        print(
            f"claudio: failed to read 1Password secret: {result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    return result.stdout.strip()


def _resolve_op_references(env: dict[str, str]) -> dict[str, str]:
    resolved = {}
    for key, value in env.items():
        resolved[key] = _resolve_op_value(value)
    return resolved


def _get_key_main(argv: list[str]) -> None:
    """Print the API key/token for the active project to stdout."""
    parser = argparse.ArgumentParser(
        prog="claudio get-key",
        description="Print the resolved API key for a project (for use as apiKeyHelper).",
    )
    parser.add_argument(
        "--project", "-p", help="Project name (defaults to last-used project)"
    )
    args = parser.parse_args(argv)

    config = merged_claudio_config()
    if not config:
        print("claudio: no configuration found", file=sys.stderr)
        sys.exit(1)

    try:
        projects = validate_projects(config)
    except ConfigError as exc:
        print(f"claudio: config error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.project:
        selected = next((p for p in projects if p["name"] == args.project), None)
        if not selected:
            names = ", ".join(p["name"] for p in projects)
            print(
                f"claudio: project '{args.project}' not found. Available: {names}",
                file=sys.stderr,
            )
            sys.exit(1)
    elif len(projects) == 1:
        selected = projects[0]
    else:
        settings = load_user_settings()
        last = settings.get("lastProject")
        selected = next((p for p in projects if p["name"] == last), None)
        if not selected:
            print(
                "claudio: no project selected. Run `claudio` first or pass --project.",
                file=sys.stderr,
            )
            sys.exit(1)

    env = selected.get("env", {})
    key_value = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
    if not key_value:
        print(
            f"claudio: no API key or auth token configured for project '{selected['name']}'",
            file=sys.stderr,
        )
        sys.exit(1)

    print(_resolve_op_value(key_value))


def _exec_claude(claude_args: list[str]) -> None:
    """Replace the current process with `claude`."""
    if sys.platform == "win32":
        result = subprocess.run(["claude", *claude_args], shell=True)
        sys.exit(result.returncode)
    else:
        os.execvp("claude", ["claude", *claude_args])
