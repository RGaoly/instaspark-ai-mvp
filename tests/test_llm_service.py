"""Tests for the LLM service — mock fallback behavior when no API key is set.

In the test environment, LLM_API_KEY is empty, so all functions
exercise the deterministic fallback paths.
"""

from __future__ import annotations

from services.llm_service import (
    _call_llm,
    _mock_brief,
    _mock_localized_content,
    generate_brief,
    generate_hooks,
    generate_localized_content,
    generate_script,
    is_llm_available,
)


# ─── is_llm_available ──────────────────────────────────────────


def test_llm_not_available_without_key():
    """In test env, no API key is set, so LLM should be unavailable."""
    assert is_llm_available() is False


def test_call_llm_returns_none_without_key():
    """_call_llm should return None when no API key is configured."""
    result = _call_llm("system", "user")
    assert result is None


# ─── generate_brief ────────────────────────────────────────────


def test_generate_brief_returns_string():
    mission = {"product": "Insta360 X5", "market": "United States", "target_topics": ["adventure", "travel"]}
    creator = {"creator_name": "Test Creator"}
    brief = generate_brief(mission, creator)
    assert isinstance(brief, str)
    assert len(brief) > 0


def test_generate_brief_contains_product_name():
    mission = {"product": "Insta360 X5", "market": "United States", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    brief = generate_brief(mission, creator)
    assert "Insta360 X5" in brief


def test_generate_brief_contains_sections():
    mission = {"product": "Insta360 X5", "market": "United States", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    brief = generate_brief(mission, creator)
    assert "Objective" in brief
    assert "Core Message" in brief
    assert "Shot List" in brief


def test_mock_brief_is_deterministic():
    brief1 = _mock_brief("Product A", "US", "adventure", "Creator X")
    brief2 = _mock_brief("Product A", "US", "adventure", "Creator X")
    assert brief1 == brief2


# ─── generate_localized_content ────────────────────────────────


def test_generate_localized_returns_list():
    mission = {"product": "Insta360 X5", "markets": ["United States", "Mexico"]}
    creator = {"creator_name": "Test Creator"}
    result = generate_localized_content(mission, creator)
    assert isinstance(result, list)
    assert len(result) >= 2


def test_generate_localized_has_required_keys():
    mission = {"product": "Insta360 X5", "markets": ["United States", "Mexico"]}
    creator = {"creator_name": "Test Creator"}
    result = generate_localized_content(mission, creator)
    for item in result:
        assert "market" in item
        assert "language" in item
        assert "hook" in item
        assert "caption" in item
        assert "cta" in item
        assert "disclosure" in item


def test_generate_localized_covers_markets():
    mission = {"product": "Insta360 X5", "markets": ["United States", "Mexico"]}
    creator = {"creator_name": "Test Creator"}
    result = generate_localized_content(mission, creator)
    markets = [item["market"] for item in result]
    assert "United States" in markets
    assert "Mexico" in markets


def test_mock_localized_has_different_languages():
    markets = ["United States", "Mexico"]
    configs = {
        "United States": {"language": "English", "flag": "US"},
        "Mexico": {"language": "Espanol", "flag": "MX"},
    }
    result = _mock_localized_content("Product", markets, configs)
    languages = [item["language"] for item in result]
    assert "English" in languages
    assert "Espanol" in languages


# ─── generate_hooks ────────────────────────────────────────────


def test_generate_hooks_returns_list():
    mission = {"product": "Insta360 X5", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    hooks = generate_hooks(mission, creator)
    assert isinstance(hooks, list)
    assert len(hooks) == 3


def test_generate_hooks_are_non_empty_strings():
    mission = {"product": "Insta360 X5", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    hooks = generate_hooks(mission, creator)
    for hook in hooks:
        assert isinstance(hook, str)
        assert len(hook) > 0


# ─── generate_script ───────────────────────────────────────────


def test_generate_script_returns_string():
    mission = {"product": "Insta360 X5", "market": "United States", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    script = generate_script(mission, creator)
    assert isinstance(script, str)
    assert len(script) > 0


def test_generate_script_contains_timestamps():
    mission = {"product": "Insta360 X5", "market": "United States", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    script = generate_script(mission, creator)
    # Mock script should have timestamp-like patterns
    assert "s:" in script or "second" in script.lower()
