from views.content_studio import (
    NOT_IN_CATALOG,
    _catalog_join,
    _mission_creator_cards,
    _platform_requirements_html,
)


def test_catalog_join_lists_and_empty():
    assert _catalog_join(["POV", "vlog"]) == "POV, vlog"
    assert _catalog_join("travel|tech") == "travel, tech"
    assert _catalog_join([]) == NOT_IN_CATALOG
    assert _catalog_join(None) == NOT_IN_CATALOG


def test_creator_profile_uses_catalog_styles_not_canned_tone():
    mission = {
        "product": "Insta360 X5",
        "markets": ["United States"],
        "objective": "Launch X5",
        "budget_usd": 80000,
    }
    maya = {
        "creator_name": "Maya Outdoors",
        "primary_market": "United States",
        "styles": ["vlog", "review"],
        "topics": ["cycling", "outdoor"],
        "total_score": 81,
    }
    alex = {
        "creator_name": "Alex Rides",
        "primary_market": "Mexico",
        "styles": ["POV"],
        "topics": ["travel", "tech"],
        "total_score": 74,
    }
    maya_html = _mission_creator_cards(mission, maya)
    alex_html = _mission_creator_cards(mission, alex)
    assert "vlog, review" in maya_html
    assert "cycling, outdoor" in maya_html
    assert "POV" in alex_html
    assert "travel, tech" in alex_html
    assert "Energetic, authentic, cinematic, practical." not in maya_html
    assert "Hook → story → proof → CTA" not in maya_html
    assert "No platform fields in the demo catalog" in maya_html
    assert "Instagram Reels" not in maya_html
    assert "TikTok" not in maya_html
    assert "Need-show visual proof from" not in maya_html
    assert "Product DNA shot list" in maya_html
    assert "dna_x5_v1" in maya_html


def test_platform_requirements_use_catalog_and_live_evidence():
    empty = _platform_requirements_html({"creator_name": "Maya"}, [])
    assert "No platform fields in the demo catalog" in empty
    assert "Instagram Reels" not in empty
    catalog = _platform_requirements_html({"platforms": ["YouTube"]}, [])
    assert "YouTube" in catalog
    assert "From catalog" in catalog
    live = _platform_requirements_html(
        {},
        [{"source": "youtube_data_api", "url": "https://www.youtube.com/channel/UC1", "title": "Maya"}],
    )
    assert "YouTube" in live
    assert "Attached as live evidence" in live
