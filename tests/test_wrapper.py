"""Tests for claudio wrapper subcommand."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from claudio.cli import main
from claudio.selector import AmbiguousProject, ProjectNotFound


def _make_project(name="work", env=None):
    p = {"name": name}
    if env is not None:
        p["env"] = env
    return p


# ---------------------------------------------------------------------------
# Wrapper — missing claude path
# ---------------------------------------------------------------------------


def test_wrapper_no_claude_path_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "wrapper"])
    project = _make_project("work")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    assert "missing claude path" in capsys.readouterr().err


def test_wrapper_double_dash_separator_stripped(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "wrapper", "--", "/usr/local/bin/claude"])
    project = _make_project("work")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    mock_exec.assert_called_once_with([], claude_path="/usr/local/bin/claude")


# ---------------------------------------------------------------------------
# Wrapper — non-interactive project resolution
# ---------------------------------------------------------------------------


def test_wrapper_resolves_project_non_interactively(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "wrapper", "--", "/usr/local/bin/claude"])
    project = _make_project("work")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.resolve_project", return_value=project) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()

    mock_resolve.assert_called_once_with([project], hint=None, interactive=False)


def test_wrapper_ambiguous_exits_1_with_instructions(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "wrapper", "--", "/usr/local/bin/claude"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", side_effect=AmbiguousProject(projects)):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "CLAUDIO_PROJECT" in err
    assert "work" in err


def test_wrapper_project_not_found_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "missing", "wrapper", "--", "/usr/local/bin/claude"])
    projects = [_make_project("work")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project",
               side_effect=ProjectNotFound("missing", projects)):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Wrapper — claude path forwarded to exec_claude
# ---------------------------------------------------------------------------


def test_wrapper_passes_claude_path_to_exec(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "wrapper", "--", "/custom/path/claude", "--verbose"])
    project = _make_project("work")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    mock_exec.assert_called_once_with(["--verbose"], claude_path="/custom/path/claude")


def test_wrapper_with_project_flag_uses_hint(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "work", "wrapper", "--", "/usr/local/bin/claude"])
    projects = [_make_project("work"), _make_project("personal")]
    project = projects[0]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", return_value=project) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()

    mock_resolve.assert_called_once_with(projects, hint="work", interactive=False)


# ---------------------------------------------------------------------------
# Wrapper — env vars set before exec
# ---------------------------------------------------------------------------


def test_wrapper_env_applied_before_exec(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "wrapper", "--", "/usr/local/bin/claude"])
    project = _make_project("work", env={"ANTHROPIC_AUTH_TOKEN": "bearer-token"})

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references",
               return_value={"ANTHROPIC_AUTH_TOKEN": "bearer-token"}), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    import os
    assert os.environ.get("ANTHROPIC_AUTH_TOKEN") == "bearer-token"
    mock_exec.assert_called_once()
