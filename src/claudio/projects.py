"""Project selection logic."""

from __future__ import annotations

import sys

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML

from claudio.settings import (
    load_user_settings,
    save_user_settings,
    validate_projects,
)


def select_project(projects: list[dict]) -> dict | None:
    """Prompt the user to select a project. Returns the chosen project dict,
    or None if the user cancels (Ctrl-C / EOF)."""
    settings = load_user_settings()
    last = settings.get("lastProject")

    # Determine default index (0-based)
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

    # Persist last selection
    settings["lastProject"] = selected["name"]
    save_user_settings(settings)

    return selected
