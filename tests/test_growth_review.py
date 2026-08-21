from views.growth_review import _creator_label, _needs_conversion, _needs_outreach, _performance_table


def test_creator_label_prefers_name():
    assert _creator_label("C001", {"C001": "Maya Chen"}) == "Maya Chen · C001"
    assert _creator_label("C001", {}) == "C001"
    assert _creator_label("C001", {"C001": "C001"}) == "C001"


def test_needs_outreach_excludes_measured_only():
    assert _needs_outreach({"approved": 1})
    assert _needs_outreach({"contacted": 1, "measured": 2})
    assert not _needs_outreach({"measured": 2})
    assert not _needs_outreach({})


def test_needs_conversion_only_when_events_empty():
    assert _needs_conversion({"published": 1}, [], [])
    assert _needs_conversion({}, [], [{"creator_id": "C001"}])
    assert not _needs_conversion({"published": 1}, [{"orders": 1}], [{"creator_id": "C001"}])


def test_performance_table_shows_creator_name():
    html = _performance_table(
        [
            {
                "creator_id": "C001",
                "content_asset_id": "A1",
                "market": "US",
                "recorded_at": "2026-08-21T10:00:00",
                "orders": 2,
                "revenue_usd": 100,
                "spend_usd": 40,
            }
        ],
        {"C001": "Maya Chen"},
    )
    assert "Maya Chen · C001" in html
    assert "2026-08-21" in html
