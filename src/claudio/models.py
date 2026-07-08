"""Shared type definitions for claudio."""

from __future__ import annotations

from typing import Any, TypedDict


class ProjectProfile(TypedDict, total=False):
    name: str
    env: dict[str, str]


class EffectiveConfig(TypedDict):
    projects: list[ProjectProfile]


class LaunchContext(TypedDict):
    project: ProjectProfile
    resolved_env: dict[str, str]
    claude_args: list[str]
