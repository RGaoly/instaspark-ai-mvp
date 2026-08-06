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
            <div class="is-nav-section">Start from</div>
            """,
            unsafe_allow_html=True,
        )
        for page in pages[:2]:
            st.page_link(page, label=page.title)

        st.markdown('<div class="is-nav-section">Shared workspace</div>', unsafe_allow_html=True)
        for page in pages[2:]:
            st.page_link(page, label=page.title)

        st.markdown(
            """
            <div class="is-toolkit">
              <b>Dual-entry<br/>Operations Toolkit</b>
              <span>Mission-first · Creator-first</span>
              <button>View P0 contract →</button>
            </div>
            <div class="is-support">Need help?<br/><b style="color:#3F4A51">Contact support →</b></div>
            """,
            unsafe_allow_html=True,
        )


def render_topbar() -> None:
    st.markdown(
        """
        <div class="is-topbar">
          <div class="is-search-pill">
            <span class="is-search-icon"></span>
            <span class="is-search-placeholder">Search missions, creators, content...</span>
            <kbd class="is-kbd">⌘K</kbd>
          </div>
          <div class="is-userbar">
            <span class="is-global">◉ &nbsp;Global⌄</span>
            <span class="is-bell" title="Notifications"></span>
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
