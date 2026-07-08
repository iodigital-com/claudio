"""Project selection logic."""

from __future__ import annotations

import sys

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML

from claudio.config import load_user_settings, save_user_settings


class ProjectNotFound(Exception):
    """Requested project name does not match any known project."""

    def __init__(self, name: str, available: list[dict]) -> None:
        self.name = name
        self.available = available
        super().__init__(f"{name!r} not found")


class AmbiguousProject(Exception):
    """Multiple projects exist and interactive selection is not allowed."""

    def __init__(self, projects: list[dict]) -> None:
        self.projects = projects
        super().__init__("multiple projects, interactive selection disabled")


def resolve_project(
    projects: list[dict],
    *,
    hint: str | None = None,
    interactive: bool = True,
) -> dict | None:
    """Return the selected project.

    Priority:
      1. hint (--project / CLAUDIO_PROJECT) — raise ProjectNotFound if no match
      2. Single project — auto-select
      3. Interactive: lastProject default then prompt (returns None on cancel)
      4. Non-interactive: raise AmbiguousProject
    """
    if hint is not None:
        for p in projects:
            if p["name"] == hint:
                return p
        raise ProjectNotFound(hint, projects)

    if len(projects) == 1:
        return projects[0]

    if not interactive:
        raise AmbiguousProject(projects)

    return select_project(projects)


def select_project(projects: list[dict]) -> dict | None:
    """Prompt the user to select a project. Returns the chosen project dict,
    or None if the user cancels (Ctrl-C / EOF)."""
    settings = load_user_settings()
    last = settings.get("lastProject")

    default_idx = 0
    if last is not None:
        for i, p in enumerate(projects):
            if p["name"] == last:
                default_idx = i
                break

    print("Available projects:")
    for i, p in enumerate(projects):
        marker = "*" if i == default_idx else " "
        print(f"  {marker} [{i + 1}] {p['name']}")
    print()

    try:
        raw = pt_prompt(
            f"Select project [1-{len(projects)}]: ",
            placeholder=HTML(f"<ansigray>{default_idx + 1}</ansigray>"),
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if raw == "":
        choice = default_idx
    else:
        try:
            choice = int(raw) - 1
        except ValueError:
            print(f"Invalid input: {raw}", file=sys.stderr)
            return None
        if choice < 0 or choice >= len(projects):
            print(f"Choice out of range: {raw}", file=sys.stderr)
            return None

    selected = projects[choice]
    settings["lastProject"] = selected["name"]
    save_user_settings(settings)

    return selected
