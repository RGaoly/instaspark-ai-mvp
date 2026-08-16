from __future__ import annotations

import streamlit as st

from components.html import ai_badge, avatar, badge, esc, mission_chip, page_header
from components.i18n import t
from components.shell import render_demo_notice, render_topbar, render_write_guard, writes_locked
from components.state import active_context_label, active_mission, ranking, select_creator
from components.ui import labels, md
from services.llm_service import (
    generate_brief,
    generate_hooks,
    generate_localized_content,
    generate_script,
    generation_mode_label,
    is_llm_available,
)


def _mission_creator_cards(mission, creator) -> str:
    markets = " · ".join(mission.get("markets", ["United States", "Mexico"]))
    return f"""
    <div class="is-studio-card">
      <h4>Active entry context</h4>
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


def _brief_content(mission: dict, creator: dict) -> str:
    product = esc(mission.get("product", "Product"))
    objective = esc(mission.get("objective", "Validate product-market fit with creator-led content."))
    market = esc(mission.get("market", "Target market"))
    language = esc(mission.get("language", "Local language"))
    topics = esc(", ".join(mission.get("target_topics", [])) or "creator-relevant use cases")
    styles = esc(", ".join(mission.get("target_styles", [])) or "the creator's native style")
    return f"""
    <div class="is-brief-grid">
      <div class="is-brief-block">
        <h4>Objective</h4>
        <p>{objective}</p>
        <h4 style="margin-top:10px">Audience</h4>
        <p>{market} audiences interested in {topics}.</p>
      </div>
      <div class="is-brief-block">
        <h4>Core Message</h4>
        <p>Show how {product} supports a credible {styles} story in the creator's own voice.</p>
        <h4 style="margin-top:10px">Must-Show</h4>
        <ul>
          <li>Product in a real use case</li>
          <li>One approved value proposition</li>
          <li>Evidence for every product claim</li>
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
          <h4>{market} · {language}</h4>
          {ai_badge("AI Generated")}
        </div>
        <p><b>Hook</b><br/>A creator-native opening built around {topics}.</p>
        <p><b>Caption</b><br/>See how {product} fits a real {market} use case.</p>
        <p><b>CTA</b><br/>Use the approved campaign link to explore {product}.</p>
      </div>
      <div class="is-locale-card">
        <div class="is-locale-head">
          <h4>Localization guardrail</h4>
          {ai_badge("AI Generated")}
        </div>
        <p><b>Requirement</b><br/>Adapt meaning and cultural references for {market}; do not translate claims that have not been verified.</p>
        <p><b>Evidence</b><br/>Attach the approved product source before external review.</p>
        <p><b>Owner</b><br/>{esc(mission.get('owner', 'Mission owner'))}</p>
      </div>
    </div>
    """


def _right_controls(mission: dict) -> str:
    tones = ["Adventurous", "Authentic", "Inspiring", "Innovative"]
    compliance = [
        "Brand safety cleared",
        "Product facts require source verification",
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
        "Localized market variant",
        "CTA & disclosure present",
    ]
    return f"""
    <div class="is-studio-card">
      <h4>Brand tone</h4>
      <div class="is-tone-row">{''.join(badge(t, 'gray') for t in tones)}</div>
    </div>
    <div class="is-studio-card">
      <h4>Market & language</h4>
      <p><b>Primary</b><br/>{esc(mission.get('market', 'Target market'))} · {esc(mission.get('language', 'Local language'))}</p>
      <p><b>Additional</b><br/>{esc(' · '.join(mission.get('markets', [])[1:]) or 'Not configured')}</p>
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


def _studio_pack(mission: dict, creator: dict) -> dict:
    cache_key = f"{creator['creator_id']}:{st.session_state.get('brief_version', 1)}"
    store = st.session_state.setdefault("_content_studio_cache", {})
    if cache_key not in store:
        store[cache_key] = {
            "brief": generate_brief(mission, creator),
            "script": generate_script(mission, creator),
            "hooks": generate_hooks(mission, creator),
            "localized": generate_localized_content(mission, creator),
            "llm": is_llm_available(),
        }
    return store[cache_key]


def _localized_html(items: list[dict], mission: dict) -> str:
    cards = []
    for item in items:
        cards.append(
            '<div class="is-locale-card">'
            '<div class="is-locale-head">'
            f'<h4>{esc(item.get("market", mission.get("market", "Market")))} · {esc(item.get("language", ""))}</h4>'
            f'{ai_badge(generation_mode_label())}'
            "</div>"
            f'<p><b>Hook</b><br/>{esc(item.get("hook", ""))}</p>'
            f'<p><b>Caption</b><br/>{esc(item.get("caption", ""))}</p>'
            f'<p><b>CTA</b><br/>{esc(item.get("cta", ""))}</p>'
            f'<p><b>Disclosure</b><br/>{esc(item.get("disclosure", "#ad"))}</p>'
            "</div>"
        )
    return '<div class="is-localized">' + "".join(cards) + "</div>"


def render() -> None:
    render_topbar()
    mission = active_mission()
    ranked = ranking()
    if ranked.empty:
        st.warning("Link the active Creator Opportunity to a Launch Mission or choose a mission with eligible creators.")
        return

    creator_names = ranked.head(10)["creator_name"].tolist()
    selected_id = st.session_state.get("selected_creator_id")
    selected_matches = ranked[ranked["creator_id"] == selected_id]
    preferred_name = selected_matches.iloc[0]["creator_name"] if not selected_matches.empty else creator_names[0]
    selected_name = st.selectbox(
        t("Creator"),
        creator_names,
        index=creator_names.index(preferred_name),
        label_visibility="collapsed",
    )
    creator = ranked[ranked["creator_name"] == selected_name].iloc[0].to_dict()
    select_creator(creator["creator_id"])
    pack = _studio_pack(mission, creator)
    mode = generation_mode_label()

    head_l, head_r = st.columns([1, 0.55], vertical_alignment="top")
    with head_l:
        md(
            page_header(
                "Content Studio",
                "Create localized, on-brand content briefs and collaboration materials.",
                None,
            )
            + f'<div style="margin-top:-8px;margin-bottom:10px">{ai_badge(mode)}</div>',
            unsafe_allow_html=True,
        )
        md(mission_chip(active_context_label()), unsafe_allow_html=True)
        st.caption(
            t("Grounded in the active mission")
            + f": {mission.get('product', 'Product')} · {mission.get('market', 'Market')} · "
            + str(mission.get("objective", ""))[:120]
        )
    with head_r:
        e1, e2, e3 = st.columns(3)
        with e1:
            st.button(t("Export Brief"), use_container_width=True)
        with e2:
            if st.button(t("Regenerate"), use_container_width=True):
                st.session_state.brief_version += 1
                st.toast(t("New brief version generated"))
                st.rerun()
        with e3:
            st.button(
                t("Send to Creator"),
                type="primary",
                use_container_width=True,
                disabled=writes_locked(),
            )
        render_write_guard()

    left, center, right = st.columns([0.18, 0.58, 0.24], gap="small", vertical_alignment="top")
    with left:
        md(_mission_creator_cards(mission, creator), unsafe_allow_html=True)
    with center:
        md(
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<span style="font-size:11px;color:#69757E;font-weight:650">'
            f'{esc(mode)} collaboration brief · Version {st.session_state.brief_version}</span>'
            f'{ai_badge(mode)}</div>',
            unsafe_allow_html=True,
        )
        tabs = st.tabs(labels(["Brief", "Script", "Hooks", "Captions", "Localized variants"]))
        with tabs[0]:
            st.markdown(pack["brief"])
        with tabs[1]:
            st.markdown(pack["script"])
        with tabs[2]:
            hooks = pack["hooks"]
            md(
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
            captions = [item.get("caption", "") for item in pack["localized"]]
            if not captions:
                captions = ["No caption generated for this mission yet."]
            md(
                '<div class="is-card is-card-pad"><div class="is-card-title">Caption variants</div>'
                + "".join(
                    f'<div class="is-card-caption" style="margin-top:8px">{esc(text)}</div>'
                    for text in captions
                )
                + "</div>",
                unsafe_allow_html=True,
            )
        with tabs[4]:
            md(_localized_html(pack["localized"], mission), unsafe_allow_html=True)
    with right:
        md(_right_controls(mission), unsafe_allow_html=True)

    render_demo_notice()
