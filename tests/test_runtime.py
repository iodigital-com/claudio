"""Tests for claudio.runtime — env merging."""

from __future__ import annotations

from claudio.runtime import build_effective_env


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


def test_build_effective_env_empty_base():
    result = build_effective_env({}, {"KEY": "value"})
    assert result == {"KEY": "value"}


def test_build_effective_env_empty_project():
    result = build_effective_env({"KEY": "value"}, {})
    assert result == {"KEY": "value"}
