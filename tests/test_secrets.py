"""Tests for claudio.secrets — hardened op:// resolution."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from claudio.secrets import resolve_keychain_references, resolve_op_references


def _fake_ok(stdout: str = "secret") -> MagicMock:
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    return r


# ---------------------------------------------------------------------------
# --no-newline flag
# ---------------------------------------------------------------------------


def test_op_read_uses_no_newline_flag():
    with patch("claudio.secrets.shutil.which", return_value="op"), \
         patch("claudio.secrets.subprocess.run", return_value=_fake_ok()) as mock_run:
        resolve_op_references({"KEY": "op://vault/item/field"})
    cmd = mock_run.call_args[0][0]
    assert "--no-newline" in cmd


# ---------------------------------------------------------------------------
# Missing op binary
# ---------------------------------------------------------------------------


def test_missing_op_binary_exits_1(capsys):
    with patch("claudio.secrets.shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            resolve_op_references({"KEY": "op://vault/item/field"})
    assert exc_info.value.code == 1
    assert "op" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


def test_op_read_timeout_exits_1(capsys):
    with patch("claudio.secrets.shutil.which", return_value="op"), \
         patch("claudio.secrets.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="op", timeout=10)):
        with pytest.raises(SystemExit) as exc_info:
            resolve_op_references({"KEY": "op://vault/item/field"})
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "timed out" in err


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_identical_op_ref_resolved_only_once():
    with patch("claudio.secrets.shutil.which", return_value="op"), \
         patch("claudio.secrets.subprocess.run", return_value=_fake_ok("token-value")) as mock_run:
        result1 = resolve_op_references({"A": "op://vault/item/field"})
        result2 = resolve_op_references({"B": "op://vault/item/field"})

    assert mock_run.call_count == 1
    assert result1["A"] == "token-value"
    assert result2["B"] == "token-value"


def test_different_op_refs_each_resolved():
    with patch("claudio.secrets.shutil.which", return_value="op"), \
         patch("claudio.secrets.subprocess.run", return_value=_fake_ok("x")) as mock_run:
        resolve_op_references({
            "A": "op://vault/item/one",
            "B": "op://vault/item/two",
        })
    assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# Stdout not stripped — --no-newline is trusted
# ---------------------------------------------------------------------------


def test_stdout_not_stripped():
    """With --no-newline, op outputs no trailing newline; value must be used as-is."""
    with patch("claudio.secrets.shutil.which", return_value="op"), \
         patch("claudio.secrets.subprocess.run", return_value=_fake_ok("my-token")):
        result = resolve_op_references({"KEY": "op://vault/item/field"})
    assert result["KEY"] == "my-token"


# ---------------------------------------------------------------------------
# keychain:// resolution
# ---------------------------------------------------------------------------


def _kc_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_keychain_success():
    with patch("claudio.secrets.sys.platform", "darwin"), \
         patch("claudio.secrets.subprocess.run", return_value=_kc_proc(stdout="tok\n")) as run:
        out = resolve_keychain_references({"K": "keychain://svc/kc-success"})
    assert out == {"K": "tok"}
    assert run.call_args[0][0] == [
        "security", "find-generic-password", "-s", "svc", "-a", "kc-success", "-w",
    ]


def test_keychain_plain_value_untouched():
    with patch("claudio.secrets.subprocess.run") as run:
        out = resolve_keychain_references({"K": "plain"})
    assert out == {"K": "plain"}
    run.assert_not_called()


@pytest.mark.parametrize("ref", ["keychain://", "keychain://svc", "keychain://svc/"])
def test_keychain_malformed_ref_exits(ref):
    with patch("claudio.secrets.sys.platform", "darwin"), \
         patch("claudio.secrets.subprocess.run") as run:
        with pytest.raises(SystemExit) as exc_info:
            resolve_keychain_references({"K": ref})
    assert exc_info.value.code == 1
    run.assert_not_called()


def test_keychain_non_darwin_exits():
    with patch("claudio.secrets.sys.platform", "linux"), \
         patch("claudio.secrets.subprocess.run") as run:
        with pytest.raises(SystemExit) as exc_info:
            resolve_keychain_references({"K": "keychain://svc/acct"})
    assert exc_info.value.code == 1
    run.assert_not_called()


def test_keychain_security_failure_exits():
    with patch("claudio.secrets.sys.platform", "darwin"), \
         patch("claudio.secrets.subprocess.run",
               return_value=_kc_proc(returncode=44, stderr="not found\n")):
        with pytest.raises(SystemExit) as exc_info:
            resolve_keychain_references({"K": "keychain://svc/kc-fail"})
    assert exc_info.value.code == 1
