from __future__ import annotations

import streamlit as st


TOKENS = {
    "ink": "#111317",
    "navy": "#06172B",
    "navy_2": "#10263B",
    "yellow": "#FFD600",
    "yellow_soft": "#FFF5BF",
    "page": "#F3F7F8",
    "surface": "#FFFFFF",
    "surface_2": "#F8FAFB",
    "line": "#DCE4E7",
    "muted": "#69757E",
    "green": "#16A36A",
    "green_soft": "#E9F8F1",
    "blue": "#2577F1",
    "blue_soft": "#EAF2FF",
    "orange": "#F5A623",
    "orange_soft": "#FFF4E4",
    "red": "#E04A4A",
    "red_soft": "#FFF0F0",
}


def inject_theme() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
          --ink: {TOKENS['ink']};
          --navy: {TOKENS['navy']};
          --navy-2: {TOKENS['navy_2']};
          --yellow: {TOKENS['yellow']};
          --yellow-soft: {TOKENS['yellow_soft']};
          --page: {TOKENS['page']};
          --surface: {TOKENS['surface']};
          --surface-2: {TOKENS['surface_2']};
          --line: {TOKENS['line']};
          --muted: {TOKENS['muted']};
          --green: {TOKENS['green']};
          --green-soft: {TOKENS['green_soft']};
          --blue: {TOKENS['blue']};
          --blue-soft: {TOKENS['blue_soft']};
          --orange: {TOKENS['orange']};
          --orange-soft: {TOKENS['orange_soft']};
          --red: {TOKENS['red']};
          --red-soft: {TOKENS['red_soft']};
          --radius: 14px;
          --radius-sm: 10px;
          --shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 8px 24px rgba(14, 31, 43, 0.045);
          --shadow-hover: 0 2px 4px rgba(16, 24, 40, 0.06), 0 14px 32px rgba(14, 31, 43, 0.08);
          --ease: cubic-bezier(0.22, 1, 0.36, 1);
        }}

        html, body, [class*="css"] {{
          font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
                       "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
          -webkit-font-smoothing: antialiased;
          text-rendering: optimizeLegibility;
        }}

        .stApp {{ background: var(--page); color: var(--ink); }}
        .stApp * {{ box-sizing: border-box; }}

        [data-testid="stHeader"] {{
          background: transparent;
          height: 0;
        }}
        [data-testid="stToolbar"] {{ display: none; }}
        #MainMenu, footer {{ visibility: hidden; }}

        .block-container {{
          max-width: 1480px;
          padding: 18px 28px 48px 28px;
        }}

        [data-testid="stSidebar"] {{
          background: #FFFFFF;
          border-right: 1px solid var(--line);
          min-width: 228px !important;
          max-width: 228px !important;
        }}
        [data-testid="stSidebar"] > div:first-child {{
          padding-top: 14px;
        }}
        [data-testid="stSidebar"] .block-container {{ padding: 0; }}
        [data-testid="stSidebarNav"] {{ display: none; }}

        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
          min-height: 38px;
          border-radius: 10px;
          padding: 8px 12px;
          color: #5B6670;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: -0.01em;
          transition: background .18s var(--ease), color .18s var(--ease), transform .18s var(--ease);
        }}
        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
          background: #F1F4F5;
          color: var(--ink);
          transform: translateX(1px);
        }}
        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
          background: #EEF1F2;
          color: var(--ink);
          font-weight: 800;
          box-shadow: inset 3px 0 0 var(--yellow);
        }}

        [data-testid="stSidebar"] hr {{
          margin: 13px 0;
          border-color: var(--line);
        }}

        .is-sidebar-brand {{
          padding: 8px 10px 12px 10px;
        }}
        .is-sidebar-logo {{
          color: var(--ink);
          font-weight: 950;
          font-size: 20px;
          letter-spacing: -0.05em;
          line-height: 1;
        }}
        .is-sidebar-logo small {{
          display: block;
          font-size: 8px;
          letter-spacing: .01em;
          font-weight: 700;
          margin-top: 3px;
          color: #56616A;
        }}
        .is-nav-section {{
          color: #9AA3AA;
          font-size: 9px;
          font-weight: 850;
          letter-spacing: .12em;
          text-transform: uppercase;
          padding: 2px 11px 6px 11px;
        }}
        .is-toolkit {{
          margin: 15px 7px 8px;
          padding: 13px;
          min-height: 130px;
          border-radius: 11px;
          color: white;
          background:
            radial-gradient(circle at 85% 20%, rgba(255,255,255,.28), transparent 26%),
            linear-gradient(145deg, #3A7BE8 0%, #4EA8EA 48%, #193D75 100%);
          box-shadow: inset 0 0 0 1px rgba(255,255,255,.18);
          overflow: hidden;
          position: relative;
        }}
        .is-toolkit:after {{
          content: "";
          position: absolute;
          width: 88px;
          height: 88px;
          border: 10px solid rgba(255,255,255,.24);
          border-radius: 50%;
          right: -20px;
          bottom: -25px;
        }}
        .is-toolkit b {{ font-size: 13px; display: block; line-height: 1.35; }}
        .is-toolkit span {{ font-size: 10px; opacity: .82; }}
        .is-toolkit button {{
          margin-top: 34px;
          background: white;
          color: #1B2630;
          border: 0;
          border-radius: 6px;
          padding: 6px 9px;
          font-size: 9px;
          font-weight: 800;
        }}
        .is-support {{
          color: #6F7A82;
          font-size: 10px;
          padding: 4px 11px 14px;
        }}

        .is-topbar {{
          height: 56px;
          display: grid;
          grid-template-columns: minmax(320px, 1fr) auto;
          align-items: center;
          gap: 20px;
          margin: -4px 0 20px;
          padding-bottom: 14px;
          border-bottom: 1px solid var(--line);
        }}
        .is-search-pill {{
          max-width: 520px;
          height: 40px;
          padding: 0 12px 0 14px;
          color: #8A949C;
          font-size: 13px;
          display: flex;
          align-items: center;
          gap: 10px;
          background: #F8FAFB;
          border: 1px solid #E3E8EB;
          border-radius: 12px;
          transition: border-color .18s var(--ease), box-shadow .18s var(--ease), background .18s var(--ease);
        }}
        .is-search-pill:hover {{
          border-color: #C9D3D8;
          background: #FFFFFF;
          box-shadow: 0 0 0 3px rgba(37, 119, 241, 0.08);
        }}
        .is-search-placeholder {{ flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .st-key-global_search {{
          max-width: 560px;
          margin: -4px 0 8px;
        }}
        .st-key-global_search [data-testid="stTextInput"] input {{
          height: 40px !important;
          min-height: 40px !important;
          border-radius: 12px !important;
          border: 1px solid #E3E8EB !important;
          background-color: #F8FAFB !important;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='15' height='15' fill='none' stroke='%238A949C' stroke-width='1.8'%3E%3Ccircle cx='6.5' cy='6.5' r='5.2'/%3E%3Cpath d='M10.4 10.4L13.5 13.5' stroke-linecap='round'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: 14px 50%;
          background-size: 15px 15px;
          font-size: 13px !important;
          padding-left: 38px !important;
        }}
        .st-key-global_search [data-testid="stTextInput"] input:focus {{
          background-color: #FFFFFF !important;
          border-color: #C9D3D8 !important;
          box-shadow: 0 0 0 3px rgba(37, 119, 241, 0.08) !important;
        }}
        .is-search-hit {{
          display: flex;
          flex-direction: column;
          gap: 2px;
          padding: 2px 0 4px;
        }}
        .is-search-hit b {{
          font-size: 9px;
          letter-spacing: .04em;
          text-transform: uppercase;
          color: #8A949C;
        }}
        .is-search-hit-title {{ font-size: 13px; font-weight: 700; color: #111317; }}
        .is-search-hit-sub {{ font-size: 11px; color: #69757E; }}
        .is-kbd {{
          flex: 0 0 auto;
          min-width: 34px;
          height: 22px;
          padding: 0 7px;
          border-radius: 7px;
          border: 1px solid #E3E8EB;
          background: #FFFFFF;
          color: #8A949C;
          font-family: inherit;
          font-size: 11px;
          font-weight: 700;
          display: inline-flex;
          align-items: center;
          justify-content: center;
        }}
        .is-search-icon {{
          width: 15px; height: 15px; border: 1.8px solid #8A949C; border-radius: 50%; position: relative; flex: 0 0 15px;
        }}
        .is-search-icon:after {{
          content: ""; width: 6px; height: 1.8px; background: #8A949C; position: absolute;
          right: -5px; bottom: -2px; transform: rotate(45deg); border-radius: 4px;
        }}
        .is-userbar {{ display:flex; align-items:center; gap:14px; color:#58636B; font-size:12px; }}
        .is-global {{
          padding: 6px 10px;
          border-radius: 9px;
          border: 1px solid transparent;
          transition: background .16s var(--ease), border-color .16s var(--ease);
        }}
        .is-global:hover {{ background: #F1F4F5; border-color: #E3E8EB; }}
        .is-bell {{ position:relative; width:16px; height:16px; border:1.5px solid #6C7880; border-radius:8px 8px 5px 5px; cursor:pointer; }}
        .is-bell:after {{ content:""; width:6px; height:6px; background:var(--yellow); border-radius:50%; position:absolute; right:-4px; top:-3px; box-shadow:0 0 0 2px #fff; }}
        .is-avatar {{
          width:32px; height:32px; border-radius:50%; display:grid; place-items:center;
          background:linear-gradient(135deg,#EFC9A8,#8C4D30); color:white; font-weight:850; font-size:11px;
          box-shadow:0 0 0 2px white, 0 0 0 3px #D9E0E3;
        }}
        .is-user-name {{ font-weight:800; color:#20262B; line-height:1.15; }}
        .is-user-role {{ font-size:10px; color:#8B949A; line-height:1.2; }}

        .is-page-head {{
          display:flex;
          justify-content:space-between;
          align-items:flex-start;
          gap:20px;
          margin-bottom:14px;
        }}
        .is-page-title {{
          font-size: 28px;
          font-weight: 900;
          letter-spacing: -0.04em;
          line-height: 1.08;
          margin: 0;
        }}
        .is-page-subtitle {{
          margin-top:6px;
          color:var(--muted);
          font-size:13px;
          line-height:1.5;
        }}
        .is-badge {{
          display:inline-flex;
          align-items:center;
          min-height:22px;
          padding:3px 8px;
          border-radius:999px;
          font-size:9px;
          font-weight:850;
          letter-spacing:.02em;
        }}
        .is-badge-yellow {{ background:var(--yellow); color:var(--ink); }}
        .is-badge-green {{ background:var(--green-soft); color:#16805A; }}
        .is-badge-blue {{ background:var(--blue-soft); color:#1F67CF; }}
        .is-badge-gray {{ background:#EEF2F3; color:#66727A; }}
        .is-badge-orange {{ background:var(--orange-soft); color:#B56B00; }}
        .is-badge-red {{ background:var(--red-soft); color:#C83B3B; }}

        .is-card {{
          background:var(--surface);
          border:1px solid var(--line);
          border-radius:var(--radius);
          box-shadow:var(--shadow);
          transition: box-shadow .22s var(--ease), transform .22s var(--ease), border-color .22s var(--ease);
        }}
        .is-card:hover {{
          box-shadow: var(--shadow-hover);
          border-color: #D0DADF;
        }}
        .is-card-flat {{ box-shadow:none; }}
        .is-card-pad {{ padding:14px 15px; }}
        .is-card-title {{ font-size:13px; font-weight:850; color:#20262B; letter-spacing:-0.01em; }}
        .is-card-caption {{ color:var(--muted); font-size:11px; line-height:1.45; }}
        .is-scope-note {{
          background:#F7FBFF;
          border:1px solid #D6E6F8;
          border-radius:var(--radius);
          padding:14px 16px 12px;
          margin:0 0 14px;
        }}
        .is-scope-note.compact {{ padding:10px 12px; margin:8px 0 0; }}
        .is-scope-kicker {{
          font-size:10px; font-weight:800; letter-spacing:.04em; color:#1F67CF; text-transform:uppercase;
        }}
        .is-scope-note h4 {{
          margin:6px 0 8px; font-size:14px; letter-spacing:-0.02em; color:#1A2025;
        }}
        .is-scope-note ul {{ margin:0; padding-left:16px; }}
        .is-scope-note li {{
          font-size:12px; line-height:1.45; color:#4A565E; margin:0 0 6px;
        }}
        .is-scope-note li b {{ color:#1A2025; }}
        .is-scope-note small {{ display:block; margin-top:6px; color:#69757E; font-size:11px; }}

        .is-metric-grid {{
          display:grid;
          grid-template-columns:repeat(6,minmax(0,1fr));
          gap:10px;
          margin:4px 0 14px;
        }}
        .is-metric {{
          background:white;
          border:1px solid var(--line);
          border-radius:var(--radius);
          padding:14px 14px 12px;
          min-height:108px;
          box-shadow:var(--shadow);
          transition: box-shadow .22s var(--ease), transform .22s var(--ease), border-color .22s var(--ease);
        }}
        .is-metric:hover {{
          transform: translateY(-2px);
          box-shadow: var(--shadow-hover);
          border-color: #D0DADF;
        }}
        .is-metric-top {{
          display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px;
        }}
        .is-metric-icon {{
          width:22px; height:22px; border-radius:7px; background:var(--blue-soft);
          display:grid; place-content:center; gap:2px; padding:5px 6px;
        }}
        .is-metric-icon i {{
          display:block; width:10px; height:2px; border-radius:1px; background:var(--blue); font-style:normal;
        }}
        .is-metric-icon i.thin {{ width:6px; opacity:.55; }}
        .is-metric-label {{ color:#5B6670; font-size:11px; font-weight:650; letter-spacing:-0.01em; }}
        .is-metric-value {{ color:#111317; font-size:24px; font-weight:900; letter-spacing:-.04em; line-height:1; }}
        .is-metric-delta {{ color:var(--green); font-size:11px; font-weight:750; margin-top:6px; }}
        .is-metric-note {{ color:#879097; font-size:10px; margin-top:4px; }}
        .is-spark {{ width:100%; height:22px; margin-top:8px; display:block; }}

        .is-grid-2 {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
        .is-grid-3 {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
        .is-grid-4 {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }}
        .is-grid-main-aside {{ display:grid; grid-template-columns:minmax(0,1fr) 288px; gap:12px; align-items:start; }}
        .is-grid-left-main-right {{ display:grid; grid-template-columns:190px minmax(0,1fr) 245px; gap:11px; align-items:start; }}

        .is-panel-head {{
          display:flex; justify-content:space-between; align-items:center;
          padding:14px 16px 10px;
        }}
        .is-panel-body {{ padding:8px 16px 16px; }}
        .is-panel-title {{ font-size:13px; font-weight:850; color:#1A2025; letter-spacing:-0.01em; }}
        .is-panel-link {{
          font-size:11px; color:#2577F1; font-weight:650; cursor:pointer;
          transition: opacity .16s var(--ease);
        }}
        .is-panel-link:hover {{ opacity: 0.75; }}

        .is-kpi-strip {{
          display:grid;
          grid-template-columns:repeat(8,minmax(0,1fr));
          gap:8px;
          margin-bottom:11px;
        }}
        .is-kpi-mini {{ background:white; border:1px solid var(--line); border-radius:10px; padding:9px 10px; min-height:66px; }}
        .is-kpi-mini label {{ font-size:8.5px; color:#606C74; font-weight:700; display:block; }}
        .is-kpi-mini strong {{ font-size:16px; color:#1B2024; display:block; margin-top:5px; letter-spacing:-.03em; }}
        .is-kpi-mini small {{ font-size:7.5px; color:#8A949A; }}

        .is-process-scroll {{ overflow-x:auto; padding-bottom:3px; }}
        .is-process {{
          min-width:920px;
          display:grid;
          grid-template-columns:repeat(6,1fr);
          gap:7px;
          margin:8px 0 13px;
        }}
        .is-process.is-process-live {{
          min-width:0;
          grid-template-columns:repeat(3,minmax(0,1fr));
        }}
        .is-process-step {{
          background:white;
          border:1px solid var(--line);
          border-radius:10px;
          padding:9px 10px;
          display:flex;
          align-items:center;
          gap:8px;
          min-height:48px;
          position:relative;
        }}
        .is-process-step:not(:last-child):after {{
          content:""; position:absolute; right:-8px; width:8px; height:1px; background:#AEB8BE; z-index:2;
        }}
        .is-process-step.done:not(:last-child):after {{ background:#121518; }}
        .is-process-step.current {{ border-color:var(--yellow); box-shadow:0 0 0 3px rgba(255,214,0,.18); }}
        .is-process-step.pending {{ opacity:.55; }}
        .is-process-num {{
          flex:0 0 25px; width:25px; height:25px; border-radius:50%;
          display:grid; place-items:center; background:var(--yellow); color:#15191C;
          font-size:9px; font-weight:950;
        }}
        .is-process-step.done .is-process-num {{ background:#121518; color:white; }}
        .is-process-step.pending .is-process-num {{ background:#F0F3F4; color:#6B757C; }}
        .is-process-step b {{ font-size:9.5px; line-height:1.25; }}
        .is-process-step small {{ display:block; font-size:7.5px; color:#89939A; margin-top:2px; }}

        .is-product-card {{
          display:grid;
          grid-template-columns:148px 1fr 132px;
          gap:18px;
          align-items:stretch;
          padding:18px;
        }}
        .is-product-visual {{
          min-height:148px;
          border-radius:14px;
          background:
            radial-gradient(circle at 78% 18%, rgba(255,255,255,.55), transparent 28%),
            linear-gradient(145deg,#E8F4FB 0%,#A8D6F0 48%,#3D87BB 100%);
          display:grid;
          place-items:center;
          overflow:hidden;
          position:relative;
        }}
        .is-product-visual:before {{
          content:""; position:absolute; width:150px; height:150px; border:18px solid rgba(255,255,255,.22); border-radius:50%; right:-45px; top:-55px;
        }}
        .is-camera {{
          width:58px; height:96px; background:linear-gradient(145deg,#2A3642,#0D1116);
          border-radius:14px; box-shadow:0 16px 28px rgba(3,20,34,.28); transform:rotate(-8deg); position:relative;
        }}
        .is-camera:before {{
          content:""; width:40px; height:40px; border-radius:50%; position:absolute; left:9px; top:12px;
          background:radial-gradient(circle,#101317 0 16%,#3A4E60 17% 34%,#0B0E12 35% 55%,#75899A 56% 63%,#11151A 64%);
          box-shadow:0 0 0 3px #323D46;
        }}
        .is-camera:after {{
          content:"X5"; color:#D8E1E7; font-size:10px; font-weight:900; position:absolute; left:20px; bottom:14px; letter-spacing:.04em;
        }}
        .is-product-info {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px 18px; align-content:center; }}
        .is-field label {{ color:#8B959B; font-size:10px; text-transform:uppercase; letter-spacing:.06em; font-weight:750; display:block; }}
        .is-field strong {{ font-size:13px; color:#1A2025; display:block; margin-top:4px; line-height:1.35; font-weight:750; letter-spacing:-0.01em; }}
        .is-health {{ border-left:1px solid var(--line); padding-left:16px; display:flex; flex-direction:column; justify-content:center; align-items:center; }}
        .is-donut {{
          --pct:86;
          width:78px; height:78px; border-radius:50%;
          background:conic-gradient(var(--green) calc(var(--pct)*1%), #E7ECEE 0);
          position:relative; display:grid; place-items:center;
        }}
        .is-donut:before {{ content:""; width:58px; height:58px; border-radius:50%; background:white; position:absolute; }}
        .is-donut span {{ position:relative; font-size:20px; font-weight:900; color:#1C2429; letter-spacing:-0.04em; }}
        .is-health b {{ font-size:12px; color:var(--green); margin-top:8px; }}
        .is-health small {{ font-size:11px; color:#8B949A; }}

        .is-workflow {{ display:grid; grid-template-columns:repeat(6,1fr); gap:0; margin-top:10px; }}
        .is-workflow.is-workflow-live {{ grid-template-columns:repeat(3,1fr); }}
        .is-workflow-item {{ text-align:center; position:relative; padding:0 4px; }}
        .is-workflow-item:not(:last-child):after {{ content:""; height:2px; background:#E1E6E8; position:absolute; top:17px; left:58%; right:-42%; }}
        .is-workflow-item.done:not(:last-child):after {{ background:var(--yellow); }}
        .is-workflow-item.pending {{ opacity:.55; }}
        .is-workflow-icon {{
          width:34px; height:34px; border-radius:50%; border:1px solid var(--line); background:#F0F3F4;
          display:grid; place-items:center; margin:0 auto 8px; font-size:11px; font-weight:850; position:relative; z-index:1;
          transition: transform .18s var(--ease), box-shadow .18s var(--ease);
        }}
        .is-workflow-item:hover .is-workflow-icon {{ transform: scale(1.06); }}
        .is-workflow-item.done .is-workflow-icon {{ background:#121518; color:white; border-color:#121518; }}
        .is-workflow-item.active .is-workflow-icon {{
          background:var(--yellow); color:#17191B; border-color:var(--yellow);
          box-shadow: 0 0 0 4px rgba(255, 214, 0, 0.22);
        }}
        .is-workflow-item b {{ font-size:11px; display:block; letter-spacing:-0.01em; }}
        .is-workflow-item small {{ font-size:10px; color:#90999F; line-height:1.25; display:block; margin-top:3px; }}

        .is-list {{ list-style:none; margin:0; padding:0; }}
        .is-list li {{
          display:grid; grid-template-columns:24px 1fr; gap:10px; padding:10px 0;
          border-bottom:1px solid #EDF0F1;
          transition: background .16s var(--ease);
        }}
        .is-list li:last-child {{ border-bottom:0; }}
        .is-list li:hover {{ background: #FAFBFC; }}
        .is-list-num {{
          width:22px; height:22px; border-radius:50%; background:var(--yellow);
          display:grid; place-items:center; font-size:10px; font-weight:900;
        }}
        .is-list b {{ font-size:12px; display:block; letter-spacing:-0.01em; }}
        .is-list small {{ font-size:11px; color:#8A949A; line-height:1.4; display:block; margin-top:2px; }}

        .is-table {{ width:100%; border-collapse:separate; border-spacing:0; font-size:9px; }}
        .is-table th {{
          text-align:left; color:#7D888F; font-size:7.5px; font-weight:800; padding:8px 7px;
          background:#F8FAFA; border-top:1px solid var(--line); border-bottom:1px solid var(--line);
        }}
        .is-table th:first-child {{ border-left:1px solid var(--line); border-radius:8px 0 0 0; }}
        .is-table th:last-child {{ border-right:1px solid var(--line); border-radius:0 8px 0 0; }}
        .is-table td {{ padding:8px 7px; border-bottom:1px solid #EDF0F1; background:white; color:#2D3439; vertical-align:middle; }}
        .is-table tr td:first-child {{ border-left:1px solid var(--line); }}
        .is-table tr td:last-child {{ border-right:1px solid var(--line); }}
        .is-table tr:last-child td:first-child {{ border-radius:0 0 0 8px; }}
        .is-table tr:last-child td:last-child {{ border-radius:0 0 8px 0; }}
        .is-table tr.is-selected td {{
          background:#FFFBEA;
          box-shadow: inset 0 1px 0 rgba(255,214,0,.35), inset 0 -1px 0 rgba(255,214,0,.35);
        }}
        .is-table tr.is-selected td:first-child {{
          box-shadow: inset 3px 0 0 var(--yellow), inset 0 1px 0 rgba(255,214,0,.35), inset 0 -1px 0 rgba(255,214,0,.35);
        }}
        .is-table tr:hover td {{ background:#FAFBFC; }}
        .is-table tr.is-selected:hover td {{ background:#FFF8D6; }}
        .is-creator-cell {{ display:flex; align-items:center; gap:7px; min-width:130px; }}
        .is-mini-avatar {{
          width:26px; height:26px; border-radius:50%; display:grid; place-items:center;
          color:white; font-size:7px; font-weight:900; flex:0 0 26px;
        }}
        .is-creator-cell b {{ font-size:8.5px; display:block; }}
        .is-creator-cell small {{ font-size:6.8px; color:#89939A; display:block; }}
        .is-dot-row {{ display:flex; gap:2px; margin-top:3px; }}
        .is-dot {{ width:4px; height:4px; border-radius:50%; background:#D8DEE1; }}
        .is-dot.on {{ background:var(--green); }}
        .is-score-ring {{
          --score:90; width:30px; height:30px; border-radius:50%;
          background:conic-gradient(var(--green) calc(var(--score)*1%), #E5E9EB 0);
          display:grid; place-items:center; position:relative;
        }}
        .is-score-ring:before {{ content:""; width:23px; height:23px; border-radius:50%; background:white; position:absolute; }}
        .is-score-ring span {{ position:relative; font-size:7.5px; font-weight:900; }}
        .is-score-ring.lg {{ width:52px; height:52px; }}
        .is-score-ring.lg:before {{ width:40px; height:40px; }}
        .is-score-ring.lg span {{ font-size:14px; }}
        .is-match-label {{
          display:block; font-size:8px; font-weight:850; color:#16825D; margin-top:3px; text-align:center;
        }}

        .is-filter-row {{ display:flex; flex-wrap:wrap; gap:7px; margin:8px 0 10px; }}
        .is-filter-chip {{
          min-width:90px; padding:7px 10px; background:white; border:1px solid var(--line); border-radius:8px;
          font-size:7.5px; color:#68747C;
          transition: border-color .16s var(--ease), box-shadow .16s var(--ease), background .16s var(--ease);
          cursor:pointer;
        }}
        .is-filter-chip:hover {{
          border-color:#C9D3D8; background:#FAFBFC; box-shadow:0 2px 8px rgba(14,31,43,.05);
        }}
        .is-filter-chip.active {{
          border-color:#F0C800; background:var(--yellow-soft);
          box-shadow:0 0 0 2px rgba(255,214,0,.18);
        }}
        .is-filter-chip b {{ display:block; font-size:8px; color:#272E33; margin-top:2px; }}
        .is-filter-chip .is-chip-caret {{
          float:right; color:#9AA3AA; font-size:8px; margin-top:-10px;
        }}

        .is-mission-chip {{
          display:inline-flex; align-items:center; gap:8px;
          min-height:28px; padding:4px 12px 4px 8px;
          border-radius:999px; background:#121518; color:#FFFFFF;
          font-size:11px; font-weight:750; letter-spacing:-0.01em;
          box-shadow:0 1px 2px rgba(16,24,40,.08);
        }}
        .is-mission-chip .is-mission-dot {{
          width:8px; height:8px; border-radius:50%; background:var(--yellow);
          box-shadow:0 0 0 3px rgba(255,214,0,.28);
          flex:0 0 8px;
        }}
        .is-mission-chip.is-light {{
          background:var(--yellow-soft); color:var(--ink);
          border:1px solid #F0C800;
        }}
        .is-mission-chip.is-light .is-mission-dot {{
          background:var(--green); box-shadow:0 0 0 3px rgba(22,163,106,.2);
        }}

        .is-nl-search {{
          display:flex; align-items:center; gap:10px;
          min-height:42px; padding:8px 14px;
          background:white; border:1.5px solid #E8ECEE; border-radius:12px;
          box-shadow:var(--shadow);
          margin:4px 0 10px;
          transition: border-color .18s var(--ease), box-shadow .18s var(--ease);
        }}
        .is-nl-search:focus-within {{
          border-color:var(--yellow);
          box-shadow:0 0 0 3px rgba(255,214,0,.28), var(--shadow);
        }}
        .is-nl-search .is-nl-icon {{
          width:22px; height:22px; border-radius:7px; background:var(--yellow);
          display:grid; place-items:center; font-size:11px; font-weight:900; flex:0 0 22px;
          color:#171A1D;
        }}
        .is-nl-search .is-nl-label {{
          font-size:9px; font-weight:800; color:#8B6F00; letter-spacing:.04em;
          text-transform:uppercase; white-space:nowrap;
        }}
        .is-nl-search .is-nl-hint {{
          flex:1; font-size:12px; color:#8A949C; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        }}
        /* NL search Streamlit input sits under the chrome strip */
        div[data-testid="stTextInput"]:has(input[aria-label="Search creators"]) {{
          margin-top:-10px; margin-bottom:8px;
        }}
        div[data-testid="stTextInput"]:has(input[aria-label="Search creators"]) input {{
          border-top-left-radius:0 !important;
          border-top-right-radius:0 !important;
          border-color:var(--yellow) !important;
          box-shadow:0 0 0 3px rgba(255,214,0,.18);
          min-height:44px !important;
          font-size:13px !important;
        }}

        .is-ai-badge {{
          display:inline-flex; align-items:center; gap:5px;
          min-height:22px; padding:3px 9px;
          border-radius:999px;
          background:linear-gradient(135deg, #FFF5BF 0%, #EAF2FF 100%);
          border:1px solid #E8D98A;
          color:#3A4550; font-size:9px; font-weight:850;
        }}
        .is-ai-badge:before {{
          content:""; width:7px; height:7px; border-radius:50%;
          background:conic-gradient(var(--yellow), var(--blue), var(--green), var(--yellow));
          flex:0 0 7px;
        }}

        .is-action-bar {{
          position:sticky; bottom:8px; z-index:20;
          display:flex; justify-content:space-between; align-items:center; gap:16px;
          margin-top:12px; padding:14px 18px;
          background:rgba(255,255,255,.92); backdrop-filter:blur(10px);
          border:1px solid var(--line); border-radius:14px;
          box-shadow:0 -4px 24px rgba(14,31,43,.08), var(--shadow);
        }}
        .is-action-bar b {{ font-size:13px; letter-spacing:-0.01em; display:block; }}
        .is-action-bar small {{ font-size:11px; color:var(--muted); display:block; margin-top:2px; }}
        .is-action-bar-actions {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}

        .is-platform-card {{
          background:white; border:1px solid var(--line); border-radius:10px;
          padding:11px 12px; min-height:88px;
          transition: border-color .16s var(--ease), box-shadow .16s var(--ease);
        }}
        .is-platform-card:hover {{ border-color:#C9D3D8; box-shadow:var(--shadow); }}
        .is-platform-card h4 {{
          font-size:10px; margin:0 0 6px; display:flex; align-items:center; gap:6px;
          letter-spacing:-0.01em;
        }}
        .is-platform-card p, .is-platform-card li {{
          font-size:8px; color:#6E7980; line-height:1.45; margin:0;
        }}
        .is-platform-card ul {{ margin:4px 0 0; padding-left:14px; }}
        .is-platform-icon {{
          width:18px; height:18px; border-radius:6px; background:var(--blue-soft);
          display:grid; place-items:center; font-size:8px; font-weight:900; color:var(--blue);
          flex:0 0 18px;
        }}

        .is-header-actions {{
          display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end;
        }}
        .is-weight-tag {{
          display:inline-flex; align-items:center;
          min-height:16px; padding:1px 6px; border-radius:999px;
          background:#EEF2F3; color:#66727A; font-size:7px; font-weight:800;
        }}
        .is-risk-badge {{
          display:inline-flex; align-items:center; min-height:16px; padding:1px 6px;
          border-radius:999px; font-size:7px; font-weight:850; margin-left:4px;
        }}
        .is-risk-badge.medium {{ background:var(--orange-soft); color:#B56B00; }}
        .is-risk-badge.high {{ background:var(--red-soft); color:#C83B3B; }}

        .is-detail-score {{
          display:flex; flex-direction:column; align-items:center; gap:2px;
        }}
        .is-lift-panel {{
          background:#FBFCFC; border:1px solid #E8ECEE; border-radius:8px; padding:9px;
        }}
        .is-lift-panel h4 {{ font-size:8.5px; margin:0 0 6px; }}

        .is-kanban-count {{
          min-width:18px; height:18px; padding:0 5px; border-radius:999px;
          background:white; border:1px solid var(--line);
          display:inline-flex; align-items:center; justify-content:center;
          font-size:8px; font-weight:850; color:#4A565E;
        }}
        .is-kanban-head {{ gap:8px; }}
        .is-kanban-card {{
          transition: transform .16s var(--ease), box-shadow .16s var(--ease), border-color .16s var(--ease);
        }}
        .is-kanban-card:hover {{
          transform: translateY(-1px);
          border-color:#C9D3D8;
          box-shadow:0 6px 16px rgba(15,30,40,.08);
        }}
        .is-kanban-card-selected {{
          border-color:var(--blue);
          box-shadow:0 0 0 1px var(--blue), 0 6px 16px rgba(15,30,40,.08);
        }}
        .is-kanban-next {{
          color:var(--blue); cursor:pointer;
        }}
        .is-kanban-next:hover {{ text-decoration:underline; }}
        .is-kanban-tags {{ display:flex; flex-wrap:wrap; gap:4px; margin:5px 0 2px; }}

        .is-kpi-mini.has-donut {{
          display:grid; grid-template-columns:1fr 36px; gap:6px; align-items:center;
        }}
        .is-kpi-mini .is-mini-donut {{
          --pct:78; width:34px; height:34px; border-radius:50%;
          background:conic-gradient(var(--yellow) calc(var(--pct)*1%), #E7ECEE 0);
          position:relative; display:grid; place-items:center;
        }}
        .is-kpi-mini .is-mini-donut:before {{
          content:""; width:22px; height:22px; border-radius:50%; background:white; position:absolute;
        }}
        .is-kpi-mini .is-mini-donut span {{
          position:relative; font-size:7px; font-weight:900; color:#1C2429;
        }}

        .is-locale-card .is-locale-head {{
          display:flex; justify-content:space-between; align-items:center; gap:6px; margin-bottom:6px;
        }}
        .is-locale-card .is-locale-head h4 {{ margin:0; }}
        .is-tone-row {{ display:flex; flex-wrap:wrap; gap:5px; }}
        .is-quality-head {{
          display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;
        }}
        .is-quality-score {{
          font-size:9px; font-weight:900; color:var(--green);
          background:var(--green-soft); padding:2px 7px; border-radius:999px;
        }}

        .is-view-tabs {{
          display:flex; gap:0; border-bottom:1px solid var(--line); margin:0 0 12px;
        }}
        .is-view-tab {{
          font-size:11px; color:#68747C; font-weight:650;
          padding:8px 14px 10px; border-bottom:2px solid transparent; cursor:pointer;
        }}
        .is-view-tab.active {{
          color:#1A2025; font-weight:850; border-bottom-color:var(--yellow);
        }}

        .is-compare-head .is-fit-row {{
          display:flex; align-items:center; gap:6px; margin-top:4px;
        }}
        .is-driver-row {{
          display:grid; grid-template-columns:1fr auto; gap:6px; align-items:center;
        }}
        .is-driver-row .is-scorebar {{ margin:5px 0; }}
        .is-evidence-meta {{
          display:flex; gap:6px; flex-wrap:wrap; margin-top:4px;
        }}
        .is-evidence-tag {{
          font-size:6.5px; font-weight:750; color:#66727A;
          background:#EEF2F3; padding:2px 6px; border-radius:999px;
        }}

        .is-profile-head {{ display:grid; grid-template-columns:45px 1fr 52px; gap:9px; align-items:center; }}
        .is-profile-avatar {{ width:45px; height:45px; border-radius:50%; display:grid; place-items:center; color:white; font-weight:900; background:linear-gradient(135deg,#5D7E9D,#1E2E40); }}
        .is-profile-name {{ font-size:12px; font-weight:900; }}
        .is-socials {{ font-size:8px; color:#7E8990; margin-top:3px; }}
        .is-tabs {{ display:flex; gap:15px; border-bottom:1px solid var(--line); margin:10px -14px 8px; padding:0 14px; }}
        .is-tab {{ font-size:8px; color:#68747C; padding:0 0 7px; }}
        .is-tab.active {{ color:#1A2025; font-weight:850; border-bottom:2px solid var(--blue); }}
        .is-reason {{ display:flex; gap:8px; padding:7px 8px; border:1px solid #E8ECEE; border-radius:7px; margin-bottom:6px; background:#FAFBFB; }}
        .is-reason-icon {{ width:19px; height:19px; border-radius:50%; background:var(--yellow-soft); color:#8B6F00; display:grid; place-items:center; font-size:8px; font-weight:900; flex:0 0 19px; }}
        .is-reason b {{ font-size:8px; display:block; }}
        .is-reason small {{ font-size:7px; color:#879198; display:block; margin-top:2px; line-height:1.3; }}
        .is-video-row {{ display:grid; grid-template-columns:repeat(3,1fr); gap:6px; }}
        .is-video {{
          aspect-ratio:16/9; border-radius:7px; overflow:hidden; position:relative;
          background:linear-gradient(135deg,#243F5B,#80B0C9 52%,#E8B35C);
        }}
        .is-video:nth-child(2) {{ background:linear-gradient(135deg,#0E3548,#44A6BC 50%,#DCF3F5); }}
        .is-video:nth-child(3) {{ background:linear-gradient(135deg,#4E381E,#D79737 48%,#85A97B); }}
        .is-video:after {{ content:"▶"; width:20px; height:20px; border-radius:50%; display:grid; place-items:center; color:white; background:rgba(0,0,0,.42); position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); font-size:7px; }}

        .is-scorebar {{ display:grid; grid-template-columns:100px 1fr 30px; gap:8px; align-items:center; margin:7px 0; }}
        .is-scorebar label {{ font-size:8px; color:#536068; }}
        .is-scorebar-track {{ height:5px; border-radius:999px; background:#E7ECEE; overflow:hidden; }}
        .is-scorebar-fill {{ height:100%; border-radius:999px; background:var(--green); }}
        .is-scorebar span {{ font-size:7.5px; font-weight:800; text-align:right; }}

        .is-risk {{ display:flex; gap:8px; align-items:flex-start; padding:8px 0; border-bottom:1px solid #EDF0F1; }}
        .is-risk:last-child {{ border-bottom:0; }}
        .is-risk-icon {{ width:20px; height:20px; border-radius:50%; display:grid; place-items:center; background:var(--orange-soft); color:#B56B00; font-weight:900; font-size:8px; flex:0 0 20px; }}
        .is-risk.high .is-risk-icon {{ background:var(--red-soft); color:var(--red); }}
        .is-risk b {{ font-size:8px; display:block; }}
        .is-risk small {{ font-size:7px; color:#879198; line-height:1.3; display:block; margin-top:2px; }}

        .is-compare-grid {{ display:grid; grid-template-columns:155px repeat(3,minmax(0,1fr)); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
        .is-compare-grid > div {{ padding:8px 10px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); font-size:8px; min-height:34px; background:white; }}
        .is-compare-grid > div:nth-child(4n) {{ border-right:0; }}
        .is-compare-grid > div:nth-last-child(-n+4) {{ border-bottom:0; }}
        .is-compare-label {{ background:#F7F9FA !important; color:#69757D; font-weight:750; }}
        .is-compare-head {{ min-height:88px !important; }}
        .is-compare-head.selected {{ box-shadow:inset 0 0 0 2px var(--blue); background:#F4F8FF !important; }}

        .is-studio-shell {{ display:grid; grid-template-columns:175px minmax(0,1fr) 225px; gap:11px; align-items:start; }}
        .is-studio-card {{ background:white; border:1px solid var(--line); border-radius:10px; padding:11px; margin-bottom:10px; }}
        .is-studio-card h4 {{ font-size:9.5px; margin:0 0 7px; }}
        .is-studio-card p, .is-studio-card li {{ font-size:7.5px; color:#6E7980; line-height:1.45; }}
        .is-studio-card ul {{ margin:5px 0 0; padding-left:14px; }}
        .is-brief-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; }}
        .is-brief-block {{ background:#FBFCFC; border:1px solid #E8ECEE; border-radius:8px; padding:9px; min-height:126px; }}
        .is-brief-block h4 {{ font-size:8.5px; margin:0 0 7px; }}
        .is-brief-block p, .is-brief-block li {{ font-size:7.2px; color:#5E6970; line-height:1.45; }}
        .is-brief-block ul {{ margin:0; padding-left:13px; }}
        .is-localized {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:9px; }}
        .is-locale-card {{ border:1px solid #E7ECEE; border-radius:8px; padding:9px; background:white; }}
        .is-locale-card h4 {{ font-size:8.5px; margin:0 0 6px; }}
        .is-locale-card p {{ font-size:7.3px; color:#5F6A71; line-height:1.5; }}
        .is-check {{ display:flex; gap:6px; align-items:flex-start; font-size:7.5px; padding:4px 0; color:#5C686F; }}
        .is-check i {{ width:13px; height:13px; border-radius:50%; background:var(--green-soft); color:var(--green); font-style:normal; display:grid; place-items:center; font-size:7px; font-weight:900; flex:0 0 13px; }}

        .is-kanban {{ display:grid; grid-template-columns:repeat(5,minmax(160px,1fr)); gap:8px; min-width:900px; }}
        .is-kanban-col {{ background:#F7F9FA; border:1px solid var(--line); border-radius:9px; padding:8px; }}
        .is-kanban-head {{ display:flex; justify-content:space-between; align-items:center; font-size:8.5px; font-weight:850; padding:2px 2px 7px; }}
        .is-kanban-card {{ background:white; border:1px solid #E2E7E9; border-radius:7px; padding:8px; margin-bottom:7px; box-shadow:0 4px 12px rgba(15,30,40,.035); }}
        .is-kanban-card:last-child {{ margin-bottom:0; }}
        .is-kanban-card-selected {{
          border-color:var(--blue);
          box-shadow:0 0 0 1px var(--blue), 0 6px 16px rgba(15,30,40,.08);
        }}
        .is-kanban-person {{ display:flex; gap:7px; align-items:center; margin-bottom:6px; }}
        .is-kanban-person b {{ font-size:8.2px; display:block; }}
        .is-kanban-person small {{ font-size:6.8px; color:#89939A; display:block; }}
        .is-kanban-meta {{ display:grid; grid-template-columns:55px 1fr; gap:3px; font-size:7px; color:#7B868D; }}
        .is-kanban-meta strong {{ color:#3C474E; font-weight:750; }}
        .is-kanban-next {{ margin-top:7px; font-size:7px; font-weight:800; color:#2F3A40; }}

        .is-chart {{ background:white; border:1px solid var(--line); border-radius:10px; padding:11px; }}
        .is-chart-title {{ font-size:9.5px; font-weight:850; margin-bottom:8px; }}
        .is-bar-chart {{ display:flex; align-items:flex-end; gap:22px; height:116px; padding:5px 8px 22px; border-bottom:1px solid #EDF0F1; }}
        .is-bar-group {{ flex:1; display:flex; justify-content:center; gap:6px; align-items:flex-end; height:100%; position:relative; }}
        .is-bar {{ width:18px; border-radius:4px 4px 0 0; min-height:8px; }}
        .is-bar.blue {{ background:var(--blue); }}
        .is-bar.green {{ background:var(--green); }}
        .is-bar-label {{ position:absolute; bottom:-18px; left:50%; transform:translateX(-50%); white-space:nowrap; font-size:6.8px; color:#7C878E; }}
        .is-funnel {{ display:flex; align-items:center; gap:7px; height:116px; padding:12px 4px; }}
        .is-funnel-step {{ text-align:center; flex:1; }}
        .is-funnel-shape {{ margin:0 auto; height:48px; background:var(--blue); clip-path:polygon(10% 0,90% 0,75% 100%,25% 100%); }}
        .is-funnel-step:nth-child(2) .is-funnel-shape {{ width:78%; }}
        .is-funnel-step:nth-child(3) .is-funnel-shape {{ width:58%; }}
        .is-funnel-step:nth-child(4) .is-funnel-shape {{ width:39%; }}
        .is-funnel-step:nth-child(5) .is-funnel-shape {{ width:28%; background:var(--green); }}
        .is-funnel-step b {{ font-size:8px; display:block; margin-top:6px; }}
        .is-funnel-step small {{ font-size:6.8px; color:#8B959B; }}
        .is-budget-actions {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin-top:10px; }}
        .is-action-card {{ border:1px solid var(--line); border-radius:8px; padding:9px; background:white; min-height:95px; }}
        .is-action-card.green {{ border-color:#BFE8D6; background:#F4FCF8; }}
        .is-action-card.orange {{ border-color:#F2D7A7; background:#FFFBF3; }}
        .is-action-card.blue {{ border-color:#BFD6FA; background:#F5F9FF; }}
        .is-action-card h4 {{ font-size:8.5px; margin:0 0 5px; }}
        .is-action-card p {{ font-size:7px; line-height:1.4; color:#6E7980; }}
        .is-action-impact {{ font-size:7.5px; font-weight:850; margin-top:7px; }}

        .stButton > button {{
          min-height:36px;
          border-radius:10px;
          border:1px solid #D6DEE1;
          background:white;
          color:#232A2F;
          font-size:13px;
          font-weight:700;
          box-shadow:none;
          transition: transform .16s var(--ease), box-shadow .16s var(--ease), background .16s var(--ease), border-color .16s var(--ease);
        }}
        .stButton > button:hover {{
          border-color:#AEB9BE;
          color:#111317;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(14,31,43,.08);
        }}
        .stButton > button[kind="primary"] {{
          background:var(--yellow);
          border-color:var(--yellow);
          color:#171A1D;
          font-weight:850;
        }}
        .stButton > button[kind="primary"]:hover {{
          background:#F0C800;
          border-color:#F0C800;
          transform: translateY(-1px);
          box-shadow: 0 6px 16px rgba(255, 214, 0, 0.35);
        }}
        .stButton > button:active {{ transform: translateY(0); }}

        [data-testid="stSelectbox"] label, [data-testid="stTextInput"] label,
        [data-testid="stMultiSelect"] label, [data-testid="stNumberInput"] label,
        [data-testid="stDateInput"] label, [data-testid="stSlider"] label,
        [data-testid="stTextArea"] label {{
          color:#56626A;
          font-size:10px;
          font-weight:750;
        }}
        [data-baseweb="select"] > div,
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input,
        [data-testid="stTextArea"] textarea {{
          border-color:#D9E1E4 !important;
          border-radius:7px !important;
          font-size:11px !important;
          background:white !important;
        }}
        [data-testid="stExpander"] {{
          border:1px solid var(--line);
          border-radius:10px;
          background:white;
        }}
        [data-testid="stExpander"] summary {{ font-size:11px; font-weight:800; }}
        [data-testid="stTabs"] button {{ font-size:10px; }}

        @media (max-width: 1180px) {{
          .is-metric-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
          .is-grid-main-aside {{ grid-template-columns:1fr; }}
          .is-grid-left-main-right, .is-studio-shell {{ grid-template-columns:1fr; }}
          .is-product-card {{ grid-template-columns:150px 1fr; }}
          .is-health {{ grid-column:1 / -1; border-left:0; border-top:1px solid var(--line); padding:10px 0 0; flex-direction:row; gap:8px; }}
          .is-kpi-strip {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
        }}
        @media (max-width: 760px) {{
          [data-testid="stSidebar"] {{ min-width:220px !important; max-width:220px !important; }}
          .block-container {{ padding:14px 12px 36px; }}
          .is-topbar {{ grid-template-columns:1fr; height:auto; padding-bottom:10px; }}
          .is-userbar {{ display:none; }}
          .is-page-head {{ flex-direction:column; }}
          .is-metric-grid, .is-grid-2, .is-grid-3, .is-grid-4 {{ grid-template-columns:1fr; }}
          .is-kpi-strip {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
          .is-product-card {{ grid-template-columns:1fr; }}
          .is-product-info {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
          .is-brief-grid, .is-localized, .is-budget-actions {{ grid-template-columns:1fr; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
