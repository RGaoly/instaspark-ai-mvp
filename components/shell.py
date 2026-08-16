from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from components.html import esc
from components.i18n import is_zh, lhtml, set_language, t
from components.search import search_workspace
from components.state import (
    creators,
    missions,
    opportunity_records,
    reset_demo,
    select_creator,
    set_active_context,
)
from infra.auth import can_write, current_display_name, current_role, logout

_KIND_LABELS = {
    "mission": "Mission",
    "opportunity": "Opportunity",
    "creator": "Creator",
}


def _sync_language_switcher() -> None:
    selected = st.session_state.get("language_switcher")
    if selected in {"en", "zh"}:
        set_language(selected)


def render_sidebar(pages: Sequence[st.Page]) -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="is-sidebar-brand">
              <div class="is-sidebar-logo">InstaSpark AI<small>for Insta360</small></div>
            </div>
            <div class="is-nav-section">{t("Language")}</div>
            """,
            unsafe_allow_html=True,
        )

        language = st.segmented_control(
            t("Language"),
            options=["en", "zh"],
            format_func=lambda code: "EN" if code == "en" else "中文",
            default="zh" if is_zh() else "en",
            label_visibility="collapsed",
            key="language_switcher",
            on_change=_sync_language_switcher,
        )
        if language and language != st.session_state.language:
            set_language(language)
            st.rerun()

        st.markdown(
            f'<div class="is-nav-section">{t("Start from")}</div>',
            unsafe_allow_html=True,
        )
        for page in pages[:2]:
            st.page_link(page, label=t(page.title))

        st.markdown(
            f'<div class="is-nav-section">{t("Shared workspace")}</div>',
            unsafe_allow_html=True,
        )
        for page in pages[2:]:
            st.page_link(page, label=t(page.title))

        if st.button(
            t("Reset demo"),
            use_container_width=True,
            key="reset_demo",
            disabled=not can_write(),
        ):
            reset_demo()
            st.toast(t("Demo reset to the opening state"))
            st.rerun()
        if not can_write():
            st.caption(t("Viewer role is read-only. Sign in as admin to approve, save, or advance workflow."))

        if st.button(t("Sign out"), use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()

        st.markdown(
            lhtml(
                """
                <div class="is-toolkit">
                  <b>Dual-entry<br/>Operations Toolkit</b>
                  <span>Mission-first · Creator-first</span>
                </div>
                """
            )
            + f'<div class="is-support">{t("Need help?")}<br/>'
            f'<b style="color:#3F4A51">{t("Contact support →")}</b></div>',
            unsafe_allow_html=True,
        )


def _open_search_hit(hit: dict) -> None:
    if hit["kind"] == "mission":
        set_active_context("launch_mission", hit["id"])
    elif hit["kind"] == "opportunity":
        set_active_context("creator_opportunity", hit["id"])
    else:
        select_creator(hit["id"])
    st.session_state.global_search = ""
    page = (st.session_state.get("_nav_pages") or {}).get(hit["page"])
    if page is not None:
        st.switch_page(page)


def render_topbar() -> None:
    display_name = current_display_name()
    initials = "".join(word[0] for word in display_name.split() if word)[:2].upper() or "?"
    role_label = t("Global Marketing") if current_role() == "admin" else t("Viewer")
    language_links = (
        '<div class="is-top-language" aria-label="Language">'
        f'<a href="?lang=en" target="_top" class="{"active" if not is_zh() else ""}">EN</a>'
        f'<a href="?lang=zh" target="_top" class="{"active" if is_zh() else ""}">中文</a></div>'
    )
    search_col, user_col = st.columns([1.55, 1], vertical_alignment="center")
    with search_col:
        query = st.text_input(
            "Workspace search",
            key="global_search",
            placeholder=t("Search missions, creators, content..."),
            label_visibility="collapsed",
        )
    with user_col:
        st.markdown(
            f"""
            <div class="is-userbar">
              {language_links}
              <span class="is-global">◉ &nbsp;{t("Global")}⌄</span>
              <span class="is-bell" title="{t('Notifications')}"></span>
              <span class="is-avatar">{esc(initials)}</span>
              <span><span class="is-user-name">{esc(display_name)}</span><span class="is-user-role">{role_label}</span></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    needle = str(query or "").strip()
    if not needle:
        return

    hits = search_workspace(
        needle,
        creators=creators(),
        missions=missions(),
        opportunities=opportunity_records(),
    )
    with st.container(border=True):
        if not hits:
            st.caption(t("No matches for this search"))
        for hit in hits:
            kind = t(_KIND_LABELS.get(hit["kind"], hit["kind"]))
            action, body = st.columns([0.16, 1], vertical_alignment="center")
            with action:
                if st.button(t("Open"), key=f"gs_{hit['kind']}_{hit['id']}", use_container_width=True):
                    _open_search_hit(hit)
            with body:
                st.markdown(
                    f'<div class="is-search-hit"><b>{esc(kind)}</b>'
                    f'<span class="is-search-hit-title">{esc(hit["title"])}</span>'
                    f'<span class="is-search-hit-sub">{esc(hit["subtitle"])}</span></div>',
                    unsafe_allow_html=True,
                )


def render_demo_notice() -> None:
    st.caption(
        t(
            "Independent portfolio demo · synthetic creator and performance data · "
            "not affiliated with or deployed at Insta360."
        )
    )


def writes_locked() -> bool:
    return not can_write()


def render_write_guard() -> None:
    if writes_locked():
        st.caption(t("Viewer role is read-only. Sign in as admin to approve, save, or advance workflow."))
