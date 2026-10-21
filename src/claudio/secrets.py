"""Secret resolution — 1Password via `op read`, macOS Keychain via `security`."""

from __future__ import annotations

import shutil
import subprocess
import sys

_OP_TIMEOUT = 10  # seconds per op read call

# Cache resolved secrets within a single claudio run so identical op:// refs
# (e.g. the same token referenced from multiple projects) don't trigger extra
# biometric prompts.
_cache: dict[str, str] = {}


def _op_binary() -> str:
    """Return the path to the op binary, or exit 1 with a helpful message."""
    op = shutil.which("op")
    if not op:
        print(
            "claudio: 1Password CLI (`op`) not found — install it from "
            "https://developer.1password.com/docs/cli/get-started/",
            file=sys.stderr,
        )
        sys.exit(1)
    return op


def resolve_op_references(env: dict[str, str]) -> dict[str, str]:
    """Replace any ``op://`` values in *env* with their resolved secrets.

    Caches results within the process so identical refs are resolved once.
    Never prints the resolved value.
    """
    resolved = {}
    for key, value in env.items():
        if not value.startswith("op://"):
            resolved[key] = value
            continue

        if value in _cache:
            resolved[key] = _cache[value]
            continue

        op = _op_binary()
        try:
            result = subprocess.run(
                [op, "read", "--no-newline", value],
                capture_output=True,
                text=True,
                timeout=_OP_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(
                f"claudio: timed out resolving 1Password secret for {key} "
                f"(>{_OP_TIMEOUT}s) — is op authenticated?",
                file=sys.stderr,
            )
            sys.exit(1)

        if result.returncode != 0:
            print(
                f"claudio: failed to read 1Password secret for {key}: "
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(1)

        _cache[value] = result.stdout
        resolved[key] = result.stdout

    return resolved


_KEYCHAIN_PREFIX = "keychain://"


def resolve_keychain_references(env: dict[str, str]) -> dict[str, str]:
    """Replace any ``keychain://<service>/<account>`` values in *env* with secrets
    read from the macOS Keychain. Never prints the resolved value.
    """
    resolved = {}
    for key, value in env.items():
        if not value.startswith(_KEYCHAIN_PREFIX):
            resolved[key] = value
            continue

        if sys.platform != "darwin":
            print(
                f"claudio: keychain:// references are only supported on macOS (env var {key})",
                file=sys.stderr,
            )
            sys.exit(1)

        service, _, account = value[len(_KEYCHAIN_PREFIX):].partition("/")
        if not service or not account:
            print(
                f"claudio: invalid keychain reference for {key}: "
                "expected keychain://<service>/<account>",
                file=sys.stderr,
            )
            sys.exit(1)

        if value in _cache:
            resolved[key] = _cache[value]
            continue

        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"claudio: failed to read Keychain secret for {key}: "
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(1)

        secret = result.stdout.rstrip("\n")
        _cache[value] = secret
        resolved[key] = secret

    return resolved
