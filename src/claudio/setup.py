"""Editor setup helpers — generate wrapper shims and settings snippets."""

from __future__ import annotations

import json
import re
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


# When claudio injects credentials (e.g. a company proxy ANTHROPIC_BASE_URL +
# ANTHROPIC_AUTH_TOKEN), the extension should not nag for an interactive Claude
# sign-in. This mirrors Anthropic's documented third-party-provider setup.
_LOGIN_PROMPT_KEY = "claudeCode.disableLoginPrompt"


def _shim_content(claudio: str, claude: str) -> str:
    # VS Code / Cursor invoke the process wrapper with their *bundled* claude
    # binary as the first argument. `claudio wrapper` prefers that binary and
    # falls back to --fallback-claude when the editor passes no binary (e.g.
    # unsupported platforms) or when the shim is run manually.
    return f"#!/bin/sh\nexec {claudio} wrapper --fallback-claude {claude} -- \"$@\"\n"


class SettingsParseError(Exception):
    """Raised when an existing settings file cannot be parsed safely."""


def _strip_jsonc(text: str) -> str:
    """Strip // and /* */ comments and trailing commas from JSONC text.

    String-aware, so // or /* inside string values are preserved. VS Code /
    Cursor settings files are JSONC, which the stdlib json module rejects.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    result = "".join(out)
    # Remove trailing commas before a closing } or ].
    return re.sub(r",(\s*[}\]])", r"\1", result)


def _read_json(path: Path) -> dict[str, Any]:
    """Read a (possibly JSONC) settings file without losing existing content.

    Raises SettingsParseError for a non-empty file that cannot be parsed, so
    callers can abort instead of silently overwriting the user's settings.
    """
    if not path.exists():
        return {}
    raw = path.read_text()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_strip_jsonc(raw))
    except json.JSONDecodeError as exc:
        raise SettingsParseError(str(exc)) from exc


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def cmd_setup_print(adapter: EditorAdapter) -> None:
    """Print the settings snippet and shim script without writing anything."""
    claudio = _claudio_path()
    claude = _claude_path() or "/usr/local/bin/claude"
    shim = _shim_path()

    shim_content = _shim_content(claudio, claude)
    settings_snippet = {
        adapter.settings_key: str(shim),
        _LOGIN_PROMPT_KEY: True,
    }

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

    # Write the setting to user settings (workspace settings are not allowed for
    # this key). We MERGE into the existing file so unrelated settings survive.
    try:
        data = _read_json(adapter.user_settings)
    except SettingsParseError as exc:
        print(
            f"claudio setup: could not parse {adapter.user_settings}:\n"
            f"  {exc}\n"
            "  Refusing to overwrite it. Fix the JSON (or move it aside) and "
            "re-run, or add these keys manually:\n"
            f"    {adapter.settings_key}: {shim}\n"
            f"    {_LOGIN_PROMPT_KEY}: true",
            file=sys.stderr,
        )
        sys.exit(1)

    # Back up the existing file before touching it, so nothing is ever lost.
    backup: Path | None = None
    if adapter.user_settings.exists() and adapter.user_settings.read_text().strip():
        backup = adapter.user_settings.with_suffix(
            adapter.user_settings.suffix + ".claudio.bak"
        )
        backup.write_text(adapter.user_settings.read_text())

    data[adapter.settings_key] = str(shim)
    data[_LOGIN_PROMPT_KEY] = True
    _write_json(adapter.user_settings, data)

    print(f"Wrote {shim}")
    print(f"Updated {adapter.user_settings} → {adapter.settings_key}")
    if backup is not None:
        print(f"Backed up previous settings to {backup} (comments are not preserved)")
    print()
    print(f"Restart {adapter.name} (or reload the window) for the change to take effect.")
