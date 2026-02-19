"""Settings discovery for claudio and Claude Code configs.

Mirrors Claude Code's settings hierarchy:
  1. Local project settings  (.claude/settings.local.json)  — highest
  2. Shared project settings (.claude/settings.json)
  3. User settings           (~/.claude/settings.json)      — lowest

For claudio's own config the filenames are:
  claudio.settings.json / claudio.settings.local.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _find_git_root() -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _user_dir() -> Path:
    return Path.home() / ".claude"


def _project_dir() -> Path | None:
    root = _find_git_root()
    if root is None:
        return None
    return root / ".claude"


# ---------- Generic loader (ordered highest → lowest precedence) ----------


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


ConfigLayer = tuple[str, Path, dict[str, Any]]


def _config_layers(
    shared_name: str, local_name: str
) -> list[ConfigLayer]:
    """Return config layers ordered from highest to lowest precedence."""
    layers: list[ConfigLayer] = []

    project_dir = _project_dir()
    if project_dir is not None:
        local_path = project_dir / local_name
        data = _load_json(local_path)
        if data:
            layers.append(("project-local", local_path, data))

        shared_path = project_dir / shared_name
        data = _load_json(shared_path)
        if data:
            layers.append(("project-shared", shared_path, data))

    user_path = _user_dir() / shared_name
    data = _load_json(user_path)
    if data:
        layers.append(("user", user_path, data))

    return layers


# ---------- Claude Code settings ----------------------------------------


def claude_config_layers() -> list[ConfigLayer]:
    return _config_layers("settings.json", "settings.local.json")


def highest_claude_env() -> tuple[Path | None, dict[str, str]]:
    """Return the env dict from the highest-precedence Claude config that has one."""
    for _label, path, data in claude_config_layers():
        if "env" in data and isinstance(data["env"], dict):
            return path, data["env"]
    return None, {}


# ---------- claudio settings --------------------------------------------


def claudio_config_layers() -> list[ConfigLayer]:
    return _config_layers(
        "claudio.settings.json", "claudio.settings.local.json"
    )


def merged_claudio_config() -> dict[str, Any]:
    """Return a deep-merged claudio config across all layers (highest precedence wins).

    Projects are matched by name. For each project, fields are merged with
    higher-precedence layers winning. The 'env' dict within each project is
    also deep-merged so that, e.g., a user-level API key is inherited by a
    local project entry that only specifies a name.
    """
    layers = claudio_config_layers()
    if not layers:
        return {}

    # The highest-precedence layer that defines 'projects' determines which
    # projects are available. Lower layers only enrich those projects (e.g.
    # contributing env keys), never adding new ones to the list.
    defining_data = next(
        (data for _label, _path, data in layers if "projects" in data),
        None,
    )
    if defining_data is None:
        return {}

    # Build per-name merged configs from all layers (lowest → highest).
    projects_by_name: dict[str, dict[str, Any]] = {}
    for _label, _path, data in reversed(layers):
        for proj in data.get("projects", []):
            name = proj.get("name")
            if not isinstance(name, str):
                continue
            existing = projects_by_name.get(name, {})
            merged_proj = {**existing, **proj}
            # Deep-merge the env sub-dict instead of replacing it wholesale.
            if isinstance(existing.get("env"), dict) and isinstance(proj.get("env"), dict):
                merged_proj["env"] = {**existing["env"], **proj["env"]}
            projects_by_name[name] = merged_proj

    # Preserve the order from the defining layer; exclude any names not in it.
    defining_names = [
        p["name"]
        for p in defining_data.get("projects", [])
        if isinstance(p.get("name"), str)
    ]
    projects = [projects_by_name[n] for n in defining_names if n in projects_by_name]

    if not projects:
        return {}

    return {"projects": projects}


# ---------- User-level claudio settings -----------------------------------


def _user_settings_path() -> Path:
    return _user_dir() / "claudio.settings.json"


def load_user_settings() -> dict[str, Any]:
    return _load_json(_user_settings_path())


def save_user_settings(settings: dict[str, Any]) -> None:
    path = _user_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")


# ---------- Validation --------------------------------------------------


class ConfigError(Exception):
    pass


def validate_projects(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate and return the projects list from a claudio config."""
    projects = data.get("projects")
    if not isinstance(projects, list) or len(projects) == 0:
        raise ConfigError("'projects' must be a non-empty array")

    for i, proj in enumerate(projects):
        if not isinstance(proj, dict):
            raise ConfigError(f"projects[{i}] must be an object")
        if not isinstance(proj.get("name"), str) or not proj["name"]:
            raise ConfigError(f"projects[{i}].name must be a non-empty string")
        env = proj.get("env", {})
        if not isinstance(env, dict):
            raise ConfigError(f"projects[{i}].env must be an object")
        for k, v in env.items():
            if not isinstance(v, str):
                raise ConfigError(
                    f"projects[{i}].env.{k} must be a string"
                )
    return projects


