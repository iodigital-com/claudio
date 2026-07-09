"""Editor setup helpers — generate wrapper shims and settings snippets."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EditorAdapter:
    """Describes how to configure one editor to use the claudio wrapper."""

    name: str
    settings_file: str  # relative to workspace root
    settings_key: str   # JSON key that holds the claude executable path


VSCODE = EditorAdapter(
    name="VS Code",
    settings_file=".vscode/settings.json",
    settings_key="claude.claudePath",
)

CURSOR = EditorAdapter(
    name="Cursor",
    settings_file=".cursor/settings.json",
    settings_key="claude.claudePath",
)


def _claudio_path() -> str:
    """Return the absolute path to the running claudio executable."""
    exe = shutil.which("claudio")
    if exe:
        return exe
    # Fall back to the interpreter-based invocation path.
    return sys.argv[0]


def _claude_path() -> str | None:
    """Return the absolute path to the real claude binary, or None."""
    return shutil.which("claude")


def _shim_path(workspace_root: Path) -> Path:
    return workspace_root / ".claude" / "claudio-wrapper"


def _shim_content(claudio: str, claude: str) -> str:
    return f"#!/bin/sh\nexec {claudio} wrapper -- {claude} \"$@\"\n"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def cmd_setup_print(adapter: EditorAdapter) -> None:
    """Print the settings snippet and shim script without writing anything."""
    claudio = _claudio_path()
    claude = _claude_path() or "/usr/local/bin/claude"
    shim = ".claude/claudio-wrapper"

    shim_content = _shim_content(claudio, claude)
    settings_snippet = {adapter.settings_key: f"$WORKSPACE_ROOT/{shim}"}

    print(f"# {adapter.name} setup\n")
    print(f"# 1. Create {shim} in your workspace root and make it executable:")
    print()
    print(shim_content)
    print(f"#    chmod +x {shim}\n")
    print(f"# 2. Add to {adapter.settings_file} (replacing $WORKSPACE_ROOT with the absolute path):")
    print()
    print(json.dumps(settings_snippet, indent=2))


def cmd_setup_workspace(adapter: EditorAdapter, workspace_root: Path | None = None) -> None:
    """Create the shim and update the workspace settings file."""
    if workspace_root is None:
        workspace_root = Path.cwd()

    claudio = _claudio_path()
    claude = _claude_path()
    if not claude:
        print(
            "claudio setup: claude binary not found — install Claude Code first",
            file=sys.stderr,
        )
        sys.exit(1)

    # Write shim script.
    shim = _shim_path(workspace_root)
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(_shim_content(claudio, claude))
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Merge settings.json — only write the one key, never touch others.
    settings_path = workspace_root / adapter.settings_file
    data = _read_json(settings_path)
    data[adapter.settings_key] = str(shim)
    _write_json(settings_path, data)

    print(f"Wrote {shim.relative_to(workspace_root)}")
    print(f"Updated {adapter.settings_file} → {adapter.settings_key}")
    print()
    print("Restart VS Code (or reload the window) for the change to take effect.")
