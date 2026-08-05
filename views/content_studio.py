from __future__ import annotations

import streamlit as st

from components.html import avatar, badge, esc, page_header
from components.shell import render_demo_notice, render_topbar
from components.state import active_mission, ranking, select_creator


def _mission_creator_cards(mission, creator) -> str:
    return f"""
    <div class="is-studio-card">
      <h4>Mission context</h4>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:7px"><div class="is-camera" style="width:32px;height:52px;border-radius:8px"></div><div><b style="font-size:9px">{esc(mission['product'])}</b><br/>{badge('Active','green')}</div></div>
      <p><b>Markets</b><br/>United States · Mexico</p>
      <p><b>Objective</b><br/>{esc(mission['objective'])}</p>
      <p><b>Budget</b><br/>USD {mission.get('budget_usd',0):,.0f}</p>
    </div>
    <div class="is-studio-card">
      <h4>Creator profile</h4>
      <div class="is-creator-cell">{avatar(creator['creator_name'],3)}<span><b>{esc(creator['creator_name'])}</b><small>{esc(creator['primary_market'])}</small></span></div>
      <p><b>Creator tone</b><br/>Energetic, authentic, cinematic, practical.</p>
      <p><b>Common structure</b><br/>Hook → story → proof → CTA</p>
    </div>
    """


def _brief_content(creator) -> str:
    return f"""
    <div class="is-brief-grid">
      <div class="is-brief-block"><h4>Objective</h4><p>Drive awareness and consideration by demonstrating all-day shooting and reframing in a real creator-led adventure.</p><h4>Target audience</h4><p>Action-camera users, outdoor creators and travel storytellers.</p></div>
      <div class="is-brief-block"><h4>Multi-shot scenes</h4><ul><li>Sunrise setup and gear prep</li><li>POV action sequence</li><li>Selfie-stick reveal</li><li>Night or low-light proof</li></ul></div>
      <div class="is-brief-block"><h4>Shot list</h4><ul><li>Wide establishing shot</li><li>Immersive POV</li><li>Subject + environment</li><li>Close-up of key feature</li><li>Reverse example</li></ul></div>
      <div class="is-brief-block"><h4>Do / Don't</h4><p style="color:#16825D">✓ Use natural light<br/>✓ Keep edits cinematic<br/>✓ Show real movement</p><p style="color:#C83B3B">× Do not invent specs<br/>× Avoid competitor claims</p></div>
    </div>
    <div class="is-localized">
      <div class="is-locale-card"><h4>🇺🇸 United States · English</h4><p><b>Hook</b><br/>All day. All night. All angles. This is the Insta360 X5.</p><p><b>Caption</b><br/>From sunrise rides to city nights, the X5 captures it all in stunning 8K 360.</p><p><b>CTA</b><br/>Tap the link to explore the Insta360 X5.</p></div>
      <div class="is-locale-card"><h4>🇲🇽 Mexico · Español</h4><p><b>Hook</b><br/>Todo el día. Toda la noche. Todos los ángulos.</p><p><b>Caption</b><br/>Desde rutas al amanecer hasta noches en la ciudad, la X5 captura todo en 8K 360.</p><p><b>CTA</b><br/>Toca el enlace para conocer la Insta360 X5.</p></div>
    </div>
    """


def _right_controls() -> str:
    checks = ["Brand safety", "Product facts", "Disclosure guidance", "Platform format", "Rights and usage", "CTA clarity"]
    return f"""
    <div class="is-studio-card"><h4>Brand tone</h4><p>{badge('Adventurous','gray')} {badge('Authentic','gray')} {badge('Inspiring','gray')} {badge('Innovative','gray')}</p></div>
    <div class="is-studio-card"><h4>Market & language</h4><p><b>Primary</b><br/>🇺🇸 United States</p><p><b>Additional</b><br/>🇲🇽 Mexico · Spanish</p></div>
    <div class="is-studio-card"><h4>Safety & compliance</h4>{''.join(f'<div class="is-check"><i>✓</i>{c}</div>' for c in checks[:3])}</div>
    <div class="is-studio-card"><h4>Quality checklist</h4>{''.join(f'<div class="is-check"><i>✓</i>{c}</div>' for c in checks)}</div>
    """


def render() -> None:
    render_topbar()
    mission = active_mission()
    ranked = ranking()
    if ranked.empty:
        st.warning("No eligible creators available.")
        return

    creator_names = ranked.head(10)["creator_name"].tolist()
    selected_name = st.selectbox("Creator", creator_names, label_visibility="collapsed")
    creator = ranked[ranked["creator_name"] == selected_name].iloc[0].to_dict()
    select_creator(creator["creator_id"])

    st.markdown(page_header("Content Studio", "Create localized, on-brand content briefs and collaboration materials.", "Content replication"), unsafe_allow_html=True)

    left, center, right = st.columns([0.18, 0.58, 0.24], gap="small", vertical_alignment="top")
    with left:
        st.markdown(_mission_creator_cards(mission, creator), unsafe_allow_html=True)
    with center:
        top_a, top_b, top_c = st.columns([1, 0.2, 0.22])
        with top_a:
            st.caption(f"AI-generated collaboration brief · Version {st.session_state.brief_version}")
        with top_b:
            if st.button("Regenerate", use_container_width=True):
                st.session_state.brief_version += 1
                st.toast("New brief version generated")
                st.rerun()
        with top_c:
            st.button("Send to creator", type="primary", use_container_width=True)
        tabs = st.tabs(["Brief", "Script", "Hooks", "Captions", "Localized variants"])
        with tabs[0]:
            st.markdown(_brief_content(creator), unsafe_allow_html=True)
        with tabs[1]:
            st.markdown('<div class="is-card is-card-pad"><div class="is-card-title">30–60 second script</div><div class="is-card-caption" style="margin-top:8px;line-height:1.7">0–3s: immersive hook. 3–15s: creator challenge. 15–35s: product proof in action. 35–48s: reframing reveal. 48–60s: creator verdict and CTA.</div></div>', unsafe_allow_html=True)
        with tabs[2]:
            st.markdown('<div class="is-grid-3">' + ''.join(f'<div class="is-card is-card-pad"><b style="font-size:10px">Hook {i}</b><div class="is-card-caption" style="margin-top:6px">{text}</div></div>' for i,text in enumerate(["One camera. Every angle.","What if you never missed the shot?","This ride changed after I stopped choosing the frame."],1)) + '</div>', unsafe_allow_html=True)
        with tabs[3]:
            st.markdown('<div class="is-card is-card-pad"><div class="is-card-title">Caption variants</div><div class="is-card-caption" style="margin-top:8px">Platform-native captions for TikTok, Instagram Reels and YouTube Shorts, including disclosure and CTA guidance.</div></div>', unsafe_allow_html=True)
        with tabs[4]:
            st.markdown(_brief_content(creator), unsafe_allow_html=True)
    with right:
        st.markdown(_right_controls(), unsafe_allow_html=True)

    render_demo_notice()
