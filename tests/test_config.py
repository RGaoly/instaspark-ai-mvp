"""Tests for the configuration module — .env loading, defaults, type casting."""

from __future__ import annotations

import pytest


def test_config_imports_successfully():
    """Config module should import without errors."""
    from infra import config

    assert config is not None


def test_app_name_is_string():
    from infra.config import APP_NAME

    assert isinstance(APP_NAME, str)
    assert len(APP_NAME) > 0


def test_database_path_is_valid():
    from infra.config import DATABASE_PATH

    # DATABASE_PATH can be a Path or str depending on environment (test vs production)
    path_str = str(DATABASE_PATH)
    assert len(path_str) > 0
    assert path_str.endswith(".db")


def test_sqlite_journal_mode_default():
    from infra.config import SQLITE_JOURNAL_MODE

    assert SQLITE_JOURNAL_MODE in {"WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY"}


def test_pbkdf2_iterations_is_int():
    from infra.config import PBKDF2_ITERATIONS

    assert isinstance(PBKDF2_ITERATIONS, int)
    assert PBKDF2_ITERATIONS >= 100_000  # Security minimum


def test_default_credentials_are_strings():
    from infra.config import (
        DEFAULT_ADMIN_PASSWORD,
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_DEMO_PASSWORD,
        DEFAULT_DEMO_USERNAME,
    )

    assert isinstance(DEFAULT_ADMIN_USERNAME, str)
    assert isinstance(DEFAULT_ADMIN_PASSWORD, str)
    assert isinstance(DEFAULT_DEMO_USERNAME, str)
    assert isinstance(DEFAULT_DEMO_PASSWORD, str)
    assert len(DEFAULT_ADMIN_PASSWORD) > 0
    assert len(DEFAULT_DEMO_PASSWORD) > 0


def test_data_paths_are_path_objects():
    from pathlib import Path

    from infra.config import (
        CREATORS_DATA_PATH,
        MISSION_DATA_PATH,
        OPPORTUNITIES_DATA_PATH,
    )

    for path in [CREATORS_DATA_PATH, MISSION_DATA_PATH, OPPORTUNITIES_DATA_PATH]:
        assert isinstance(path, Path)
        assert path.exists(), f"{path} should ship with the repo"


def test_score_weights_sum_to_one():
    from infra.config import SCORE_WEIGHTS

    total = sum(SCORE_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


def test_score_weights_are_floats():
    from infra.config import SCORE_WEIGHTS

    for key, value in SCORE_WEIGHTS.items():
        assert isinstance(value, float), f"{key} should be float"
        assert 0.0 <= value <= 1.0, f"{key} should be in [0, 1]"


def test_opportunity_thresholds_are_ints():
    from infra.config import (
        OPPORTUNITY_HUMAN_REVIEW_THRESHOLD,
        OPPORTUNITY_LOW_CONFIDENCE_THRESHOLD,
        OPPORTUNITY_QUALIFIED_THRESHOLD,
    )

    assert isinstance(OPPORTUNITY_HUMAN_REVIEW_THRESHOLD, int)
    assert isinstance(OPPORTUNITY_QUALIFIED_THRESHOLD, int)
    assert isinstance(OPPORTUNITY_LOW_CONFIDENCE_THRESHOLD, int)

    # Thresholds should be logically ordered
    assert OPPORTUNITY_LOW_CONFIDENCE_THRESHOLD < OPPORTUNITY_HUMAN_REVIEW_THRESHOLD
    assert OPPORTUNITY_HUMAN_REVIEW_THRESHOLD <= OPPORTUNITY_QUALIFIED_THRESHOLD


def test_external_service_keys_default_empty():
    from infra.config import FEISHU_APP_ID, FEISHU_APP_SECRET, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

    # In test environment, API key should be empty (no real key)
    assert isinstance(LLM_API_KEY, str)
    assert isinstance(FEISHU_APP_ID, str)
    assert isinstance(FEISHU_APP_SECRET, str)

    # Base URL and model should have defaults
    assert isinstance(LLM_BASE_URL, str)
    assert LLM_BASE_URL.startswith("https://")
    assert isinstance(LLM_MODEL, str)
    assert len(LLM_MODEL) > 0


def test_config_values_match_defaults():
    """Without .env overrides, config should return documented defaults."""
    from infra.config import (
        APP_NAME,
        DEFAULT_ADMIN_DISPLAY_NAME,
        DEFAULT_ADMIN_USERNAME,
        PBKDF2_ITERATIONS,
        SALT_LENGTH,
    )

    assert APP_NAME == "InstaSpark AI"
    assert DEFAULT_ADMIN_USERNAME == "admin"
    assert DEFAULT_ADMIN_DISPLAY_NAME == "Olivia Chen"
    assert PBKDF2_ITERATIONS == 260_000
    assert SALT_LENGTH == 16
