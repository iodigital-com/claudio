"""claudio CLI entry point."""

from __future__ import annotations

import os
import shutil
import sys

from claudio.config import (
    ConfigError,
    claudio_config_candidates,
    claudio_config_layers,
    highest_claude_env,
    load_user_settings,
    merged_claudio_config,
    validate_projects,
)
from claudio.launcher import exec_claude
from claudio.runtime import build_effective_env
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


def _apply_project_env(project: dict) -> None:
    """Resolve and inject project env vars into the current process environment."""
    project_env = project.get("env", {})
    if not project_env:
        return
    _, base_env = highest_claude_env()
    effective_env = build_effective_env(base_env, project_env)
    effective_env = resolve_op_references(effective_env)
    os.environ.update(effective_env)


def _cmd_projects(projects: list[dict]) -> None:
    settings = load_user_settings()
    last = settings.get("lastProject")
    for p in projects:
        marker = "*" if p["name"] == last else " "
        print(f"  {marker} {p['name']}")


_CREDENTIAL_VARS = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
_PROXY_VAR = "ANTHROPIC_BASE_URL"
_KNOWN_VARS = (_PROXY_VAR,) + _CREDENTIAL_VARS
_VAR_WIDTH = max(len(v) for v in _KNOWN_VARS)  # 20


def _cmd_doctor(projects: list[dict], hint: str | None = None) -> None:
    """Check project config health. Exits 1 if any warnings are found."""
    warnings = 0

    # -- Binaries -----------------------------------------------------------
    print("Binaries:")
    for bin_name in ("claude", "op"):
        path = shutil.which(bin_name)
        if path:
            print(f"  {bin_name:<8}  {path}")
        else:
            print(f"  {bin_name:<8}  not found")
            if bin_name == "op":
                print(
                    "             install from "
                    "https://developer.1password.com/docs/cli/get-started/"
                )
            warnings += 1
    print()

    # -- Config layers ------------------------------------------------------
    print("Config:")
    active_paths = {str(path) for _label, path, _data in claudio_config_layers()}
    for _label, path in claudio_config_candidates():
        if path.exists():
            tag = "active" if str(path) in active_paths else "exists (no projects key)"
        else:
            tag = "not found"
        print(f"  {path}  [{tag}]")
    print()

    # -- Projects -----------------------------------------------------------
    # Filter to a single project when a hint is given.
    display_projects = projects
    if hint:
        display_projects = [p for p in projects if p["name"] == hint]
        if not display_projects:
            print(f"claudio doctor: project not found: {hint!r}", file=sys.stderr)
            sys.exit(1)

    print(f"{len(display_projects)} project(s) configured.\n")

    for proj in display_projects:
        name = proj["name"]
        env = proj.get("env", {})
        print(f"  {name}")

        for var in _KNOWN_VARS:
            if var in env:
                val = env[var]
                src = "1Password" if val.startswith("op://") else "plaintext"
                print(f"    {var:<{_VAR_WIDTH}}  ({src})")

        other_vars = sorted(k for k in env if k not in set(_KNOWN_VARS))
        for var in other_vars:
            print(f"    {var}")

        has_api_key = "ANTHROPIC_API_KEY" in env
        has_auth_token = "ANTHROPIC_AUTH_TOKEN" in env

        if not has_api_key and not has_auth_token:
            print("    warning: no credential configured — set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")
            warnings += 1
        elif has_api_key and has_auth_token:
            print(
                "    warning: both ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN are set"
                " — ANTHROPIC_AUTH_TOKEN takes precedence; remove one"
            )
            warnings += 1

        if has_auth_token and _PROXY_VAR not in env:
            print("    note: ANTHROPIC_AUTH_TOKEN set without ANTHROPIC_BASE_URL — is a proxy URL intended?")

        print()

    if warnings:
        print(f"{warnings} warning(s).")
        sys.exit(1)
    print("No issues found.")


def _cmd_wrapper(projects: list[dict], hint: str | None, remainder: list[str]) -> None:
    """Non-interactive project resolver for VS Code / Cursor process wrapper use."""
    if remainder and remainder[0] == "--":
        remainder = remainder[1:]

    if not remainder:
        print(
            "claudio wrapper: missing claude path\n"
            "  Usage: claudio wrapper -- /path/to/claude [...args]\n"
            "  Tip:   use 'which claude' to find the path",
            file=sys.stderr,
        )
        sys.exit(1)

    claude_path, *claude_args = remainder

    try:
        selected = resolve_project(projects, hint=hint, interactive=False)
    except AmbiguousProject as exc:
        print(
            "claudio wrapper: cannot resolve project non-interactively.\n"
            "\n"
            "Fix options:\n"
            "  1. Set CLAUDIO_PROJECT in the shell that starts your IDE:\n"
            f'       export CLAUDIO_PROJECT="{exc.projects[0]["name"]}"\n'
            "  2. Create .claude/claudio.settings.local.json with one project.\n"
            "  3. Run `claudio setup vscode --workspace` to pin the project.",
            file=sys.stderr,
        )
        sys.exit(1)
    except ProjectNotFound as exc:
        _print_not_found_error(exc)
        sys.exit(1)

    if selected is None:
        sys.exit(1)

    _apply_project_env(selected)
    exec_claude(claude_args, claude_path=claude_path)


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

    command: str | None = None
    if claude_args and claude_args[0] in ("projects", "current", "doctor", "wrapper"):
        command = claude_args.pop(0)

    hint: str | None = args.project or os.environ.get("CLAUDIO_PROJECT") or None
    interactive = not args.no_interactive

    config = merged_claudio_config()

    if not config:
        if command in ("projects", "current", "doctor", "wrapper"):
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

    if command == "doctor":
        _cmd_doctor(projects, hint=hint)
        return

    if command == "wrapper":
        _cmd_wrapper(projects, hint, claude_args)
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

    _apply_project_env(selected)
    print(f"Using project: {selected['name']}")
    exec_claude(claude_args)
