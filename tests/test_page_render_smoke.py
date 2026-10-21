"""Smoke test: every workspace page must render without raising.

Regression coverage for page-level crashes that unit tests miss (e.g. a
local variable shadowing an imported helper inside a view's render path).
Each page is run through Streamlit's AppTest harness with a bootstrapped
demo state and an authenticated admin session.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

PAGES = [
    "views.launch_mission",
    "views.creator_opportunity",
    "views.creator_search",
    "views.creator_compare",
    "views.content_studio",
    "views.outreach_operations",
    "views.growth_review",
]


def _render_page(module_name: str) -> None:
    import importlib

    import streamlit as st

    from components.state import bootstrap_state

    st.session_state.auth_user = {
        "id": 1,
        "username": "admin",
        "display_name": "Admin",
        "role": "admin",
    }
    bootstrap_state()
    module = importlib.import_module(module_name)
    module.render()


@pytest.mark.parametrize("module_name", PAGES)
def test_page_renders_without_exception(module_name: str):
    at = AppTest.from_function(_render_page, args=(module_name,), default_timeout=60)
    at.run()
    assert not at.exception, f"{module_name} raised: {[str(e.value)[:200] for e in at.exception]}"
