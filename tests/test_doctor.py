"""Tests for the enhanced claudio doctor subcommand."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from claudio.cli import main


def _make_project(name="work", env=None):
    p = {"name": name}
    if env is not None:
        p["env"] = env
    return p


# ---------------------------------------------------------------------------
# Binaries section
# ---------------------------------------------------------------------------


def test_doctor_shows_binary_paths(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "doctor"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", side_effect=lambda n: f"/usr/bin/{n}"), \
         patch("claudio.cli.claudio_config_candidates", return_value=[]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        main()
    out = capsys.readouterr().out
    assert "Binaries" in out
    assert "/usr/bin/claude" in out
    assert "/usr/bin/op" in out


def test_doctor_warns_when_op_not_found(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "doctor"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", return_value=None), \
         patch("claudio.cli.claudio_config_candidates", return_value=[]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "not found" in out
    assert "1password" in out.lower()


def test_doctor_warns_when_claude_not_found(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "doctor"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})

    def _which(name):
        return None if name == "claude" else "/usr/bin/op"

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", side_effect=_which), \
         patch("claudio.cli.claudio_config_candidates", return_value=[]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    assert "not found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Config layers section
# ---------------------------------------------------------------------------


def test_doctor_shows_config_section(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "doctor"])
    from pathlib import Path
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})
    # /nonexistent/... will not exist on any real filesystem
    fake_path = Path("/nonexistent/claudio.settings.json")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", return_value="/usr/bin/x"), \
         patch("claudio.cli.claudio_config_candidates",
               return_value=[("user", fake_path)]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        main()
    out = capsys.readouterr().out
    assert "Config" in out
    assert "not found" in out


def test_doctor_marks_active_config_file(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["claudio", "doctor"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})
    real_path = tmp_path / "claudio.settings.json"
    real_path.write_text('{"projects": []}')

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", return_value="/usr/bin/x"), \
         patch("claudio.cli.claudio_config_candidates",
               return_value=[("user", real_path)]), \
         patch("claudio.cli.claudio_config_layers",
               return_value=[("user", real_path, {"projects": [project]})]):
        main()
    out = capsys.readouterr().out
    assert "active" in out


# ---------------------------------------------------------------------------
# --project filter
# ---------------------------------------------------------------------------


def test_doctor_project_flag_filters_output(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "personal", "doctor"])
    projects = [
        _make_project("work", env={"ANTHROPIC_API_KEY": "sk-work"}),
        _make_project("personal", env={"ANTHROPIC_API_KEY": "sk-personal"}),
    ]
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.shutil.which", return_value="/usr/bin/x"), \
         patch("claudio.cli.claudio_config_candidates", return_value=[]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        main()
    out = capsys.readouterr().out
    assert "personal" in out
    assert "work" not in out
    assert "1 project(s)" in out


def test_doctor_project_flag_unknown_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "ghost", "doctor"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", return_value="/usr/bin/x"), \
         patch("claudio.cli.claudio_config_candidates", return_value=[]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# No plaintext values in output
# ---------------------------------------------------------------------------


def test_doctor_never_prints_env_values(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "doctor"])
    # Set both credentials to trigger a warning+exit so we can still capture output
    project = _make_project("work", env={
        "ANTHROPIC_API_KEY": "sk-super-secret",
        "ANTHROPIC_AUTH_TOKEN": "bearer-super-secret",
        "ANTHROPIC_BASE_URL": "https://proxy.secret.internal",
    })
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.shutil.which", return_value="/usr/bin/x"), \
         patch("claudio.cli.claudio_config_candidates", return_value=[]), \
         patch("claudio.cli.claudio_config_layers", return_value=[]):
        with pytest.raises(SystemExit):
            main()
    out = capsys.readouterr().out
    assert "sk-super-secret" not in out
    assert "bearer-super-secret" not in out
    assert "proxy.secret.internal" not in out
