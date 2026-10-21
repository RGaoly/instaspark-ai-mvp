"""Regression test: opening a global-search hit must not crash.

_open_search_hit used to assign st.session_state.global_search after the
search widget was already instantiated in the run, raising
StreamlitWidgetAlreadyInstantiatedError on every "Open" click.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_search_open_switches_page_without_widget_state_error():
    at = AppTest.from_file(str(APP), default_timeout=60)
    for _ in range(3):
        at.run()  # consume bounded cookie retries, reach the login page

    at.text_input(key="auth_username").set_value("admin")
    at.text_input(key="auth_password").set_value("admin123")
    at.button(key="auth_submit").click().run()
    assert at.session_state["auth_user"]["username"] == "admin"

    at.text_input(key="global_search").set_value("Insta360")
    at.run()
    open_buttons = [b for b in at.button if b.label == "Open"]
    assert open_buttons, "expected at least one search result for 'Insta360'"
    open_buttons[0].click().run()

    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    # The deferred clear must have emptied the search box for the next run.
    assert at.session_state["global_search"] == ""
