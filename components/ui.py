"""Rendering helpers that keep every view on the localization path.

Views render most of their surface as HTML strings. Routing those through
``md`` instead of ``st.markdown`` means a view cannot silently ship
English-only markup.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from components.i18n import localize_text


def md(body: Any, **kwargs: Any) -> None:
    """Render markdown or HTML with the active language applied."""
    st.markdown(localize_text(body), **kwargs)


def labels(values: list[str]) -> list[str]:
    """Localize a list of widget labels, e.g. for ``st.tabs``."""
    return [localize_text(value) for value in values]
