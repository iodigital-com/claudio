"""Editor setup helpers — generate wrapper shims and settings snippets."""

from __future__ import annotations

import json
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
    settings_key: str   # JSON key that holds the claude executable path
    user_settings: Path # absolute path to the editor's user settings.json


def _user_settings_path(app_name: str) -> Path:
    """Return the platform-specific user settings.json path for an editor."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / app_name / "User" / "settings.json"
    if sys.platform == "win32":
        appdata = Path(str(Path.home() / "AppData" / "Roaming"))
        return appdata / app_name / "User" / "settings.json"
    # Linux / other
    return home / ".config" / app_name / "User" / "settings.json"


VSCODE = EditorAdapter(
    name="VS Code",
    settings_key="claudeCode.claudeProcessWrapper",
    user_settings=_user_settings_path("Code"),
)

CURSOR = EditorAdapter(
    name="Cursor",
    settings_key="claudeCode.claudeProcessWrapper",
    user_settings=_user_settings_path("Cursor"),
)


def _claudio_path() -> str:
    """Return the absolute path to the running claudio executable."""
    exe = shutil.which("claudio")
    if exe:
        return exe
    return sys.argv[0]


def _claude_path() -> str | None:
    """Return the absolute path to the real claude binary, or None."""
    return shutil.which("claude")


def _shim_path() -> Path:
    return Path.home() / ".claude" / "claudio-wrapper"


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
    shim = _shim_path()

    shim_content = _shim_content(claudio, claude)
    settings_snippet = {adapter.settings_key: str(shim)}

    print(f"# {adapter.name} setup\n")
    print(f"# 1. Create {shim} and make it executable:")
    print()
    print(shim_content)
    print(f"#    chmod +x {shim}\n")
    print(f"# 2. Add to {adapter.name} user settings ({adapter.user_settings}):")
    print()
    print(json.dumps(settings_snippet, indent=2))


def cmd_setup_workspace(adapter: EditorAdapter) -> None:
    """Create the global shim and update the editor's user settings file."""
    claudio = _claudio_path()
    claude = _claude_path()
    if not claude:
        print(
            "claudio setup: claude binary not found — install Claude Code first",
            file=sys.stderr,
        )
        sys.exit(1)

    # Write shim to ~/.claude/claudio-wrapper (global, not per-repo).
    shim = _shim_path()
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(_shim_content(claudio, claude))
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Write the setting to user settings (workspace settings are not allowed for this key).
    data = _read_json(adapter.user_settings)
    data[adapter.settings_key] = str(shim)
    _write_json(adapter.user_settings, data)

    print(f"Wrote {shim}")
    print(f"Updated {adapter.user_settings} → {adapter.settings_key}")
    print()
    print(f"Restart {adapter.name} (or reload the window) for the change to take effect.")
