from __future__ import annotations

import streamlit as st

from components.shell import render_sidebar
from components.state import bootstrap_state
from components.theme import inject_theme
from views import (
    content_studio,
    creator_compare,
    creator_search,
    growth_review,
    launch_mission,
    outreach_operations,
)


st.set_page_config(
    page_title="InstaSpark AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()
bootstrap_state()

pages = [
    st.Page(launch_mission.render, title="Launch Mission", url_path="launch-mission", default=True),
    st.Page(creator_search.render, title="Creator Search & Match", url_path="creator-search"),
    st.Page(creator_compare.render, title="Creator Compare", url_path="creator-compare"),
    st.Page(content_studio.render, title="Content Studio", url_path="content-studio"),
    st.Page(outreach_operations.render, title="Outreach Operations", url_path="outreach-operations"),
    st.Page(growth_review.render, title="Growth Review", url_path="growth-review"),
]

router = st.navigation(pages, position="hidden")
render_sidebar(pages)
router.run()
