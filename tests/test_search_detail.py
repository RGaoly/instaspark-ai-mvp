from views.creator_search import (
    _audience_html,
    _catalog_risks,
    _content_style_html,
    _risk_html,
    _scored_reasons,
    _why_recommended_html,
)


def test_scored_reasons_do_not_pad_defaults():
    assert _scored_reasons({}) == []
    assert _scored_reasons({"positives": ["Topic overlap", ""]}) == ["Topic overlap"]


def test_catalog_risks_use_warnings_or_risks():
    assert _catalog_risks({"warnings": ["日程不确定"]}) == ["日程不确定"]
    assert _catalog_risks({"risks": ["需确认排他"]}) == ["需确认排他"]
    assert _catalog_risks({}) == []


def test_why_tab_does_not_invent_four_reasons():
    html = _why_recommended_html({"positives": ["Topic overlap"], "total_score": 70}, [])
    assert "Topic overlap" in html
    assert "Eligible under the active entry's hard gates" not in html
    assert "Commercial terms require direct confirmation" not in html


def test_style_and_risk_tabs_use_catalog():
    style = _content_style_html({"styles": ["POV", "vlog"], "topics": ["outdoor"]})
    assert "POV, vlog" in style
    assert "outdoor" in style
    empty_risk = _risk_html({})
    assert "No catalog warnings for this creator" in empty_risk
    risk = _risk_html({"warnings": ["需确认竞品合作排他"]})
    assert "需确认竞品合作排他" in risk


def test_audience_tab_shows_overlap_not_unique_reach():
    creator = {"creator_id": "C001", "topics": ["outdoor"], "styles": ["vlog"], "mission_fit": 80}
    html = _audience_html(creator, [creator])
    assert "synthetic cohorts, not platform unique reach" in html
    assert "Mission fit" in html
