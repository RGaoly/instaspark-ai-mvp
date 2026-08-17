"""Tests for the LLM service — mock fallback behavior when no API key is set.

In the test environment, LLM_API_KEY is empty, so all functions
exercise the deterministic fallback paths.
"""

from __future__ import annotations

from services.llm_service import (
    DEFAULT_OUTREACH_TONE,
    _call_llm,
    _grounding_facts,
    _mock_brief,
    _mock_localized_content,
    generate_brief,
    generate_hooks,
    generate_localized_content,
    generate_outreach_message,
    generate_script,
    generation_mode_label,
    is_llm_available,
)


# ─── is_llm_available ──────────────────────────────────────────


def test_llm_not_available_without_key():
    """In test env, no API key is set, so LLM should be unavailable."""
    assert is_llm_available() is False
    assert generation_mode_label() == "Template demo"


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


def test_generate_hooks_are_grounded_in_product():
    mission = {"product": "Insta360 X5", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator"}
    hooks = generate_hooks(mission, creator)
    assert any("Insta360 X5" in hook for hook in hooks)


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


def test_generate_localized_includes_selected_tone_and_checklist():
    mission = {"product": "Insta360 X5", "markets": ["United States", "Mexico"]}
    creator = {"creator_name": "Test Creator", "creator_id": "C017"}
    facts = _grounding_facts(
        mission,
        creator,
        tone="Adventurous",
        checklist=["Paid partnership disclosure"],
    )
    assert "Brand tone: Adventurous" in facts
    assert "Paid partnership disclosure" in facts

    result = generate_localized_content(
        mission,
        creator,
        tone="Adventurous",
        checklist=["Paid partnership disclosure"],
    )
    blob = " ".join(
        f"{item.get('hook', '')} {item.get('caption', '')}" for item in result
    )
    assert "Adventurous" in blob
    assert "Paid partnership disclosure" in blob

    authentic = generate_localized_content(mission, creator, tone="Authentic")
    authentic_blob = " ".join(item.get("hook", "") for item in authentic)
    assert "Authentic" in authentic_blob
    assert authentic_blob != " ".join(item.get("hook", "") for item in result)


def test_generate_brief_grounding_includes_selected_tone_and_checklist():
    mission = {"product": "Insta360 X5", "market": "United States", "target_topics": ["adventure"]}
    creator = {"creator_name": "Test Creator", "creator_id": "C017"}
    facts = _grounding_facts(
        mission,
        creator,
        tone="Adventurous",
        checklist=["Paid partnership disclosure"],
    )
    assert "Brand tone: Adventurous" in facts
    assert "Paid partnership disclosure" in facts

    brief = generate_brief(mission, creator, tone="Adventurous", checklist=["Paid partnership disclosure"])
    assert "Adventurous" in brief
    assert "Paid partnership disclosure" in brief

    hooks = generate_hooks(mission, creator, tone="Adventurous")
    assert any("Adventurous" in hook for hook in hooks)

    script = generate_script(mission, creator, tone="Adventurous", checklist=["Native hook in first 2s"])
    assert "Adventurous" in script
    assert "Native hook in first 2s" in script


def test_generate_outreach_message_template_includes_coupon_utm_and_tone():
    assert is_llm_available() is False
    mission = {
        "product": "Insta360 X5",
        "market": "United States",
        "objective": "Validate product-market fit with creator-led content.",
        "owner": "Olivia Chen",
        "target_topics": ["adventure"],
    }
    creator = {
        "creator_name": "Alex Rivera",
        "creator_id": "C017",
        "primary_market": "United States",
        "topics": ["adventure", "travel"],
    }
    coupon = "X5-C017-ABCDEF"
    deeplink = (
        "https://store.insta360.com/?utm_source=instaspark&utm_medium=creator"
        "&utm_campaign=launch-x5&utm_content=c017&coupon=X5-C017-ABCDEF"
    )
    message = generate_outreach_message(
        mission,
        creator,
        coupon=coupon,
        deeplink=deeplink,
        brief_excerpt="Show the product in a real use case.",
        tone="Adventurous",
    )
    assert coupon in message
    assert deeplink in message
    assert "Adventurous" in message
    assert "Show the product in a real use case." in message
    assert "Insta360 X5" in message
    defaulted = generate_outreach_message(mission, creator, coupon=coupon, deeplink=deeplink)
    assert DEFAULT_OUTREACH_TONE in defaulted
    facts = _grounding_facts(
        mission,
        creator,
        tone="Professional",
        coupon=coupon,
        deeplink=deeplink,
        brief_excerpt="Show the product in a real use case.",
    )
    assert f"Coupon: {coupon}" in facts
    assert f"UTM deeplink: {deeplink}" in facts
