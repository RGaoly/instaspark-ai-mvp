from __future__ import annotations

from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parents[1]


def test_phase0_routes_exist():
    required = [
        "views/launch_mission.py",
        "views/creator_search.py",
        "views/creator_compare.py",
        "views/content_studio.py",
        "views/outreach_operations.py",
        "views/growth_review.py",
    ]
    for relative in required:
        assert (ROOT / relative).exists(), relative


def test_shared_ui_files_exist():
    required = [
        "components/theme.py",
        "components/shell.py",
        "components/state.py",
        "components/html.py",
        ".streamlit/config.toml",
    ]
    for relative in required:
        assert (ROOT / relative).exists(), relative


def test_python_sources_compile(tmp_path):
    for path in [ROOT / "app.py", *ROOT.glob("components/*.py"), *ROOT.glob("views/*.py")]:
        py_compile.compile(str(path), cfile=str(tmp_path / f"{path.stem}.pyc"), doraise=True)


def test_router_uses_hidden_navigation_and_custom_labels():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.navigation(pages, position="hidden")' in source
    assert 'title="Launch Mission"' in source
    assert 'title="Creator Search & Match"' in source
    assert 'title="Growth Review"' in source


def test_no_duplicate_legacy_pages_navigation():
    assert not (ROOT / "pages").exists(), "Legacy pages/ directory would create duplicate navigation"
    config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert "showSidebarNavigation = false" in config


def test_no_known_invalid_streamlit_icons():
    scanned = [ROOT / "app.py", *ROOT.glob("components/*.py"), *ROOT.glob("views/*.py")]
    invalid = ['icon="✓"', "icon='✓'"]
    for path in scanned:
        source = path.read_text(encoding="utf-8")
        for pattern in invalid:
            assert pattern not in source, f"Invalid icon usage in {path}"


def _assert_label_disabled(source: str, label: str) -> None:
    marker = f't("{label}")'
    assert marker in source, label
    window = source.split(marker, 1)[1][:320]
    assert "disabled=True" in window, f"{label} is still live"


def test_unwired_chrome_buttons_are_disabled():
    search = (ROOT / "views/creator_search.py").read_text(encoding="utf-8")
    studio = (ROOT / "views/content_studio.py").read_text(encoding="utf-8")
    launch = (ROOT / "views/launch_mission.py").read_text(encoding="utf-8")
    compare = (ROOT / "views/creator_compare.py").read_text(encoding="utf-8")
    growth = (ROOT / "views/growth_review.py").read_text(encoding="utf-8")

    _assert_label_disabled(search, "Save Search")
    _assert_label_disabled(search, "Sort: Match score")
    _assert_label_disabled(studio, "Export Brief")
    _assert_label_disabled(studio, "Send to Creator")
    _assert_label_disabled(launch, "Export")
    _assert_label_disabled(compare, "Export")
    _assert_label_disabled(growth, "Export")

    assert "Record performance event (demo)" in growth
    assert "Add data source" not in growth
    assert "record_performance_event" in growth

    assert 'open_workspace_page("content-studio")' in search
    assert 'open_workspace_page("creator-compare")' in search
    assert 'help=t("External send is not wired in this demo")' in studio


def test_honesty_chrome_is_not_hardcoded_pretty():
    launch = (ROOT / "views/launch_mission.py").read_text(encoding="utf-8")
    search = (ROOT / "views/creator_search.py").read_text(encoding="utf-8")
    compare = (ROOT / "views/creator_compare.py").read_text(encoding="utf-8")
    studio = (ROOT / "views/content_studio.py").read_text(encoding="utf-8")

    assert "health_score" not in launch
    assert "<b>Healthy</b>" not in launch
    assert "content_in_review" not in launch
    assert "badge('Verified'" not in search
    assert "Excellent Match" not in search
    assert "is-video" not in search
    assert "match_label" in search
    assert "Modeled est. views" in search
    assert "NL query is a lexical filter + small boost, not semantic search." in search
    assert "Topic overlap" in search
    assert "search_filter_markets" in search
    assert "filter_ranked_creators" in search
    assert "42 + idx * 18" not in compare
    assert "View more content →" not in compare
    assert "2 Medium · 1 High" not in compare
    assert "match_fit_label" in compare
    assert "badge('Passed'" not in studio
    assert "8/8" not in studio
    assert "Not assessed in this demo" in studio
    assert "studio_brand_tone" in studio
    assert "generate_localized_content(grounded, creator, tone=tone, checklist=checklist)" in studio
    assert "save_content_asset" in studio
    assert "content_assets_in_review_count" in launch
    assert "launch_progress" in launch
    assert "Approve creator shortlist" not in launch
    assert "Checklist for this demo" not in launch
    assert "View all (8)" not in launch
    assert "Content brief evidence review" not in launch
    assert "opportunities_for_mission" in launch
    assert "Linked creator opportunities" in launch
    opportunity = (ROOT / "views/creator_opportunity.py").read_text(encoding="utf-8")
    assert "save_opportunity" in opportunity
    assert "_render_mission_link" in opportunity
    assert "health_score" not in opportunity
    growth = (ROOT / "views/growth_review.py").read_text(encoding="utf-8")
    assert "filter_performance_events" in growth
    assert 'key="growth_period"' in growth
    assert 'key="growth_market"' in growth
    assert "campaign_dates" not in growth
