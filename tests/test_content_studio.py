from views.content_studio import NOT_IN_CATALOG, _catalog_join, _mission_creator_cards


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
    assert "Demo format assumptions, not creator fields" in maya_html
    assert maya_html != alex_html
