"""Shared pytest fixtures for the claudio test suite."""

from __future__ import annotations

import pytest

import claudio.secrets as _secrets_mod


@pytest.fixture(autouse=True)
def clear_secrets_cache():
    """Reset the in-process op:// cache before every test."""
    _secrets_mod._cache.clear()
    yield
    _secrets_mod._cache.clear()
