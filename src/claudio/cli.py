"""claudio CLI entry point."""

from __future__ import annotations

import os
import sys

from claudio.config import (
    ConfigError,
    highest_claude_env,
    load_user_settings,
    merged_claudio_config,
    validate_projects,
)
from claudio.launcher import exec_claude
from claudio.runtime import build_effective_env, build_settings_args, compile_anthropic_block
from claudio.secrets import resolve_op_references
from claudio.selector import AmbiguousProject, ProjectNotFound, resolve_project


def _print_ambiguous_error(exc: AmbiguousProject) -> None:
    print(
        "claudio: Multiple Claudio projects found and interactive selection is disabled.\n",
        file=sys.stderr,
    )
    print("Choose one of:", file=sys.stderr)
    for p in exc.projects:
        name = p["name"]
        print(f'  claudio --project "{name}" ...', file=sys.stderr)
    print(f'  export CLAUDIO_PROJECT="{exc.projects[0]["name"]}"', file=sys.stderr)
    print(
        "  create .claude/claudio.settings.local.json with one project",
        file=sys.stderr,
    )


def _print_not_found_error(exc: ProjectNotFound) -> None:
    print(f"claudio: project not found: {exc.name!r}", file=sys.stderr)
    print("Available projects:", file=sys.stderr)
    for p in exc.available:
        print(f"  {p['name']}", file=sys.stderr)


def _cmd_projects(projects: list[dict]) -> None:
    settings = load_user_settings()
    last = settings.get("lastProject")
    for p in projects:
        marker = "*" if p["name"] == last else " "
        print(f"  {marker} {p['name']}")


def _cmd_current(projects: list[dict], hint: str | None) -> None:
    try:
        selected = resolve_project(projects, hint=hint, interactive=False)
    except AmbiguousProject as exc:
        settings = load_user_settings()
        last = settings.get("lastProject")
        if last:
            for p in exc.projects:
                if p["name"] == last:
                    print(p["name"])
                    return
        _print_ambiguous_error(exc)
        sys.exit(1)
    except ProjectNotFound as exc:
        _print_not_found_error(exc)
        sys.exit(1)
    if selected is not None:
        print(selected["name"])


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
    parser.add_argument(
        "--project",
        "-p",
        metavar="NAME",
        help="Select a project by name (skips interactive prompt)",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Fail if interactive selection would be required",
    )

    args, claude_args = parser.parse_known_args()

    # Subcommands: extract from the start of remaining args rather than using
    # add_subparsers, which would conflict with unknown positionals forwarded to claude.
    command: str | None = None
    if claude_args and claude_args[0] in ("projects", "current"):
        command = claude_args.pop(0)

    # Resolve the project hint: explicit flag beats env var.
    hint: str | None = args.project or os.environ.get("CLAUDIO_PROJECT") or None
    interactive = not args.no_interactive

    config = merged_claudio_config()

    if not config:
        if command in ("projects", "current"):
            print("claudio: no projects configured", file=sys.stderr)
            sys.exit(1)
        exec_claude(claude_args)
        return

    try:
        projects = validate_projects(config)
    except ConfigError as exc:
        print(f"claudio: config error: {exc}", file=sys.stderr)
        sys.exit(1)

    if command == "projects":
        _cmd_projects(projects)
        return

    if command == "current":
        _cmd_current(projects, hint)
        return

    try:
        selected = resolve_project(projects, hint=hint, interactive=interactive)
    except ProjectNotFound as exc:
        _print_not_found_error(exc)
        sys.exit(1)
    except AmbiguousProject as exc:
        _print_ambiguous_error(exc)
        sys.exit(1)

    if selected is None:
        sys.exit(130)

    # Compile anthropic: block first; explicit env wins on conflict.
    anthropic_env = compile_anthropic_block(selected)
    project_env = {**anthropic_env, **selected.get("env", {})}
    extra_settings_args: list[str] = []
    if project_env:
        _, base_env = highest_claude_env()
        effective_env = build_effective_env(base_env, project_env)
        effective_env = resolve_op_references(effective_env)
        extra_settings_args = build_settings_args(effective_env)

    print(f"Using project: {selected['name']}")
    exec_claude(extra_settings_args + claude_args)
