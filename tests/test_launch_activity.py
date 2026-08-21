from views.launch_mission import _activity_html, _activity_rows


def test_activity_rows_newest_first_and_named():
    events = [
        {
            "creator_id": "C001",
            "from_state": "shortlisted",
            "to_state": "approved",
            "reason": "Fit approved",
            "actor": "Olivia Chen",
            "occurred_at": "2026-08-21T10:00:00",
        },
        {
            "creator_id": "C002",
            "from_state": "approved",
            "to_state": "contacted",
            "reason": "Pack sent",
            "actor": "Olivia Chen",
            "occurred_at": "2026-08-21T11:00:00",
        },
    ]
    rows = _activity_rows(events, {"C001": "Maya", "C002": "Leo"}, limit=5)
    assert rows[0][0] == "Leo: approved → contacted"
    assert "Pack sent" in rows[0][1]
    assert rows[1][0] == "Maya: shortlisted → approved"


def test_activity_html_empty_is_honest():
    html = _activity_html([], {})
    assert "No workflow events for this mission yet." in html
    assert "Team notifications" not in html
    assert "State machine active" not in html
