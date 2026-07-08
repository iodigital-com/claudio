"""Tests for claudio.runtime — env compilation and settings args."""

from __future__ import annotations

import json

import pytest

from claudio.runtime import build_effective_env, build_settings_args, compile_anthropic_block


# ---------------------------------------------------------------------------
# compile_anthropic_block
# ---------------------------------------------------------------------------


def test_compile_no_anthropic_key_returns_empty():
    assert compile_anthropic_block({"name": "work"}) == {}


def test_compile_anthropic_none_returns_empty():
    assert compile_anthropic_block({"name": "work", "anthropic": None}) == {}


def test_compile_base_url_only():
    result = compile_anthropic_block({
        "name": "work",
        "anthropic": {"baseUrl": "https://proxy.example.com"},
    })
    assert result == {"ANTHROPIC_BASE_URL": "https://proxy.example.com"}


def test_compile_bearer_auth():
    result = compile_anthropic_block({
        "name": "work",
        "anthropic": {
            "auth": {"type": "bearer", "token": "my-token"},
        },
    })
    assert result == {"ANTHROPIC_AUTH_TOKEN": "my-token"}


def test_compile_api_key_auth():
    result = compile_anthropic_block({
        "name": "work",
        "anthropic": {
            "auth": {"type": "apiKey", "apiKey": "sk-test"},
        },
    })
    assert result == {"ANTHROPIC_API_KEY": "sk-test"}


def test_compile_base_url_and_bearer():
    result = compile_anthropic_block({
        "name": "work",
        "anthropic": {
            "baseUrl": "https://proxy.example.com",
            "auth": {"type": "bearer", "token": "my-token"},
        },
    })
    assert result == {
        "ANTHROPIC_BASE_URL": "https://proxy.example.com",
        "ANTHROPIC_AUTH_TOKEN": "my-token",
    }


def test_compile_op_reference_passes_through():
    """op:// references are left intact; resolution happens later."""
    result = compile_anthropic_block({
        "name": "work",
        "anthropic": {
            "auth": {"type": "bearer", "token": "op://Employee/Klant A/token"},
        },
    })
    assert result["ANTHROPIC_AUTH_TOKEN"] == "op://Employee/Klant A/token"


def test_compile_unknown_auth_type_produces_no_key():
    result = compile_anthropic_block({
        "name": "work",
        "anthropic": {"auth": {"type": "unknown", "token": "x"}},
    })
    assert "ANTHROPIC_AUTH_TOKEN" not in result
    assert "ANTHROPIC_API_KEY" not in result


# ---------------------------------------------------------------------------
# build_effective_env — conflict resolution
# ---------------------------------------------------------------------------


def test_build_effective_env_project_wins_on_conflict():
    base = {"KEY": "base-value", "OTHER": "base-other"}
    project = {"KEY": "project-value"}
    result = build_effective_env(base, project)
    assert result["KEY"] == "project-value"
    assert result["OTHER"] == "base-other"


def test_build_effective_env_merges_distinct_keys():
    result = build_effective_env({"A": "1"}, {"B": "2"})
    assert result == {"A": "1", "B": "2"}


# ---------------------------------------------------------------------------
# build_settings_args
# ---------------------------------------------------------------------------


def test_build_settings_args_produces_settings_flag():
    args = build_settings_args({"KEY": "value"})
    assert args[0] == "--settings"
    parsed = json.loads(args[1])
    assert parsed == {"env": {"KEY": "value"}}
