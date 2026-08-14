"""Login page component for InstaSparkAI.

Renders a centered login card with branding, username/password fields,
and demo credential hints. Gates the entire application behind authentication.
"""

from __future__ import annotations

import streamlit as st

from components.i18n import is_zh, t
from infra.auth import init_auth, login
from infra.config import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_DEMO_PASSWORD,
    DEFAULT_DEMO_USERNAME,
)


def render_login_page() -> None:
    """Render the login page. Returns only if login succeeds."""
    init_auth()

    # Inject login page styles compatible with light theme
    st.markdown(
        """
        <style>
        /* Center the login form vertically */
        div.stApp > div > div > div > div {
            padding-top: 2rem;
        }
        /* Login card */
        .auth-card {
            background: #FFFFFF;
            border: 1px solid #E8EAED;
            border-radius: 16px;
            padding: 36px 32px;
            max-width: 400px;
            margin: 0 auto;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
        }
        .auth-logo {
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.03em;
            text-align: center;
            margin-bottom: 4px;
            color: #111317;
        }
        .auth-subtitle {
            font-size: 13px;
            color: #6B7280;
            text-align: center;
            margin-bottom: 24px;
        }
        .auth-hint {
            margin-top: 20px;
            padding: 12px 14px;
            background: #FFF8E1;
            border: 1px solid #FFE082;
            border-radius: 8px;
            font-size: 12px;
            color: #6B7280;
            line-height: 1.7;
        }
        .auth-hint b { color: #F57F17; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    label_login = t("Sign in to InstaSpark AI")
    label_subtitle = t("Creator marketing collaboration workspace")
    label_username = t("Username")
    label_password = t("Password")
    label_button = t("Sign in")
    label_error = t("Invalid username or password")
    label_hint_title = t("Demo credentials")
    label_hint_admin = t("Admin (full access)")
    label_hint_viewer = t("Viewer (read-only)")

    # Use centered column layout
    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)

        st.markdown(
            f'<div class="auth-logo">⚡ InstaSpark AI</div>'
            f'<div class="auth-subtitle">{label_subtitle}</div>',
            unsafe_allow_html=True,
        )

        st.text_input(label_username, key="auth_username", placeholder="admin")
        st.text_input(label_password, key="auth_password", type="password", placeholder="••••••••")

        if st.button(label_button, type="primary", use_container_width=True):
            if login(username := st.session_state.get("auth_username", ""),
                     password := st.session_state.get("auth_password", "")):
                st.rerun()
            else:
                st.error(label_error)

        st.markdown(
            f'<div class="auth-hint">'
            f'<b>{label_hint_title}</b><br/>'
            f'{DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD} — {label_hint_admin}<br/>'
            f'{DEFAULT_DEMO_USERNAME} / {DEFAULT_DEMO_PASSWORD} — {label_hint_viewer}'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('</div>', unsafe_allow_html=True)
