from __future__ import annotations

import streamlit as st

from components.auth import render_login_page
from components.i18n import set_language
from components.shell import render_sidebar
from components.state import bootstrap_state
from components.theme import inject_theme
from infra.auth import init_auth, is_authenticated
from infra.config import DEFAULT_LANGUAGE
from views import (
    content_studio,
    creator_compare,
    creator_opportunity,
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

if "language" not in st.session_state:
    st.session_state.language = DEFAULT_LANGUAGE

# The topbar switches language via ?lang= so it works inside the HTML shell.
_requested_language = st.query_params.get("lang")
if _requested_language in {"en", "zh"}:
    set_language(_requested_language)
    st.query_params.clear()

inject_theme()
init_auth()

if not is_authenticated():
    render_login_page()
    st.stop()

bootstrap_state()

# Page titles stay canonical English so routes and the P0 contract are stable;
# the sidebar localizes the visible label instead.
pages = [
    st.Page(launch_mission.render, title="Launch Mission", url_path="launch-mission", default=True),
    st.Page(creator_opportunity.render, title="Creator Opportunity", url_path="creator-opportunity"),
    st.Page(creator_search.render, title="Creator Search & Match", url_path="creator-search"),
    st.Page(creator_compare.render, title="Creator Compare", url_path="creator-compare"),
    st.Page(content_studio.render, title="Content Studio", url_path="content-studio"),
    st.Page(outreach_operations.render, title="Outreach Operations", url_path="outreach-operations"),
    st.Page(growth_review.render, title="Growth Review", url_path="growth-review"),
]

router = st.navigation(pages, position="hidden")
render_sidebar(pages)
router.run()
