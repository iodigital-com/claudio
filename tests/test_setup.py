"""Tests for claudio setup vscode / cursor."""

from __future__ import annotations

import dataclasses
import json
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from claudio.cli import main
from claudio.setup import CURSOR, VSCODE, EditorAdapter, cmd_setup_print, cmd_setup_workspace


def _adapter(base: EditorAdapter, user_settings: Path) -> EditorAdapter:
    """Return a copy of *base* with user_settings pointing at a test path."""
    return dataclasses.replace(base, user_settings=user_settings)


# ---------------------------------------------------------------------------
# EditorAdapter constants
# ---------------------------------------------------------------------------


def test_vscode_adapter_attributes():
    assert VSCODE.name == "VS Code"
    assert VSCODE.settings_key == "claudeCode.claudeProcessWrapper"
    assert "Code" in str(VSCODE.user_settings)


def test_cursor_adapter_attributes():
    assert CURSOR.name == "Cursor"
    assert CURSOR.settings_key == VSCODE.settings_key
    assert "Cursor" in str(CURSOR.user_settings)


def test_vscode_and_cursor_user_settings_differ():
    assert VSCODE.user_settings != CURSOR.user_settings


# ---------------------------------------------------------------------------
# cmd_setup_print
# ---------------------------------------------------------------------------


def test_setup_print_shows_shim_content(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
        cmd_setup_print(VSCODE)
    out = capsys.readouterr().out
    assert "claudio wrapper" in out
    assert "--fallback-claude /usr/bin/claude" in out
    assert "/usr/bin/claude" in out


def test_setup_print_shows_settings_key(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
        cmd_setup_print(VSCODE)
    out = capsys.readouterr().out
    assert VSCODE.settings_key in out


def test_setup_print_no_files_written(tmp_path, capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
        cmd_setup_print(VSCODE)
    assert list(tmp_path.iterdir()) == []


def test_setup_cursor_print_shows_cursor_name(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
        cmd_setup_print(CURSOR)
    out = capsys.readouterr().out
    assert "Cursor" in out


# ---------------------------------------------------------------------------
# cmd_setup_workspace — shim written to ~/.claude/claudio-wrapper
# ---------------------------------------------------------------------------


def test_setup_workspace_creates_global_shim(tmp_path):
    adapter = _adapter(VSCODE, tmp_path / "settings.json")
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(adapter)
    shim = tmp_path / ".claude" / "claudio-wrapper"
    assert shim.exists()
    assert "claudio wrapper" in shim.read_text()
    assert "--fallback-claude /usr/bin/claude" in shim.read_text()


def test_setup_workspace_shim_is_executable(tmp_path):
    adapter = _adapter(VSCODE, tmp_path / "settings.json")
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(adapter)
    shim = tmp_path / ".claude" / "claudio-wrapper"
    assert shim.stat().st_mode & stat.S_IXUSR


def test_setup_workspace_shim_path_in_user_settings(tmp_path):
    user_settings = tmp_path / "user_settings.json"
    adapter = _adapter(VSCODE, user_settings)
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(adapter)
    settings = json.loads(user_settings.read_text())
    assert settings[VSCODE.settings_key] == str(tmp_path / ".claude" / "claudio-wrapper")


# ---------------------------------------------------------------------------
# cmd_setup_workspace — user settings
# ---------------------------------------------------------------------------


def test_setup_workspace_sets_disable_login_prompt(tmp_path):
    user_settings = tmp_path / "user_settings.json"
    adapter = _adapter(VSCODE, user_settings)
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(adapter)
    settings = json.loads(user_settings.read_text())
    assert settings["claudeCode.disableLoginPrompt"] is True


def test_setup_print_shows_disable_login_prompt(capsys):
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
        cmd_setup_print(VSCODE)
    assert "claudeCode.disableLoginPrompt" in capsys.readouterr().out


def test_setup_workspace_merges_existing_user_settings(tmp_path):
    user_settings = tmp_path / "user_settings.json"
    user_settings.write_text(json.dumps({"editor.tabSize": 2}) + "\n")
    adapter = _adapter(VSCODE, user_settings)
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(adapter)
    settings = json.loads(user_settings.read_text())
    assert settings["editor.tabSize"] == 2
    assert VSCODE.settings_key in settings


def test_setup_workspace_exits_1_if_claude_not_found(tmp_path, capsys):
    adapter = _adapter(VSCODE, tmp_path / "settings.json")
    with patch("claudio.setup.shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            cmd_setup_workspace(adapter)
    assert exc_info.value.code == 1
    assert "claude" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# Cursor — separate user settings from VS Code, same shim
# ---------------------------------------------------------------------------


def test_setup_cursor_writes_to_cursor_user_settings(tmp_path):
    cursor_settings = tmp_path / "cursor_settings.json"
    adapter = _adapter(CURSOR, cursor_settings)
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(adapter)
    assert cursor_settings.exists()
    settings = json.loads(cursor_settings.read_text())
    assert CURSOR.settings_key in settings


def test_setup_cursor_and_vscode_share_shim(tmp_path):
    vscode_settings = tmp_path / "vscode_settings.json"
    cursor_settings = tmp_path / "cursor_settings.json"
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path):
        cmd_setup_workspace(_adapter(VSCODE, vscode_settings))
        cmd_setup_workspace(_adapter(CURSOR, cursor_settings))
    shim = str(tmp_path / ".claude" / "claudio-wrapper")
    assert json.loads(vscode_settings.read_text())[VSCODE.settings_key] == shim
    assert json.loads(cursor_settings.read_text())[CURSOR.settings_key] == shim


# ---------------------------------------------------------------------------
# claudio setup vscode / cursor via main()
# ---------------------------------------------------------------------------


def test_main_setup_vscode_print(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "vscode"])
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
        main()
    out = capsys.readouterr().out
    assert "VS Code" in out
    assert "claudio wrapper" in out


def test_main_setup_cursor_print(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "cursor"])
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=Path("/home/user")):
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


def test_main_setup_workspace_creates_global_shim(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["claudio", "setup", "vscode", "--workspace"])
    user_settings = tmp_path / "user_settings.json"
    with patch("claudio.setup.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.setup.Path.home", return_value=tmp_path), \
         patch("claudio.cli.VSCODE", _adapter(VSCODE, user_settings)):
        main()
    assert (tmp_path / ".claude" / "claudio-wrapper").exists()
    assert user_settings.exists()
