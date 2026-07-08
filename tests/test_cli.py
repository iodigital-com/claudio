"""Tests for claudio.cli — launch behavior, arg forwarding, and secret resolution."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from claudio.cli import _resolve_op_references, main
from claudio.settings import ConfigError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(name="work", env=None):
    p = {"name": name}
    if env is not None:
        p["env"] = env
    return p


# ---------------------------------------------------------------------------
# _resolve_op_references
# ---------------------------------------------------------------------------


def test_resolve_op_references_passes_through_plain_values():
    result = _resolve_op_references({"KEY": "plain-value"})
    assert result == {"KEY": "plain-value"}


def test_resolve_op_references_calls_op_read_for_op_ref():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "resolved-secret\n"
    with patch("claudio.cli.subprocess.run", return_value=fake) as mock_run:
        result = _resolve_op_references({"KEY": "op://vault/item/field"})
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["op", "read", "op://vault/item/field"]
    assert result["KEY"] == "resolved-secret"


def test_resolve_op_references_exits_on_op_failure():
    fake = MagicMock()
    fake.returncode = 1
    fake.stderr = "item not found"
    with patch("claudio.cli.subprocess.run", return_value=fake):
        with pytest.raises(SystemExit) as exc_info:
            _resolve_op_references({"KEY": "op://vault/item/field"})
    assert exc_info.value.code == 1


def test_resolve_op_references_mixed_values():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "secret\n"
    with patch("claudio.cli.subprocess.run", return_value=fake):
        result = _resolve_op_references({
            "PLAIN": "plain-value",
            "SECRET": "op://vault/item/field",
        })
    assert result["PLAIN"] == "plain-value"
    assert result["SECRET"] == "secret"


# ---------------------------------------------------------------------------
# main — no config → pass-through to claude
# ---------------------------------------------------------------------------


def test_main_no_config_launches_claude_directly(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    with patch("claudio.cli.merged_claudio_config", return_value={}), \
         patch("claudio.cli._exec_claude") as mock_exec:
        main()
    mock_exec.assert_called_once_with([])


def test_main_no_config_forwards_extra_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--model", "sonnet", "--no-stream"])
    with patch("claudio.cli.merged_claudio_config", return_value={}), \
         patch("claudio.cli._exec_claude") as mock_exec:
        main()
    mock_exec.assert_called_once_with(["--model", "sonnet", "--no-stream"])


# ---------------------------------------------------------------------------
# main — invalid config → hard fail
# ---------------------------------------------------------------------------


def test_main_invalid_project_schema_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": []}), \
         patch("claudio.cli.validate_projects", side_effect=ConfigError("bad schema")):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# main — single project → auto-selected, no prompt
# ---------------------------------------------------------------------------


def test_main_single_project_auto_selected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})
    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli._resolve_op_references", return_value={"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("claudio.cli.select_project") as mock_select, \
         patch("claudio.cli._exec_claude"):
        main()
    mock_select.assert_not_called()


# ---------------------------------------------------------------------------
# main — multiple projects → select_project called
# ---------------------------------------------------------------------------


def test_main_multiple_projects_calls_select_project(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    projects = [_make_project("work"), _make_project("personal")]
    selected = projects[0]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.select_project", return_value=selected) as mock_select, \
         patch("claudio.cli._exec_claude"):
        main()
    mock_select.assert_called_once_with(projects)


def test_main_select_project_cancel_exits_130(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.select_project", return_value=None), \
         patch("claudio.cli._exec_claude"):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 130


# ---------------------------------------------------------------------------
# main — env forwarding and op:// resolution
# ---------------------------------------------------------------------------


def test_main_op_reference_resolved_before_forwarding(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "op://vault/item/field"})

    def fake_resolve(env):
        return {k: "resolved-secret" if v.startswith("op://") else v for k, v in env.items()}

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli._resolve_op_references", side_effect=fake_resolve) as mock_resolve, \
         patch("claudio.cli._exec_claude") as mock_exec:
        main()

    mock_resolve.assert_called_once()
    exec_args = mock_exec.call_args[0][0]
    assert "--settings" in exec_args
    settings_json = exec_args[exec_args.index("--settings") + 1]
    settings = json.loads(settings_json)
    assert settings["env"]["ANTHROPIC_API_KEY"] == "resolved-secret"


def test_main_extra_args_forwarded_alongside_settings(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--verbose"])
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli._resolve_op_references", return_value={"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("claudio.cli._exec_claude") as mock_exec:
        main()

    exec_args = mock_exec.call_args[0][0]
    assert "--verbose" in exec_args


def test_main_no_env_in_project_launches_claude_without_settings_flag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = _make_project("work")  # no env

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli._exec_claude") as mock_exec:
        main()

    exec_args = mock_exec.call_args[0][0]
    assert "--settings" not in exec_args
