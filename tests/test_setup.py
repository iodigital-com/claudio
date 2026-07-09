"""Tests for claudio setup vscode / cursor."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from claudio.cli import main
from claudio.setup import CURSOR, VSCODE, EditorAdapter, cmd_setup_print, cmd_setup_workspace


# ---------------------------------------------------------------------------
# EditorAdapter constants
# ---------------------------------------------------------------------------


def test_vscode_adapter_attributes():
    assert VSCODE.name == "VS Code"
    assert VSCODE.settings_file == ".vscode/settings.json"
    assert "claude.claudePath" in VSCODE.settings_key


def test_cursor_adapter_attributes():
    assert CURSOR.name == "Cursor"
    assert "cursor" in CURSOR.settings_file.lower()
    assert CURSOR.settings_key == VSCODE.settings_key  # same key, different file


# ---------------------------------------------------------------------------
# Cursor workspace — distinct settings path from VS Code
# ---------------------------------------------------------------------------


def test_setup_cursor_workspace_writes_cursor_settings(tmp_path):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(CURSOR, workspace_root=tmp_path)
    settings_path = tmp_path / ".cursor" / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())
    assert CURSOR.settings_key in settings


def test_setup_cursor_workspace_does_not_touch_vscode_settings(tmp_path):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(CURSOR, workspace_root=tmp_path)
    vscode_settings = tmp_path / ".vscode" / "settings.json"
    assert not vscode_settings.exists()


def test_setup_cursor_and_vscode_share_shim(tmp_path):
    """Both editors point to the same shim; running setup for both is idempotent."""
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(VSCODE, workspace_root=tmp_path)
        cmd_setup_workspace(CURSOR, workspace_root=tmp_path)
    shim = tmp_path / ".claude" / "claudio-wrapper"
    assert shim.exists()
    vscode_s = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
    cursor_s = json.loads((tmp_path / ".cursor" / "settings.json").read_text())
    assert vscode_s[VSCODE.settings_key] == cursor_s[CURSOR.settings_key] == str(shim)


def test_setup_cursor_print_shows_cursor_name(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_print(CURSOR)
    out = capsys.readouterr().out
    assert "Cursor" in out


def test_main_setup_cursor_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "cursor", "--workspace"])
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.cwd", return_value=tmp_path):
        main()
    assert (tmp_path / ".cursor" / "settings.json").exists()


# ---------------------------------------------------------------------------
# cmd_setup_print
# ---------------------------------------------------------------------------


def test_setup_print_shows_shim_content(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_print(VSCODE)
    out = capsys.readouterr().out
    assert "claudio wrapper" in out
    assert "/usr/bin/claude" in out


def test_setup_print_shows_settings_key(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_print(VSCODE)
    out = capsys.readouterr().out
    assert VSCODE.settings_key in out


def test_setup_print_no_secrets_written(tmp_path, capsys):
    """--print must never write any file."""
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_print(VSCODE)
    # workspace directory is unchanged
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# cmd_setup_workspace
# ---------------------------------------------------------------------------


def test_setup_workspace_creates_shim(tmp_path):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(VSCODE, workspace_root=tmp_path)
    shim = tmp_path / ".claude" / "claudio-wrapper"
    assert shim.exists()
    content = shim.read_text()
    assert "claudio wrapper" in content
    assert "/usr/bin/claude" in content


def test_setup_workspace_shim_is_executable(tmp_path):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(VSCODE, workspace_root=tmp_path)
    shim = tmp_path / ".claude" / "claudio-wrapper"
    mode = shim.stat().st_mode
    assert mode & stat.S_IXUSR


def test_setup_workspace_writes_settings_json(tmp_path):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(VSCODE, workspace_root=tmp_path)
    settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
    shim_path = str(tmp_path / ".claude" / "claudio-wrapper")
    assert settings[VSCODE.settings_key] == shim_path


def test_setup_workspace_merges_existing_settings(tmp_path):
    settings_path = tmp_path / ".vscode" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"editor.tabSize": 2}) + "\n")

    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        cmd_setup_workspace(VSCODE, workspace_root=tmp_path)

    settings = json.loads(settings_path.read_text())
    assert settings["editor.tabSize"] == 2
    assert VSCODE.settings_key in settings


def test_setup_workspace_exits_1_if_claude_not_found(tmp_path, capsys):
    with patch("claudio.setup.shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            cmd_setup_workspace(VSCODE, workspace_root=tmp_path)
    assert exc_info.value.code == 1
    assert "claude" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# claudio setup vscode / cursor via main()
# ---------------------------------------------------------------------------


def test_main_setup_vscode_print(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "vscode"])
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        main()
    out = capsys.readouterr().out
    assert "VS Code" in out
    assert "claudio wrapper" in out


def test_main_setup_cursor_print(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "cursor"])
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
        main()
    out = capsys.readouterr().out
    assert "Cursor" in out


def test_main_setup_unknown_editor_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "sublime"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert "Usage" in capsys.readouterr().err


def test_main_setup_no_editor_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_setup_workspace_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "vscode", "--workspace"])
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.cwd", return_value=tmp_path):
        main()
    assert (tmp_path / ".vscode" / "settings.json").exists()
