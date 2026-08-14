"""Centralized configuration management for InstaSparkAI.

Loads environment variables from a ``.env`` file at the project root.
All configuration values have sensible defaults so the app runs out-of-the-box
in development, while production deployments can override via environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")


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
LLM_API_KEY: str = _get_str("LLM_API_KEY", "")
LLM_BASE_URL: str = _get_str("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL: str = _get_str("LLM_MODEL", "deepseek-chat")
LLM_MAX_TOKENS: int = _get_int("LLM_MAX_TOKENS", 2000)
LLM_TEMPERATURE: float = _get_float("LLM_TEMPERATURE", 0.7)
FEISHU_APP_ID: str = _get_str("FEISHU_APP_ID", "")
FEISHU_APP_SECRET: str = _get_str("FEISHU_APP_SECRET", "")
