from __future__ import annotations

import streamlit as st

from components.html import ai_badge, avatar, badge, esc, page_header
from components.shell import render_demo_notice, render_topbar
from components.state import active_mission, ranking, select_creator


def _mission_creator_cards(mission, creator) -> str:
    markets = " · ".join(mission.get("markets", ["United States", "Mexico"]))
    return f"""
    <div class="is-studio-card">
      <h4>Mission context</h4>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:7px">
        <div class="is-camera" style="width:32px;height:52px;border-radius:8px"></div>
        <div><b style="font-size:9px">{esc(mission['product'])}</b><br/>{badge('Active','green')}</div>
      </div>
      <p><b>Markets</b><br/>{esc(markets)}</p>
      <p><b>Objective</b><br/>{esc(mission['objective'])}</p>
      <p><b>Budget</b><br/>USD {mission.get('budget_usd',0):,.0f}</p>
    </div>
    <div class="is-studio-card">
      <h4>Creator profile</h4>
      <div class="is-creator-cell" style="margin-bottom:8px">{avatar(creator['creator_name'],3)}
        <span><b>{esc(creator['creator_name'])}</b><small>{esc(creator['primary_market'])}</small></span></div>
      <p><b>Creator tone</b><br/>Energetic, authentic, cinematic, practical.</p>
      <p><b>Common structure</b><br/>Hook → story → proof → CTA</p>
      <p><b>Match score</b><br/>{creator.get('total_score', 0):.0f}/100 · Excellent</p>
    </div>
    <div class="is-studio-card">
      <h4>Platform requirements</h4>
      <div class="is-platform-card" style="margin-bottom:7px;padding:8px">
        <h4><span class="is-platform-icon">IG</span> Instagram Reels</h4>
        <p>9:16 · 15–45s · native captions · #ad</p>
      </div>
      <div class="is-platform-card" style="margin-bottom:7px;padding:8px">
        <h4><span class="is-platform-icon">TT</span> TikTok</h4>
        <p>9:16 · hook in 2s · trending audio OK</p>
      </div>
      <div class="is-platform-card" style="padding:8px">
        <h4><span class="is-platform-icon">YT</span> YouTube Shorts</h4>
        <p>9:16 · 30–60s · end-screen CTA</p>
      </div>
    </div>
    """


def _brief_content(creator) -> str:
    _ = creator
    return f"""
    <div class="is-brief-grid">
      <div class="is-brief-block">
        <h4>Objective</h4>
        <p>Drive awareness and consideration by demonstrating all-day shooting and reframing in a real creator-led adventure.</p>
        <h4 style="margin-top:10px">Audience</h4>
        <p>Action-camera users, outdoor creators and travel storytellers across US + Mexico.</p>
      </div>
      <div class="is-brief-block">
        <h4>Core Message</h4>
        <p>Capture every angle without missing the moment — Insta360 X5 keeps the story open.</p>
        <h4 style="margin-top:10px">Must-Show</h4>
        <ul>
          <li>8K 360 capture in motion</li>
          <li>Reframe / Invisible Selfie Stick</li>
          <li>Low-light or night proof</li>
          <li>Natural creator verdict</li>
        </ul>
      </div>
      <div class="is-brief-block">
        <h4>Shot List</h4>
        <ul>
          <li>Wide establishing shot</li>
          <li>Immersive POV ride / surf</li>
          <li>Subject + environment</li>
          <li>Close-up of key feature</li>
          <li>Reframe reveal example</li>
          <li>CTA end card</li>
        </ul>
      </div>
      <div class="is-brief-block">
        <h4>Do / Don't</h4>
        <p style="color:#16825D">✓ Use natural light<br/>✓ Keep edits cinematic<br/>✓ Show real movement<br/>✓ Disclose paid partnership</p>
        <p style="color:#C83B3B;margin-top:8px">× Do not invent specs<br/>× Avoid competitor claims<br/>× No unsafe stunts</p>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:9px">
      <div class="is-platform-card">
        <h4><span class="is-platform-icon">IG</span> Instagram</h4>
        <ul><li>Primary cut 30s</li><li>Carousel stills optional</li><li>Story stickers for CTA</li></ul>
      </div>
      <div class="is-platform-card">
        <h4><span class="is-platform-icon">TT</span> TikTok</h4>
        <ul><li>Hook in first 2s</li><li>On-screen text EN/ES</li><li>Spark Ads ready</li></ul>
      </div>
      <div class="is-platform-card">
        <h4><span class="is-platform-icon">YT</span> YouTube</h4>
        <ul><li>Shorts + optional mid-roll</li><li>Pinned comment CTA</li><li>Affiliate link in desc</li></ul>
      </div>
    </div>
    <div class="is-localized">
      <div class="is-locale-card">
        <div class="is-locale-head">
          <h4>🇺🇸 United States · English</h4>
          {ai_badge("AI Generated")}
        </div>
        <p><b>Hook</b><br/>All day. All night. All angles. This is the Insta360 X5.</p>
        <p><b>Caption</b><br/>From sunrise rides to city nights, the X5 captures it all in stunning 8K 360.</p>
        <p><b>CTA</b><br/>Tap the link to explore the Insta360 X5.</p>
      </div>
      <div class="is-locale-card">
        <div class="is-locale-head">
          <h4>🇲🇽 Mexico · Español</h4>
          {ai_badge("AI Generated")}
        </div>
        <p><b>Hook</b><br/>Todo el día. Toda la noche. Todos los ángulos.</p>
        <p><b>Caption</b><br/>Desde rutas al amanecer hasta noches en la ciudad, la X5 captura todo en 8K 360.</p>
        <p><b>CTA</b><br/>Toca el enlace para conocer la Insta360 X5.</p>
      </div>
    </div>
    """


def _right_controls() -> str:
    tones = ["Adventurous", "Authentic", "Inspiring", "Innovative"]
    compliance = [
        "Brand safety cleared",
        "Product facts verified",
        "Disclosure guidance attached",
        "Platform format compliant",
    ]
    quality = [
        "Objective aligned to mission",
        "Audience defined",
        "Core message locked",
        "Must-show features listed",
        "Shot list complete",
        "Do / Don't reviewed",
        "Localized US + ES variants",
        "CTA & disclosure present",
    ]
    return f"""
    <div class="is-studio-card">
      <h4>Brand tone</h4>
      <div class="is-tone-row">{''.join(badge(t, 'gray') for t in tones)}</div>
    </div>
    <div class="is-studio-card">
      <h4>Market & language</h4>
      <p><b>Primary</b><br/>🇺🇸 United States · English</p>
      <p><b>Additional</b><br/>🇲🇽 Mexico · Español</p>
    </div>
    <div class="is-studio-card">
      <h4>Safety & compliance {badge('Passed','green')}</h4>
      {''.join(f'<div class="is-check"><i>✓</i>{esc(c)}</div>' for c in compliance)}
    </div>
    <div class="is-studio-card">
      <div class="is-quality-head">
        <h4 style="margin:0">Quality checklist</h4>
        <span class="is-quality-score">8/8</span>
      </div>
      {''.join(f'<div class="is-check"><i>✓</i>{esc(c)}</div>' for c in quality)}
    </div>
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

    head_l, head_r = st.columns([1, 0.55], vertical_alignment="top")
    with head_l:
        st.markdown(
            page_header(
                "Content Studio",
                "Create localized, on-brand content briefs and collaboration materials.",
                None,
            )
            + f'<div style="margin-top:-8px;margin-bottom:10px">{ai_badge("AI Content Studio")}</div>',
            unsafe_allow_html=True,
        )
    with head_r:
        e1, e2, e3 = st.columns(3)
        with e1:
            st.button("Export Brief", use_container_width=True)
        with e2:
            if st.button("Regenerate", use_container_width=True):
                st.session_state.brief_version += 1
                st.toast("New brief version generated")
                st.rerun()
        with e3:
            st.button("Send to Creator", type="primary", use_container_width=True)

    left, center, right = st.columns([0.18, 0.58, 0.24], gap="small", vertical_alignment="top")
    with left:
        st.markdown(_mission_creator_cards(mission, creator), unsafe_allow_html=True)
    with center:
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<span style="font-size:11px;color:#69757E;font-weight:650">'
            f'AI-generated collaboration brief · Version {st.session_state.brief_version}</span>'
            f'{ai_badge("Localized")}</div>',
            unsafe_allow_html=True,
        )
        tabs = st.tabs(["Brief", "Script", "Hooks", "Captions", "Localized variants"])
        with tabs[0]:
            st.markdown(_brief_content(creator), unsafe_allow_html=True)
        with tabs[1]:
            st.markdown(
                '<div class="is-card is-card-pad"><div class="is-card-title">30–60 second script</div>'
                '<div class="is-card-caption" style="margin-top:8px;line-height:1.7">'
                "0–3s: immersive hook. 3–15s: creator challenge. 15–35s: product proof in action. "
                "35–48s: reframing reveal. 48–60s: creator verdict and CTA.</div></div>",
                unsafe_allow_html=True,
            )
        with tabs[2]:
            hooks = [
                "One camera. Every angle.",
                "What if you never missed the shot?",
                "This ride changed after I stopped choosing the frame.",
            ]
            st.markdown(
                '<div class="is-grid-3">'
                + "".join(
                    f'<div class="is-card is-card-pad"><b style="font-size:10px">Hook {i}</b>'
                    f'<div class="is-card-caption" style="margin-top:6px">{esc(text)}</div></div>'
                    for i, text in enumerate(hooks, 1)
                )
                + "</div>",
                unsafe_allow_html=True,
            )
        with tabs[3]:
            st.markdown(
                '<div class="is-card is-card-pad"><div class="is-card-title">Caption variants</div>'
                '<div class="is-card-caption" style="margin-top:8px">'
                "Platform-native captions for TikTok, Instagram Reels and YouTube Shorts, "
                "including disclosure and CTA guidance.</div></div>",
                unsafe_allow_html=True,
            )
        with tabs[4]:
            st.markdown(_brief_content(creator), unsafe_allow_html=True)
    with right:
        st.markdown(_right_controls(), unsafe_allow_html=True)

    render_demo_notice()
