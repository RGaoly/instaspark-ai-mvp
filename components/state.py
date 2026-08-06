from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from src.data_loader import load_creators, load_mission
from src.scoring import rank_creators


ROOT = Path(__file__).resolve().parents[1]
CREATORS_PATH = ROOT / "data" / "creators.csv"
MISSION_PATH = ROOT / "data" / "launch_mission.json"


@st.cache_data(show_spinner=False)
def _load_creators():
    return load_creators(CREATORS_PATH)


@st.cache_data(show_spinner=False)
def _load_default_mission() -> dict[str, Any]:
    return load_mission(MISSION_PATH)


def bootstrap_state() -> None:
    defaults: dict[str, Any] = {
        "mission": {
            **_load_default_mission(),
            "markets": ["US", "Mexico", "Japan"],
            "campaign_dates": "May 12 - Jul 12, 2026",
            "budget_usd": 1_250_000,
            "owner": "Olivia Chen",
            "status": "Active",
            "health_score": 86,
        },
        "shortlist_ids": ["C001", "C003", "C006"],
        "selected_creator_id": "C001",
        "compare_ids": ["C001", "C003", "C006"],
        "decision_log": [],
        "brief_version": 1,
        "outreach_stage": {},
        "show_mission_form": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def creators():
    return _load_creators().copy()


def active_mission() -> dict[str, Any]:
    return dict(st.session_state.mission)


def ranking():
    mission = active_mission()
    score_mission = {
        **mission,
        "market": mission.get("market", "United States"),
        "language": mission.get("language", "English"),
    }
    return rank_creators(creators(), score_mission)


def select_creator(creator_id: str) -> None:
    st.session_state.selected_creator_id = creator_id


def selected_creator() -> dict[str, Any]:
    ranked = ranking()
    if ranked.empty:
        return creators().iloc[0].to_dict()
    selected_id = st.session_state.get("selected_creator_id")
    matches = ranked[ranked["creator_id"] == selected_id]
    if matches.empty:
        return ranked.iloc[0].to_dict()
    return matches.iloc[0].to_dict()


def save_decision(creator_id: str, decision: str, reason: str) -> None:
    st.session_state.decision_log.append(
        {"creator_id": creator_id, "decision": decision, "reason": reason}
    )
    if decision == "Approved" and creator_id not in st.session_state.shortlist_ids:
        st.session_state.shortlist_ids.append(creator_id)
