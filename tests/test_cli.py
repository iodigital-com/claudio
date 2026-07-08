"""Tests for claudio.cli — launch behavior, arg forwarding, and secret resolution."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from claudio.cli import main
from claudio.config import ConfigError
from claudio.secrets import resolve_op_references
from claudio.selector import AmbiguousProject, ProjectNotFound


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(name="work", env=None):
    p = {"name": name}
    if env is not None:
        p["env"] = env
    return p


# ---------------------------------------------------------------------------
# resolve_op_references
# ---------------------------------------------------------------------------


def test_resolve_op_references_passes_through_plain_values():
    result = resolve_op_references({"KEY": "plain-value"})
    assert result == {"KEY": "plain-value"}


def test_resolve_op_references_calls_op_read_for_op_ref():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "resolved-secret\n"
    with patch("claudio.secrets.subprocess.run", return_value=fake) as mock_run:
        result = resolve_op_references({"KEY": "op://vault/item/field"})
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["op", "read", "op://vault/item/field"]
    assert result["KEY"] == "resolved-secret"


def test_resolve_op_references_exits_on_op_failure():
    fake = MagicMock()
    fake.returncode = 1
    fake.stderr = "item not found"
    with patch("claudio.secrets.subprocess.run", return_value=fake):
        with pytest.raises(SystemExit) as exc_info:
            resolve_op_references({"KEY": "op://vault/item/field"})
    assert exc_info.value.code == 1


def test_resolve_op_references_mixed_values():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "secret\n"
    with patch("claudio.secrets.subprocess.run", return_value=fake):
        result = resolve_op_references({
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
         patch("claudio.cli.exec_claude") as mock_exec:
        main()
    mock_exec.assert_called_once_with([])


def test_main_no_config_forwards_extra_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--model", "sonnet", "--no-stream"])
    with patch("claudio.cli.merged_claudio_config", return_value={}), \
         patch("claudio.cli.exec_claude") as mock_exec:
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
         patch("claudio.cli.resolve_op_references", return_value={"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("claudio.cli.resolve_project", return_value=project) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()
    mock_resolve.assert_called_once_with([project], hint=None, interactive=True)


# ---------------------------------------------------------------------------
# main — multiple projects → select_project called
# ---------------------------------------------------------------------------


def test_main_multiple_projects_calls_resolve_project(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    projects = [_make_project("work"), _make_project("personal")]
    selected = projects[0]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", return_value=selected) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()
    mock_resolve.assert_called_once_with(projects, hint=None, interactive=True)


def test_main_select_project_cancel_exits_130(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", return_value=None), \
         patch("claudio.cli.exec_claude"):
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
         patch("claudio.cli.resolve_op_references", side_effect=fake_resolve) as mock_resolve, \
         patch("claudio.cli.exec_claude") as mock_exec:
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
         patch("claudio.cli.resolve_op_references", return_value={"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    exec_args = mock_exec.call_args[0][0]
    assert "--verbose" in exec_args


def test_main_no_env_in_project_launches_claude_without_settings_flag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = _make_project("work")  # no env

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    exec_args = mock_exec.call_args[0][0]
    assert "--settings" not in exec_args


# ---------------------------------------------------------------------------
# main — --project flag
# ---------------------------------------------------------------------------


def test_main_project_flag_selects_by_name(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "personal"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", return_value=projects[1]) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()

    mock_resolve.assert_called_once_with(projects, hint="personal", interactive=True)


def test_main_project_flag_unknown_name_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "unknown"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project",
               side_effect=ProjectNotFound("unknown", projects)):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# main — CLAUDIO_PROJECT env var
# ---------------------------------------------------------------------------


def test_main_env_var_selects_by_name(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    monkeypatch.setenv("CLAUDIO_PROJECT", "personal")
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", return_value=projects[1]) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()

    mock_resolve.assert_called_once_with(projects, hint="personal", interactive=True)


def test_main_project_flag_beats_env_var(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--project", "work"])
    monkeypatch.setenv("CLAUDIO_PROJECT", "personal")
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project", return_value=projects[0]) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()

    mock_resolve.assert_called_once_with(projects, hint="work", interactive=True)


# ---------------------------------------------------------------------------
# main — --no-interactive
# ---------------------------------------------------------------------------


def test_main_no_interactive_passes_flag_to_resolve(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--no-interactive"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project",
               side_effect=AmbiguousProject(projects)):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_main_no_interactive_single_project_succeeds(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "--no-interactive"])
    project = _make_project("work")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.resolve_project", return_value=project) as mock_resolve, \
         patch("claudio.cli.exec_claude"):
        main()

    mock_resolve.assert_called_once_with([project], hint=None, interactive=False)


# ---------------------------------------------------------------------------
# resolve_project — unit tests
# ---------------------------------------------------------------------------


def test_resolve_project_hint_matches_by_name():
    from claudio.selector import resolve_project
    projects = [_make_project("work"), _make_project("personal")]
    result = resolve_project(projects, hint="personal")
    assert result["name"] == "personal"


def test_resolve_project_hint_not_found_raises():
    from claudio.selector import resolve_project
    projects = [_make_project("work")]
    with pytest.raises(ProjectNotFound) as exc_info:
        resolve_project(projects, hint="missing")
    assert exc_info.value.name == "missing"
    assert exc_info.value.available == projects


def test_resolve_project_single_auto_selects():
    from claudio.selector import resolve_project
    project = _make_project("work")
    result = resolve_project([project])
    assert result["name"] == "work"


def test_resolve_project_multiple_non_interactive_raises():
    from claudio.selector import resolve_project
    projects = [_make_project("work"), _make_project("personal")]
    with pytest.raises(AmbiguousProject) as exc_info:
        resolve_project(projects, interactive=False)
    assert len(exc_info.value.projects) == 2


# ---------------------------------------------------------------------------
# claudio projects subcommand
# ---------------------------------------------------------------------------


def test_main_projects_subcommand_lists_all(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "projects"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.load_user_settings", return_value={}):
        main()

    out = capsys.readouterr().out
    assert "work" in out
    assert "personal" in out


def test_main_projects_subcommand_marks_last(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "projects"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.load_user_settings", return_value={"lastProject": "personal"}):
        main()

    out = capsys.readouterr().out
    lines = out.splitlines()
    personal_line = next(l for l in lines if "personal" in l)
    assert "*" in personal_line


# ---------------------------------------------------------------------------
# claudio current subcommand
# ---------------------------------------------------------------------------


def test_main_current_subcommand_prints_name(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "current"])
    project = _make_project("work")

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.resolve_project", return_value=project):
        main()

    assert capsys.readouterr().out.strip() == "work"


def test_main_current_subcommand_no_config_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio", "current"])

    with patch("claudio.cli.merged_claudio_config", return_value={}):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_main_current_subcommand_ambiguous_falls_back_to_last(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["claudio", "current"])
    projects = [_make_project("work"), _make_project("personal")]

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": projects}), \
         patch("claudio.cli.validate_projects", return_value=projects), \
         patch("claudio.cli.resolve_project",
               side_effect=AmbiguousProject(projects)), \
         patch("claudio.cli.load_user_settings", return_value={"lastProject": "work"}):
        main()

    assert capsys.readouterr().out.strip() == "work"


# ---------------------------------------------------------------------------
# anthropic block compilation
# ---------------------------------------------------------------------------


def test_main_anthropic_bearer_sets_auth_token(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = {
        "name": "work",
        "anthropic": {
            "baseUrl": "https://proxy.example.com",
            "auth": {"type": "bearer", "token": "my-token"},
        },
    }

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references", side_effect=lambda e: e), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    args = mock_exec.call_args[0][0]
    settings = json.loads(args[args.index("--settings") + 1])
    assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://proxy.example.com"
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == "my-token"


def test_main_explicit_env_wins_over_anthropic_block(monkeypatch):
    """Explicit env key overrides the same key derived from the anthropic block."""
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = {
        "name": "work",
        "anthropic": {
            "auth": {"type": "bearer", "token": "anthropic-token"},
        },
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "explicit-token",
        },
    }

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references", side_effect=lambda e: e), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    args = mock_exec.call_args[0][0]
    settings = json.loads(args[args.index("--settings") + 1])
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == "explicit-token"


def test_main_anthropic_api_key_sets_api_key(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = {
        "name": "work",
        "anthropic": {
            "auth": {"type": "apiKey", "apiKey": "sk-test"},
        },
    }

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references", side_effect=lambda e: e), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    args = mock_exec.call_args[0][0]
    settings = json.loads(args[args.index("--settings") + 1])
    assert settings["env"]["ANTHROPIC_API_KEY"] == "sk-test"


def test_main_anthropic_op_reference_resolved(monkeypatch):
    """op:// in anthropic.auth.token is resolved before launch."""
    monkeypatch.setattr(sys, "argv", ["claudio"])
    project = {
        "name": "work",
        "anthropic": {
            "auth": {"type": "bearer", "token": "op://vault/item/token"},
        },
    }

    def fake_resolve(env):
        return {k: "resolved-secret" if v.startswith("op://") else v for k, v in env.items()}

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references", side_effect=fake_resolve), \
         patch("claudio.cli.resolve_project", return_value=project), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    args = mock_exec.call_args[0][0]
    settings = json.loads(args[args.index("--settings") + 1])
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == "resolved-secret"
