from views.creator_compare import _compare_grid, open_search_youtube_lookup, resolve_compare_focus
import pandas as pd


def test_resolve_compare_focus_keeps_selected_when_in_set():
    assert resolve_compare_focus(["C002", "C001", "C003"], "C001") == "C001"
    assert resolve_compare_focus(["C002", "C001"], "C009") == "C002"
    assert resolve_compare_focus([], "C001") is None


def test_compare_grid_marks_focused_column_not_first():
    rows = pd.DataFrame(
        [
            {
                "creator_id": "C001",
                "creator_name": "Alex",
                "total_score": 70,
                "topics": ["travel"],
                "followers": 1000,
                "engagement_rate": 2.0,
                "brand_safety": 80,
                "estimated_cost_usd": 1000,
                "posting_consistency": 0.5,
                "historical_reliability": 0.5,
                "primary_market": "Mexico",
                "markets": ["Mexico"],
            },
            {
                "creator_id": "C002",
                "creator_name": "Sofia",
                "total_score": 85,
                "topics": ["tech"],
                "followers": 2000,
                "engagement_rate": 3.0,
                "brand_safety": 80,
                "estimated_cost_usd": 2000,
                "posting_consistency": 0.5,
                "historical_reliability": 0.5,
                "primary_market": "United States",
                "markets": ["United States"],
            },
        ]
    )
    html = _compare_grid(rows, "C002")
    assert "2 creators selected" in html
    assert html.count("is-compare-head selected") == 1
    assert html.index("Alex") < html.index("is-compare-head selected")


def test_open_search_youtube_lookup_opens_search_expander(monkeypatch):
    from views import creator_compare

    fake = {}
    opened = []
    monkeypatch.setattr(creator_compare.st, "session_state", fake)
    monkeypatch.setattr(creator_compare, "open_workspace_page", lambda page: opened.append(page))

    open_search_youtube_lookup()

    assert fake["search_youtube_open"] is True
    assert opened == ["creator-search"]
