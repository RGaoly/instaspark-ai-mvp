from __future__ import annotations

import streamlit as st

from components.auth import render_login_page
from components.i18n import set_language
from components.shell import render_sidebar
from components.state import bootstrap_state
from components.theme import inject_theme
from infra.auth import init_auth, init_auth_cookies, is_authenticated
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

# Topbar HTML links still use ?lang=; apply once then drop it so a stale
# zh query cannot pin the session after the operator switches back to EN.
_requested_language = st.query_params.get("lang")
if _requested_language in {"en", "zh"}:
    set_language(_requested_language)
    st.session_state["login_language_switcher"] = _requested_language
    st.session_state["language_switcher"] = _requested_language
    try:
        del st.query_params["lang"]
    except KeyError:
        pass

inject_theme()

# Pin the sidebar open. Streamlit persists the collapsed state in the
# browser's localStorage and, when collapsed, never renders the sidebar
# section — so CSS alone cannot restore it. This hidden same-origin
# component clears any persisted collapsed state, clicks the expand
# button when one is present, and as a last resort reloads the app once
# (safe: the stored state is already cleared, so the next boot renders
# the sidebar). Both chevrons are hidden via CSS in components/theme.py,
# so no new collapse can start. The login page has no sidebar by design
# and is explicitly excluded from the reload path.
st.components.v1.html(
    """
    <script>
    (function () {
      function pinSidebar() {
        try {
          var w = window.parent;
          var doc = w.document;
          var ls = w.localStorage;
          var cleared = false;
          Object.keys(ls).forEach(function (k) {
            if (k.indexOf('stSidebarCollapsed') === 0 && ls.getItem(k) === 'true') {
              ls.setItem(k, 'false');
              cleared = true;
            }
          });
          if (doc.querySelector('[data-testid="stSidebar"]')) return true;
          if (doc.querySelector('.auth-hero')) return true;  // login page: no sidebar by design
          var expand = doc.querySelector('[data-testid="stExpandSidebarButton"]');
          if (expand) {
            var btn = expand.querySelector('button') || expand;
            btn.click();
            return true;
          }
          if (cleared) {
            w.location.reload();
            return true;
          }
          return false;
        } catch (e) { return false; }
      }
      var tries = 0;
      var timer = setInterval(function () {
        tries += 1;
        if (pinSidebar() || tries >= 15) clearInterval(timer);
      }, 800);
    })();
    </script>
    """,
    height=0,
)

init_auth()
init_auth_cookies()

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

st.session_state["_nav_pages"] = {
    "launch-mission": pages[0],
    "creator-opportunity": pages[1],
    "creator-search": pages[2],
    "creator-compare": pages[3],
    "content-studio": pages[4],
    "outreach-operations": pages[5],
    "growth-review": pages[6],
}

router = st.navigation(pages, position="hidden")
render_sidebar(pages)
router.run()
