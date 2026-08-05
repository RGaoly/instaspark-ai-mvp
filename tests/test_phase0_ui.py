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
