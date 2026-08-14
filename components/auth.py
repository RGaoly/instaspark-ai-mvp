"""Login page — TikTok Ads / Tokopedia merchant standard.

Split canvas: brand hero on the left, a white form on the right.
Widgets are never wrapped in a decorative HTML card; that pattern is
what produced the empty white box above the old title.
"""

from __future__ import annotations

import streamlit as st

from components.html import esc
from components.i18n import is_zh, t
from infra.auth import init_auth, login
from infra.config import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_DEMO_PASSWORD,
    DEFAULT_DEMO_USERNAME,
)

_LOGIN_CSS = """
<style>
.stApp:has(.auth-hero) [data-testid="stHeader"],
.stApp:has(.auth-hero) [data-testid="stToolbar"],
.stApp:has(.auth-hero) [data-testid="stDecoration"],
.stApp:has(.auth-hero) [data-testid="stSidebar"],
.stApp:has(.auth-hero) [data-testid="stSidebarCollapsedControl"],
.stApp:has(.auth-hero) #MainMenu,
.stApp:has(.auth-hero) footer,
.stApp:has(.auth-hero) .stDeployButton {
  display: none !important;
  visibility: hidden !important;
}
.stApp:has(.auth-hero) {
  background: #FFFFFF !important;
}
.stApp:has(.auth-hero) .block-container {
  max-width: 100% !important;
  padding: 0 !important;
}
.stApp:has(.auth-hero) [data-testid="stHorizontalBlock"]:first-of-type {
  gap: 0 !important;
  min-height: 100vh;
  align-items: stretch;
}
.stApp:has(.auth-hero) [data-testid="stHorizontalBlock"]:first-of-type > div {
  min-width: 0;
}
.stApp:has(.auth-hero) [data-testid="stHorizontalBlock"]:first-of-type > div:last-child {
  background: #FFFFFF;
  padding: 28px 64px 48px;
}
.stApp:has(.auth-hero) [data-testid="stVerticalBlock"] {
  gap: 0.35rem;
}

.auth-hero {
  min-height: 100vh;
  padding: 36px 48px 48px;
  background:
    radial-gradient(1200px 600px at -10% -20%, rgba(255, 214, 0, 0.16), transparent 55%),
    radial-gradient(900px 500px at 110% 110%, rgba(37, 119, 241, 0.18), transparent 50%),
    #06172B;
  color: #FFFFFF;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.auth-hero-mark {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.auth-hero-mark i {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #FFD600;
  color: #111317;
  font-style: normal;
  font-weight: 900;
  display: grid;
  place-items: center;
  font-size: 15px;
}
.auth-hero h1 {
  margin: 72px 0 16px;
  font-size: 40px;
  line-height: 1.12;
  font-weight: 800;
  letter-spacing: -0.035em;
  max-width: 460px;
}
.auth-hero p {
  margin: 0 0 36px;
  max-width: 420px;
  font-size: 15px;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.72);
}
.auth-hero-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  max-width: 460px;
}
.auth-float {
  background: #FFFFFF;
  color: #111317;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
}
.auth-float b {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: #69757E;
  letter-spacing: 0.02em;
  margin-bottom: 6px;
}
.auth-float strong {
  font-size: 22px;
  letter-spacing: -0.03em;
}
.auth-float span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #16A36A;
  font-weight: 650;
}

.auth-form-head {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 48px;
}
.auth-lang a {
  color: #69757E;
  text-decoration: none;
  font-size: 13px;
  font-weight: 650;
  padding: 0 6px;
}
.auth-lang a.active { color: #111317; }
.auth-title {
  font-size: 32px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: -0.035em;
  color: #111317;
  margin: 0 0 10px;
}
.auth-copy {
  font-size: 14px;
  line-height: 1.55;
  color: #69757E;
  margin: 0 0 28px;
  max-width: 420px;
}
.auth-demo {
  margin-top: 18px;
  font-size: 12px;
  line-height: 1.6;
  color: #69757E;
}
.auth-demo b { color: #111317; font-weight: 700; }
.auth-legal {
  margin-top: 28px;
  font-size: 12px;
  line-height: 1.55;
  color: #8A949C;
}

.stApp:has(.auth-hero) .st-key-auth_username,
.stApp:has(.auth-hero) .st-key-auth_password {
  max-width: 440px;
}
.stApp:has(.auth-hero) .st-key-auth_username [data-testid="stTextInput"] label,
.stApp:has(.auth-hero) .st-key-auth_password [data-testid="stTextInput"] label {
  font-size: 14px !important;
  font-weight: 700 !important;
  color: #111317 !important;
  padding-bottom: 4px;
}
.stApp:has(.auth-hero) .st-key-auth_username input,
.stApp:has(.auth-hero) .st-key-auth_password input {
  min-height: 48px !important;
  height: 48px !important;
  border-radius: 8px !important;
  border: 1px solid transparent !important;
  background: #F5F5F5 !important;
  font-size: 15px !important;
  color: #111317 !important;
  padding: 0 14px !important;
}
.stApp:has(.auth-hero) .st-key-auth_username input:focus,
.stApp:has(.auth-hero) .st-key-auth_password input:focus {
  background: #FFFFFF !important;
  border-color: #111317 !important;
  box-shadow: none !important;
}
.stApp:has(.auth-hero) .st-key-auth_submit {
  max-width: 440px;
  margin-top: 8px;
}
.stApp:has(.auth-hero) .st-key-auth_submit button {
  min-height: 48px !important;
  border-radius: 8px !important;
  background: #FFD600 !important;
  color: #111317 !important;
  border: 0 !important;
  font-size: 16px !important;
  font-weight: 750 !important;
  box-shadow: none !important;
}
.stApp:has(.auth-hero) .st-key-auth_submit button:hover {
  background: #F0C800 !important;
  transform: none !important;
}
.stApp:has(.auth-hero) [data-testid="stAlert"] {
  max-width: 440px;
}

@media (max-width: 960px) {
  .stApp:has(.auth-hero) [data-testid="stHorizontalBlock"]:first-of-type > div:first-child {
    display: none;
  }
  .stApp:has(.auth-hero) .block-container {
    padding: 24px 20px 40px !important;
  }
}
</style>
"""


def render_login_page() -> None:
    init_auth()
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    hero, form = st.columns([1.12, 1], gap="small")

    with hero:
        st.markdown(
            f"""
            <div class="auth-hero">
              <div>
                <div class="auth-hero-mark"><i>⚡</i> InstaSpark AI</div>
                <h1>{esc(t("Creator operations for global product launches"))}</h1>
                <p>{esc(t("Match creators, approve with evidence, and run outreach from one workspace."))}</p>
                <div class="auth-hero-cards">
                  <div class="auth-float">
                    <b>{esc(t("Match quality"))}</b>
                    <strong>86</strong>
                    <span>{esc(t("Explainable five-factor score"))}</span>
                  </div>
                  <div class="auth-float">
                    <b>{esc(t("Governance"))}</b>
                    <strong>{esc(t("Human"))}</strong>
                    <span>{esc(t("Every approval leaves an audit trail"))}</span>
                  </div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with form:
        st.markdown(
            f"""
            <div class="auth-form-head">
              <div class="auth-lang" aria-label="Language">
                <a href="?lang=en" target="_top" class="{"active" if not is_zh() else ""}">EN</a>
                <a href="?lang=zh" target="_top" class="{"active" if is_zh() else ""}">中文</a>
              </div>
            </div>
            <div class="auth-title">{esc(t("Log in to your InstaSpark account"))}</div>
            <div class="auth-copy">{esc(t("Enter here to access matching, briefs, outreach and growth review."))}</div>
            """,
            unsafe_allow_html=True,
        )

        st.text_input(
            t("Username"),
            key="auth_username",
            placeholder=t("Enter your username"),
        )
        st.text_input(
            t("Password"),
            key="auth_password",
            type="password",
            placeholder=t("Enter your password"),
        )

        if st.button(t("Log in"), type="primary", use_container_width=True, key="auth_submit"):
            if login(
                st.session_state.get("auth_username", ""),
                st.session_state.get("auth_password", ""),
            ):
                st.rerun()
            else:
                st.error(t("Invalid username or password"))

        st.markdown(
            f"""
            <div class="auth-demo">
              {esc(t("Demo credentials"))}:
              <b>{DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}</b>
              {esc(t("Admin (full access)"))} ·
              <b>{DEFAULT_DEMO_USERNAME} / {DEFAULT_DEMO_PASSWORD}</b>
              {esc(t("Viewer (read-only)"))}
            </div>
            <div class="auth-legal">
              {esc(t("Independent portfolio demo · synthetic data · not affiliated with Insta360."))}
            </div>
            """,
            unsafe_allow_html=True,
        )
