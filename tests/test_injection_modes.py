"""Tests for secret injection modes (settings-arg and temp-file)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claudio.cli import main
from claudio.runtime import build_settings_args, build_temp_file_args


# ---------------------------------------------------------------------------
# build_settings_args
# ---------------------------------------------------------------------------


def test_build_settings_args_returns_settings_flag_and_json():
    args = build_settings_args({"ANTHROPIC_API_KEY": "sk-test"})
    assert args[0] == "--settings"
    payload = json.loads(args[1])
    assert payload["env"]["ANTHROPIC_API_KEY"] == "sk-test"


# ---------------------------------------------------------------------------
# build_temp_file_args
# ---------------------------------------------------------------------------


def test_build_temp_file_args_returns_settings_flag_and_path(tmp_path):
    args, path = build_temp_file_args({"ANTHROPIC_API_KEY": "sk-test"})
    try:
        assert args[0] == "--settings"
        assert args[1] == path
        assert Path(path).exists()
        payload = json.loads(Path(path).read_text())
        assert payload["env"]["ANTHROPIC_API_KEY"] == "sk-test"
    finally:
        os.unlink(path)


def test_build_temp_file_args_file_has_0600_permissions(tmp_path):
    _, path = build_temp_file_args({"KEY": "value"})
    try:
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600
    finally:
        os.unlink(path)


def test_build_temp_file_args_file_deleted_after_use(tmp_path):
    _, path = build_temp_file_args({"KEY": "value"})
    os.unlink(path)
    assert not Path(path).exists()


# ---------------------------------------------------------------------------
# CLAUDIO_INJECT_MODE=temp-file integration via main()
# ---------------------------------------------------------------------------


def _make_project(name="work", env=None):
    p = {"name": name}
    if env is not None:
        p["env"] = env
    return p


def test_main_default_inject_mode_uses_settings_arg(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    monkeypatch.delenv("CLAUDIO_INJECT_MODE", raising=False)
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references", return_value={"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    args = mock_exec.call_args[0][0]
    assert "--settings" in args
    settings_idx = args.index("--settings")
    # settings-arg mode passes inline JSON (parseable)
    json.loads(args[settings_idx + 1])


def test_main_temp_file_mode_passes_file_path(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["claudio"])
    monkeypatch.setenv("CLAUDIO_INJECT_MODE", "temp-file")
    project = _make_project("work", env={"ANTHROPIC_API_KEY": "sk-test"})

    captured_temp: list[str] = []

    def fake_build_temp(env):
        import tempfile
        fd, path = tempfile.mkstemp(prefix="claudio-test-", suffix=".json")
        import json as _json
        with os.fdopen(fd, "w") as fh:
            _json.dump({"env": env}, fh)
        captured_temp.append(path)
        return ["--settings", path], path

    with patch("claudio.cli.merged_claudio_config", return_value={"projects": [project]}), \
         patch("claudio.cli.validate_projects", return_value=[project]), \
         patch("claudio.cli.highest_claude_env", return_value=(None, {})), \
         patch("claudio.cli.resolve_op_references", return_value={"ANTHROPIC_API_KEY": "sk-test"}), \
         patch("claudio.cli.build_temp_file_args", side_effect=fake_build_temp), \
         patch("claudio.cli.exec_claude") as mock_exec:
        main()

    # exec_claude is called with the temp file path as a kwarg
    kwargs = mock_exec.call_args[1]
    assert kwargs.get("temp_file") == captured_temp[0]
    # clean up
    for p in captured_temp:
        try:
            os.unlink(p)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# exec_claude — temp file is deleted after subprocess exits
# ---------------------------------------------------------------------------


def test_exec_claude_deletes_temp_file_after_subprocess(tmp_path, monkeypatch):
    from claudio.launcher import exec_claude

    temp = tmp_path / "claudio-test.json"
    temp.write_text('{"env": {}}')
    path = str(temp)

    fake_result = MagicMock()
    fake_result.returncode = 0

    with patch("claudio.launcher.subprocess.run", return_value=fake_result), \
         pytest.raises(SystemExit) as exc_info:
        exec_claude(["--settings", path], temp_file=path)

    assert exc_info.value.code == 0
    assert not temp.exists()


def test_exec_claude_deletes_temp_file_even_on_nonzero_exit(tmp_path):
    from claudio.launcher import exec_claude

    temp = tmp_path / "claudio-test.json"
    temp.write_text('{"env": {}}')
    path = str(temp)

    fake_result = MagicMock()
    fake_result.returncode = 1

    with patch("claudio.launcher.subprocess.run", return_value=fake_result), \
         pytest.raises(SystemExit) as exc_info:
        exec_claude(["--settings", path], temp_file=path)

    assert exc_info.value.code == 1
    assert not temp.exists()
