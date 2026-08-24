from __future__ import annotations

from pathlib import Path

from components.i18n import localize_text, translate


ROOT = Path(__file__).resolve().parents[1]


def test_core_navigation_has_chinese_labels():
    assert translate("Launch Mission", language="zh") == "发起任务"
    assert translate("Opportunity Inbox", language="zh") == "机会收件箱"
    assert translate("Growth Review", language="zh") == "增长复盘"
    assert translate("Growth Review", language="en") == "Growth Review"
    assert translate("Record performance event (demo)", language="zh") == "录入效果事件（演示）"
    assert translate("Mission fit", language="zh") == "任务匹配"
    assert translate("Topic overlap", language="zh") == "主题重合"
    assert translate("Query boost", language="zh") == "查询加权"
    assert translate("Live YouTube evidence attached", language="zh") == "已挂接 YouTube 实时证据"
    assert translate("Product DNA", language="zh") == "产品 DNA"
    assert translate("Always-on scout cards", language="zh") == "持续侦察卡片"
    assert "not verified creator-owned" in translate(
        "Hard gates, evidence, stability, attribution, recall 60, intensive-read Top 20 with labeled_demo timestamps. YouTube overlay is name-match or topic-search, not verified creator-owned. Catalog videos, Creator Genome. Human interview adoption ≥70% is not_collected.",
        language="en",
    )
    assert (
        translate(
            "NL query is a lexical filter + small boost, not semantic search.",
            language="zh",
        )
        == "自然语言查询是词面筛选加小幅加权，不是语义搜索。"
    )
    assert translate("Live evidence: {n} attached", language="zh", n=2) == "实时证据：2 条已挂接"
    assert translate("Needs shortlist", language="zh") == "需要入围名单"
    assert translate("Demo catalog", language="zh") == "演示目录"
    assert translate("Not assessed in this demo", language="zh") == "本演示未评估"
    assert translate("Not specified in the catalog", language="zh") == "目录中未注明"
    assert translate("No platform fields in the demo catalog", language="zh") == "演示目录没有平台字段"
    assert translate("Shortlist creators", language="zh") == "将创作者加入入围名单"
    assert translate("Pipeline snapshot", language="zh") == "管线快照"
    assert translate("Unified workflow", language="zh") == "统一工作流"
    assert translate("Last 7 days", language="zh") == "最近 7 天"
    assert translate("Linked creator opportunities", language="zh") == "已关联的创作者机会"
    assert (
        translate(
            "Created {opportunity_id} and set it as the active workspace context.",
            language="zh",
            opportunity_id="OPP-004",
        )
        == "已创建 OPP-004，并设为当前工作区上下文。"
    )
    assert translate(
        "ROI uses recorded performance events in the selected period and market. Empty set equals 0x.",
        language="zh",
    ) == "ROI 只统计所选周期和市场内已录入的效果事件。筛空则为 0x。"
    assert translate("Contact pack", language="zh") == "联络包"
    assert translate("Refresh outreach message", language="zh") == "重新生成外联文案"
    assert (
        translate("External send is not wired in this demo", language="zh")
        == "本演示不发送到站外"
    )
    assert translate("Advance to {state}", language="zh", state="Contacted") == "推进到 Contacted"
    assert translate("Mark measured only after recording events", language="zh") == "仅在录入效果事件后标记为已衡量"
    assert translate("Record a conversion on Growth Review", language="zh") == "请到增长复盘页录入转化"
    assert translate("Create a brief in Content Studio", language="zh") == "请到内容工作室创建简报"
    assert translate("Audit timeline", language="zh") == "审计时间线"
    assert translate("Open Outreach", language="zh") == "打开外联"
    assert (
        translate("Performance event recorded. Creator moved to Measured.", language="zh")
        == "效果事件已录入。创作者已进入已衡量。"
    )
    assert translate("Select this creator", language="zh") == "选择该创作者"
    assert (
        translate("Stay on Search. Detail, Shortlist, Compare, and Brief apply to this creator.", language="zh")
        == "留在搜索页。详情、短名单、对比和简报都针对该创作者。"
    )
    assert translate("Click a row to inspect that creator.", language="zh") == "点击一行即可查看该创作者。"
    assert translate("Inspect {creator_id}", language="zh", creator_id="C051") == "精读 C051"
    assert (
        translate("Labeled demo evidence — not ASR, not scraped comments.", language="zh")
        == "标注演示证据 — 不是语音转写，不是抓取评论。"
    )
    assert "youtube_data_api" in translate(
        "youtube_data_api: public video link, thumbnail keyframe proxy, comment snippets. youtube_public_timedtext: caption lines when YouTube exposes them. ownership attached_channel = operator-attached channel uploads; channel_search_match = catalog name matched a public channel title; public_search_hit = topic search, not the catalog creator. labeled_demo: DNA claim timestamps (separate layer). Not ranked.",
        language="en",
    )
    assert translate("Selected creator", language="zh") == "已选择该创作者"
    assert (
        translate(
            "Synthetic 30-message corpus (EN / ES / DE). Not a live mailbox. Extraction is a labeled footer. Translation is pre-authored. Send stays disabled.",
            language="zh",
        )
        == "30 封合成来信语料（英 / 西 / 德）。不是真实邮箱。字段抽取读的是邮件页脚标签。译文是预先写好的。发送保持关闭。"
    )
    assert translate("Imported {n} synthetic inbound messages.", language="zh", n=30) == "已导入 30 封合成入站来信。"
    assert translate("Collaboration state", language="zh") == "协作状态"
    assert translate("Why recommended", language="zh") == "推荐原因"
    assert translate("Shortlist overlap", language="zh") == "入围名单重合度"
    assert translate("No scored reasons for this creator.", language="zh") == "该创作者没有已评分的推荐理由。"
    assert translate("Same catalog fields as Content Studio.", language="zh") == "与内容工作室使用同一目录字段。"
    assert translate("Focus creator", language="zh") == "聚焦创作者"
    assert translate("Look up YouTube on Search", language="zh") == "到搜索页查询 YouTube"
    assert (
        translate("No live YouTube evidence attached. Lookup is optional and labeled.", language="zh")
        == "尚未挂接 YouTube 实时证据。查询可选且会标明来源。"
    )


def test_longest_first_localization_preserves_compound_terms():
    assert localize_text("Creator Search & Match", language="zh") == "创作者搜索与匹配"
    assert localize_text("Reply ready · Human governed", language="zh") == "回复就绪 · 人工可控"


def test_language_switch_is_visible_and_global():
    shell = (ROOT / "components/shell.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.segmented_control" in shell
    assert 'options=["en", "zh"]' in shell
    assert "on_change=_sync_language_switcher" in shell
    assert 'href="?lang=zh"' in shell
    assert 'href="?lang=en"' in shell
    assert 'target="_top"' in shell
    # Page titles stay canonical English for route stability, so navigation is
    # localized where it is rendered rather than where the pages are declared.
    assert "label=t(page.title)" in shell
    assert 'st.query_params.get("lang")' in app


def test_all_seven_views_use_translation_layer():
    for path in (ROOT / "views").glob("*.py"):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "components.i18n" in source, path.name
