"""Tests for claudio.config — config merge, validation, and JSON loading."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from claudio.config import (
    ConfigError,
    merged_claudio_config,
    validate_projects,
    _load_json,
)


# ---------------------------------------------------------------------------
# _load_json
# ---------------------------------------------------------------------------


def test_load_json_returns_empty_for_missing_file(tmp_path):
    result = _load_json(tmp_path / "does_not_exist.json")
    assert result == {}


def test_load_json_parses_valid_json(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"projects": [{"name": "work"}]}))
    assert _load_json(f) == {"projects": [{"name": "work"}]}


def test_load_json_exits_on_invalid_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    with pytest.raises(SystemExit) as exc_info:
        _load_json(f)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# validate_projects
# ---------------------------------------------------------------------------


def test_validate_projects_returns_list_on_valid_config():
    projects = validate_projects({"projects": [{"name": "work"}]})
    assert len(projects) == 1
    assert projects[0]["name"] == "work"


def test_validate_projects_raises_on_missing_projects_key():
    with pytest.raises(ConfigError):
        validate_projects({})


def test_validate_projects_raises_on_empty_list():
    with pytest.raises(ConfigError):
        validate_projects({"projects": []})


def test_validate_projects_raises_on_non_dict_project():
    with pytest.raises(ConfigError):
        validate_projects({"projects": ["not-a-dict"]})


def test_validate_projects_raises_on_missing_name():
    with pytest.raises(ConfigError):
        validate_projects({"projects": [{"env": {}}]})


def test_validate_projects_raises_on_empty_name():
    with pytest.raises(ConfigError):
        validate_projects({"projects": [{"name": ""}]})


def test_validate_projects_raises_on_non_dict_env():
    with pytest.raises(ConfigError):
        validate_projects({"projects": [{"name": "work", "env": "bad"}]})


def test_validate_projects_raises_on_non_string_env_value():
    with pytest.raises(ConfigError):
        validate_projects({"projects": [{"name": "work", "env": {"KEY": 123}}]})


def test_validate_projects_accepts_valid_env():
    projects = validate_projects({
        "projects": [{"name": "work", "env": {"ANTHROPIC_API_KEY": "sk-test"}}]
    })
    assert projects[0]["env"]["ANTHROPIC_API_KEY"] == "sk-test"


# ---------------------------------------------------------------------------
# validate_projects — anthropic block
# ---------------------------------------------------------------------------


def test_validate_projects_accepts_anthropic_bearer():
    projects = validate_projects({
        "projects": [{
            "name": "work",
            "anthropic": {
                "baseUrl": "https://proxy.example.com",
                "auth": {"type": "bearer", "token": "my-token"},
            },
        }]
    })
    assert projects[0]["anthropic"]["auth"]["type"] == "bearer"


def test_validate_projects_accepts_anthropic_api_key():
    projects = validate_projects({
        "projects": [{
            "name": "work",
            "anthropic": {
                "auth": {"type": "apiKey", "apiKey": "sk-test"},
            },
        }]
    })
    assert projects[0]["anthropic"]["auth"]["apiKey"] == "sk-test"


def test_validate_projects_raises_on_non_dict_anthropic():
    with pytest.raises(ConfigError):
        validate_projects({"projects": [{"name": "work", "anthropic": "bad"}]})


def test_validate_projects_raises_on_non_string_base_url():
    with pytest.raises(ConfigError):
        validate_projects({
            "projects": [{"name": "work", "anthropic": {"baseUrl": 123}}]
        })


def test_validate_projects_raises_on_non_dict_auth():
    with pytest.raises(ConfigError):
        validate_projects({
            "projects": [{"name": "work", "anthropic": {"auth": "bad"}}]
        })


def test_validate_projects_raises_on_invalid_auth_type():
    with pytest.raises(ConfigError):
        validate_projects({
            "projects": [{
                "name": "work",
                "anthropic": {"auth": {"type": "oauth", "token": "x"}},
            }]
        })


def test_validate_projects_raises_on_bearer_missing_token():
    with pytest.raises(ConfigError):
        validate_projects({
            "projects": [{
                "name": "work",
                "anthropic": {"auth": {"type": "bearer"}},
            }]
        })


def test_validate_projects_raises_on_api_key_missing_api_key():
    with pytest.raises(ConfigError):
        validate_projects({
            "projects": [{
                "name": "work",
                "anthropic": {"auth": {"type": "apiKey"}},
            }]
        })


# ---------------------------------------------------------------------------
# merged_claudio_config
# ---------------------------------------------------------------------------


def _make_layers(layers):
    """Build a list of (label, Path, data) triples from a list of dicts."""
    return [
        (f"layer-{i}", Path(f"/fake/layer-{i}.json"), data)
        for i, data in enumerate(layers)
    ]


def test_merged_config_no_layers_returns_empty():
    with patch("claudio.config.claudio_config_layers", return_value=[]):
        assert merged_claudio_config() == {}


def test_merged_config_no_layer_has_projects_returns_empty():
    layers = _make_layers([{"env": {"FOO": "bar"}}])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        assert merged_claudio_config() == {}


def test_merged_config_single_project():
    layers = _make_layers([{"projects": [{"name": "work"}]}])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        result = merged_claudio_config()
    assert result == {"projects": [{"name": "work"}]}


def test_merged_config_higher_layer_determines_project_list():
    # Layer 0 is highest precedence; it defines projects.
    # Layer 1 (lower) has an extra project that should NOT appear.
    layers = _make_layers([
        {"projects": [{"name": "work"}]},
        {"projects": [{"name": "work"}, {"name": "personal"}]},
    ])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        result = merged_claudio_config()
    names = [p["name"] for p in result["projects"]]
    assert names == ["work"]
    assert "personal" not in names


def test_merged_config_lower_layer_enriches_env():
    # Lower layer provides the API key; higher layer provides only name.
    layers = _make_layers([
        {"projects": [{"name": "work"}]},
        {"projects": [{"name": "work", "env": {"ANTHROPIC_API_KEY": "sk-lower"}}]},
    ])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        result = merged_claudio_config()
    assert result["projects"][0]["env"]["ANTHROPIC_API_KEY"] == "sk-lower"


def test_merged_config_higher_layer_env_wins():
    # Both layers define the same env key; higher layer value must win.
    layers = _make_layers([
        {"projects": [{"name": "work", "env": {"ANTHROPIC_API_KEY": "sk-high"}}]},
        {"projects": [{"name": "work", "env": {"ANTHROPIC_API_KEY": "sk-low"}}]},
    ])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        result = merged_claudio_config()
    assert result["projects"][0]["env"]["ANTHROPIC_API_KEY"] == "sk-high"


def test_merged_config_env_deep_merged_distinct_keys():
    # Higher layer adds one key; lower layer adds a different key.
    # Both should appear in the merged env.
    layers = _make_layers([
        {"projects": [{"name": "work", "env": {"HIGH_KEY": "high"}}]},
        {"projects": [{"name": "work", "env": {"LOW_KEY": "low"}}]},
    ])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        result = merged_claudio_config()
    env = result["projects"][0]["env"]
    assert env["HIGH_KEY"] == "high"
    assert env["LOW_KEY"] == "low"


def test_merged_config_preserves_project_order_from_defining_layer():
    layers = _make_layers([
        {"projects": [{"name": "z"}, {"name": "a"}, {"name": "m"}]},
    ])
    with patch("claudio.config.claudio_config_layers", return_value=layers):
        result = merged_claudio_config()
    assert [p["name"] for p in result["projects"]] == ["z", "a", "m"]
