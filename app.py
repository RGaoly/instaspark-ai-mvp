from __future__ import annotations

from pathlib import Path
import csv
import streamlit as st

from src.data_loader import load_creators, load_mission
from src.scoring import rank_creators
from src.brief import generate_brief

ROOT = Path(__file__).parent
CREATORS_PATH = ROOT / "data" / "creators.csv"
MISSION_PATH = ROOT / "data" / "launch_mission.json"
DECISIONS_PATH = ROOT / "data" / "decisions.csv"

st.set_page_config(page_title="InstaSpark AI MVP", layout="wide")
st.title("InstaSpark AI MVP")
st.caption("Evidence-grounded creator matching and localized collaboration brief generation")
st.info("Portfolio demo using synthetic creator data. Not an official Insta360 product.")

base_mission = load_mission(MISSION_PATH)
creators = load_creators(CREATORS_PATH)

with st.sidebar:
    st.header("Launch Mission")
    product = st.text_input("Product", base_mission["product"])
    market = st.selectbox("Market", ["United States", "Mexico"], index=0)
    language = "English" if market == "United States" else "Spanish"
    st.text_input("Language", language, disabled=True)
    max_cost = st.slider("Max creator cost (USD)", 2000, 20000, int(base_mission["max_cost_usd"]), 500)
    min_brand_safety = st.slider("Minimum brand safety", 50, 95, int(base_mission["min_brand_safety"]))
    topics = st.multiselect("Target topics", ["cycling", "surfing", "skiing", "travel", "outdoor", "tech", "motorcycle"], default=base_mission["target_topics"])
    styles = st.multiselect("Target styles", ["POV", "tutorial", "cinematic", "review", "vlog", "comparison"], default=base_mission["target_styles"])

mission = {**base_mission, "product": product, "market": market, "language": language, "max_cost_usd": max_cost, "min_brand_safety": min_brand_safety, "target_topics": topics, "target_styles": styles}
ranked = rank_creators(creators, mission)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Eligible creators", len(ranked))
kpi2.metric("Shortlist", min(10, len(ranked)))
kpi3.metric("Synthetic dataset", len(creators))

st.subheader("Top creators")
if ranked.empty:
    st.warning("No creators passed the current hard gates.")
    st.stop()

top = ranked.head(10).copy()
display_cols = ["creator_name", "primary_market", "followers", "engagement_rate", "estimated_cost_usd", "content_fit", "audience_fit", "momentum", "commercial_fit", "brand_safety", "total_score"]
st.dataframe(top[display_cols], width="stretch", hide_index=True)

selected_name = st.selectbox("Inspect a creator", top["creator_name"].tolist())
selected = top[top["creator_name"] == selected_name].iloc[0].to_dict()
left, right = st.columns([1.2, 1])

with left:
    st.subheader(selected["creator_name"])
    st.write(selected["bio"])
    st.write(f"**Topics:** {', '.join(selected['topics'])}")
    st.write(f"**Styles:** {', '.join(selected['styles'])}")
    st.write(f"**Estimated cost:** ${int(selected['estimated_cost_usd']):,}")
    st.markdown("### Why recommended")
    for item in selected["positives"]:
        st.success(item)
    st.markdown("### Evidence")
    for item in selected["evidence"]:
        st.write(f"- {item}")
    st.markdown("### Risks / open questions")
    for item in selected["warnings"]:
        st.warning(item)

with right:
    st.markdown("### Score breakdown")
    for field, label in [("content_fit", "Content fit"), ("audience_fit", "Audience fit"), ("momentum", "Momentum"), ("commercial_fit", "Commercial fit"), ("brand_safety", "Brand safety")]:
        st.write(f"**{label}: {selected[field]}**")
        st.progress(float(selected[field]) / 100)
    st.markdown("### Human decision")
    decision = st.radio("Decision", ["Approve", "Reject", "Hold"], horizontal=True)
    reason_code = st.selectbox("Reason code", ["Strong content fit", "Strong audience fit", "Budget concern", "Brand safety concern", "Weak evidence", "Availability unknown", "Competitor conflict", "Other"])
    note = st.text_area("Reviewer note")
    if st.button("Save decision"):
        new_file = not DECISIONS_PATH.exists()
        with DECISIONS_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["creator_id", "creator_name", "decision", "reason_code", "note"])
            if new_file:
                writer.writeheader()
            writer.writerow({"creator_id": selected["creator_id"], "creator_name": selected["creator_name"], "decision": decision, "reason_code": reason_code, "note": note})
        st.success("Decision saved to data/decisions.csv")

st.divider()
st.subheader("Localized collaboration brief")
brief = generate_brief(mission, selected)
st.markdown(brief)
st.download_button("Download brief", data=brief, file_name=f"{selected['creator_id']}_{market.replace(' ', '_')}_brief.md", mime="text/markdown")
