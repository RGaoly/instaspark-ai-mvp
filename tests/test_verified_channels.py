from __future__ import annotations

from pathlib import Path

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.intensive_read import intensive_read_html, intensive_read_pack
from src.scoring import rank_creators
from src.verified_channels import (
    LEFTOVER_SEARCH_NOTE,
    OWNERSHIP,
    VERIFIED_ROW_LABEL,
    binds_by_creator_id,
    load_verified_public_channels,
    verified_row_label,
)


ROOT = Path(__file__).resolve().parents[1]


def test_verified_bind_table_is_honest_and_stable():
    pack = load_verified_public_channels()
    assert pack.get("available")
    binds = pack["binds"]
    assert binds
    catalog = load_creators(ROOT / "data" / "creators.csv")
    persona = {str(name).strip().lower() for name in catalog["creator_name"].tolist()}
    creator_ids = [item["creator_id"] for item in binds]
    channel_ids = [item["channel_id"] for item in binds]
    assert len(creator_ids) == len(set(creator_ids))
    assert len(channel_ids) == len(set(channel_ids))
    for item in binds:
        assert item["ownership"] == OWNERSHIP
        assert item["channel_id"].startswith("UC")
        assert item["channel_title"]
        assert "synthetic persona" in item["bind_reason"].lower() or "not the uploader" in item["bind_reason"].lower()
        assert item["channel_title"].strip().lower() not in persona
        assert item["uploads"]
        assert all(str(upload.get("url") or "").startswith("https://www.youtube.com/watch") for upload in item["uploads"])
        assert all(upload.get("channel_id") == item["channel_id"] for upload in item["uploads"])


def test_top20_intensive_board_uses_verified_bind_label():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    binds = binds_by_creator_id()
    pack = intensive_read_pack(ranked, posts, n=20)
    html = intensive_read_html(pack)
    bound_rows = [item for item in pack if item.get("verified_bind")]
    assert bound_rows, "Top 20 should include at least one verified public-channel bind"
    for item in pack:
        bind = binds.get(item["creator_id"])
        if not bind:
            owns = {str(clip.get("ownership") or "") for clip in item["clips"] if clip.get("video_id")}
            if "public_search_hit" in owns:
                assert LEFTOVER_SEARCH_NOTE in html
            continue
        assert item["verified_bind"]["channel_id"] == bind["channel_id"]
        assert item["verified_bind"]["channel_title"] == bind["channel_title"]
        label = verified_row_label(bind)
        assert label == VERIFIED_ROW_LABEL.format(channel_title=bind["channel_title"])
        assert label in html
        assert "Catalog name stays a demo persona" in html
        youtube_clips = [clip for clip in item["clips"] if clip.get("video_id")]
        assert youtube_clips
        assert all(clip.get("ownership") == OWNERSHIP for clip in youtube_clips)
        assert all(clip.get("channel_id") == bind["channel_id"] for clip in youtube_clips)
        assert all(clip.get("channel_title") == bind["channel_title"] for clip in youtube_clips)


def test_attached_channel_still_wins_over_verified_bind():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    binds = binds_by_creator_id()
    creator_id = next((cid for cid in ranked["creator_id"].astype(str) if cid in binds), None)
    assert creator_id
    creator_posts = [post for post in posts if post["creator_id"] == creator_id]
    attached = [
        {
            "post_id": creator_posts[0]["post_id"],
            "creator_id": creator_id,
            "video_id": "operatorAttach1",
            "url": "https://www.youtube.com/watch?v=operatorAttach1",
            "title": "Operator-attached upload",
            "thumbnail_url": "https://i.ytimg.com/vi/operatorAttach1/hqdefault.jpg",
            "channel_id": "UCoperatorAttach",
            "channel_title": "Operator attached",
            "ownership": "attached_channel",
            "keyframe_source": "youtube_thumbnail",
            "comment_source": "youtube_data_api",
            "asr_status": "not_collected",
        }
    ]
    pack = intensive_read_pack(
        ranked,
        posts,
        n=20,
        attached_by_creator={creator_id: attached},
    )
    row = next(item for item in pack if item["creator_id"] == creator_id)
    assert row["verified_bind"] is None
    first = next(clip for clip in row["clips"] if clip["post_id"] == creator_posts[0]["post_id"])
    assert first["ownership"] == "attached_channel"
    assert first["video_id"] == "operatorAttach1"
    html = intensive_read_html(pack)
    assert "ownership: attached_channel" in html
