"""Centralized configuration management for InstaSparkAI.

Cloud-relevant secrets resolve in this order (first non-empty wins):
``st.secrets``, ``os.environ``, then a local ``.env`` via python-dotenv.
Missing Streamlit secrets must never crash the app.

Local ``streamlit run`` still uses a project-root ``.env``. Streamlit Cloud
Secrets live in ``st.secrets`` and are not the same as ``os.environ``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root is one level up from this file (infra/)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _running_on_streamlit_cloud() -> bool:
    """Skip local dotenv on Cloud so an empty .env cannot blank secrets."""
    return Path("/mount/src").exists()


if not _running_on_streamlit_cloud():
    load_dotenv(_PROJECT_ROOT / ".env")


def _nonempty(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _from_streamlit_secrets(key: str) -> str | None:
    """Read a top-level Streamlit secret. Never raise if secrets are absent."""
    try:
        import streamlit as st

        secrets = st.secrets
        if key in secrets:
            return _nonempty(secrets[key])
        return _nonempty(secrets.get(key))
    except Exception:
        # FileNotFoundError, StreamlitSecretNotFoundError, missing runtime, etc.
        return None


def _from_environ(key: str) -> str | None:
    return _nonempty(os.environ.get(key))


def _resolve_secret(key: str, default: str) -> str:
    """First non-empty value from st.secrets, then os.environ, else default.

    Local dotenv values are already in ``os.environ`` after ``load_dotenv``.
    Whitespace-only values are treated as missing.
    """
    for candidate in (_from_streamlit_secrets(key), _from_environ(key)):
        if candidate is not None:
            return candidate
    return default


def _get_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _get_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


# ─── Application ───────────────────────────────────────────────
APP_NAME: str = _get_str("APP_NAME", "InstaSpark AI")
DEFAULT_LANGUAGE: str = _get_str("DEFAULT_LANGUAGE", "en")

# ─── Database ──────────────────────────────────────────────────
DATABASE_PATH: Path = _PROJECT_ROOT / _get_str("DATABASE_PATH", "data/instaspark.db")
SQLITE_JOURNAL_MODE: str = _get_str("SQLITE_JOURNAL_MODE", "WAL")

# ─── Authentication ────────────────────────────────────────────
PBKDF2_ITERATIONS: int = _get_int("PBKDF2_ITERATIONS", 260_000)
PBKDF2_HASH_ALGORITHM: str = _get_str("PBKDF2_HASH_ALGORITHM", "sha256")
SALT_LENGTH: int = _get_int("SALT_LENGTH", 16)

DEFAULT_ADMIN_USERNAME: str = _get_str("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD: str = _get_str("DEFAULT_ADMIN_PASSWORD", "admin123")
DEFAULT_ADMIN_DISPLAY_NAME: str = _get_str("DEFAULT_ADMIN_DISPLAY_NAME", "Olivia Chen")

DEFAULT_DEMO_USERNAME: str = _get_str("DEFAULT_DEMO_USERNAME", "demo")
DEFAULT_DEMO_PASSWORD: str = _get_str("DEFAULT_DEMO_PASSWORD", "demo123")
DEFAULT_DEMO_DISPLAY_NAME: str = _get_str("DEFAULT_DEMO_DISPLAY_NAME", "Demo Viewer")

# ─── Data File Paths ───────────────────────────────────────────
CREATORS_DATA_PATH: Path = _PROJECT_ROOT / _get_str("CREATORS_DATA_PATH", "data/creators.csv")
MISSION_DATA_PATH: Path = _PROJECT_ROOT / _get_str("MISSION_DATA_PATH", "data/launch_mission.json")
OPPORTUNITIES_DATA_PATH: Path = _PROJECT_ROOT / _get_str(
    "OPPORTUNITIES_DATA_PATH", "data/creator_opportunities.json"
)

# ─── Scoring Weights ───────────────────────────────────────────
SCORE_WEIGHT_CONTENT_FIT: float = _get_float("SCORE_WEIGHT_CONTENT_FIT", 0.30)
SCORE_WEIGHT_AUDIENCE_FIT: float = _get_float("SCORE_WEIGHT_AUDIENCE_FIT", 0.20)
SCORE_WEIGHT_MOMENTUM: float = _get_float("SCORE_WEIGHT_MOMENTUM", 0.15)
SCORE_WEIGHT_COMMERCIAL_FIT: float = _get_float("SCORE_WEIGHT_COMMERCIAL_FIT", 0.15)
SCORE_WEIGHT_BRAND_SAFETY: float = _get_float("SCORE_WEIGHT_BRAND_SAFETY", 0.20)

SCORE_WEIGHTS: dict[str, float] = {
    "content_fit": SCORE_WEIGHT_CONTENT_FIT,
    "audience_fit": SCORE_WEIGHT_AUDIENCE_FIT,
    "momentum": SCORE_WEIGHT_MOMENTUM,
    "commercial_fit": SCORE_WEIGHT_COMMERCIAL_FIT,
    "brand_safety": SCORE_WEIGHT_BRAND_SAFETY,
}

# ─── Opportunity Thresholds ────────────────────────────────────
OPPORTUNITY_HUMAN_REVIEW_THRESHOLD: int = _get_int("OPPORTUNITY_HUMAN_REVIEW_THRESHOLD", 70)
OPPORTUNITY_QUALIFIED_THRESHOLD: int = _get_int("OPPORTUNITY_QUALIFIED_THRESHOLD", 75)
OPPORTUNITY_LOW_CONFIDENCE_THRESHOLD: int = _get_int("OPPORTUNITY_LOW_CONFIDENCE_THRESHOLD", 60)

# ─── External Services ─────────────────────────────────────────
# LLM provider config — supports any OpenAI-compatible API (OpenAI, DeepSeek, etc.)
# Cloud: App settings → Secrets. Local: .env. See _resolve_secret.
LLM_API_KEY: str = _resolve_secret("LLM_API_KEY", "")
LLM_BASE_URL: str = _resolve_secret("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL: str = _resolve_secret("LLM_MODEL", "deepseek-chat")
LLM_MAX_TOKENS: int = _get_int("LLM_MAX_TOKENS", 2000)
LLM_TEMPERATURE: float = _get_float("LLM_TEMPERATURE", 0.7)
FEISHU_APP_ID: str = _get_str("FEISHU_APP_ID", "")
FEISHU_APP_SECRET: str = _get_str("FEISHU_APP_SECRET", "")
YOUTUBE_API_KEY: str = _resolve_secret("YOUTUBE_API_KEY", "")
YOUTUBE_API_TIMEOUT_SECONDS: int = _get_int("YOUTUBE_API_TIMEOUT_SECONDS", 8)
