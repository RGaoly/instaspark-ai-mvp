"""Shared pytest configuration and fixtures.

Redirects the database to a temporary file so tests never touch production data.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# Patch DB_PATH to a temp file BEFORE any test module imports database.py.
# This ensures all tests operate on an isolated database.
_tmpdir = tempfile.TemporaryDirectory()
_test_db_path = Path(_tmpdir.name) / "test.db"

import infra.database as _db_module  # noqa: E402
import infra.config as _config_module  # noqa: E402

_db_module.DB_PATH = _test_db_path
_config_module.DATABASE_PATH = str(_test_db_path)


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the test database before and after each test."""
    _db_module.init_db()
    _db_module.reset_db()
    yield
    _db_module.reset_db()


def pytest_sessionfinish(session, exitstatus):
    """Clean up temp directory after all tests complete."""
    _tmpdir.cleanup()
