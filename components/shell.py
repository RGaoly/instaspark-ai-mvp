from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from components.html import esc


def render_sidebar(pages: Sequence[st.Page]) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="is-sidebar-brand">
              <div class="is-sidebar-logo">InstaSpark AI<small>for Insta360</small></div>
            </div>
            <div class="is-nav-section">Workspace</div>
            """,
            unsafe_allow_html=True,
        )
        for page in pages:
            st.page_link(page, label=page.title)

        st.markdown(
            """
            <div class="is-toolkit">
              <b>Insta360 X5<br/>Launch Toolkit</b>
              <span>US · Mexico creator pilot</span>
              <button>View toolkit →</button>
            </div>
            <div class="is-support">Need help?<br/><b style="color:#3F4A51">Contact support →</b></div>
            """,
            unsafe_allow_html=True,
        )


def render_topbar() -> None:
    st.markdown(
        """
        <div class="is-topbar">
          <div class="is-search"><span class="is-search-icon"></span>Search missions, creators, content...</div>
          <div class="is-userbar">
            <span>◉ &nbsp;Global⌄</span>
            <span class="is-bell"></span>
            <span class="is-avatar">OC</span>
            <span><span class="is-user-name">Olivia Chen</span><span class="is-user-role">Global Marketing</span></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_demo_notice() -> None:
    st.caption(
        "Independent portfolio demo · synthetic creator and performance data · not affiliated with or deployed at Insta360."
    )
