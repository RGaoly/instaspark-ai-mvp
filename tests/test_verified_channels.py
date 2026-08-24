from __future__ import annotations

from pathlib import Path

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.intensive_read import intensive_read_html, intensive_read_pack
from src.scoring import rank_creators
from src.verified_channels import (
    OWNERSHIP,
    VERIFIED_ROW_LABEL,
    binds_by_creator_id,
    load_verified_public_channels,
    verified_row_label,
)


ROOT = Path(__file__).resolve().parents[1]


def test_verified_bind_table_is_catalog_identity_not_kyc():
    pack = load_verified_public_channels()
    assert pack.get("available")
    binds = pack["binds"]
    assert len(binds) == 20
    catalog = load_creators(ROOT / "data" / "creators.csv")
    by_id = catalog.set_index("creator_id")
    creator_ids = [item["creator_id"] for item in binds]
    channel_ids = [item["channel_id"] for item in binds]
    assert len(creator_ids) == len(set(creator_ids))
    assert len(channel_ids) == len(set(channel_ids))
    for item in binds:
        row = by_id.loc[item["creator_id"]]
        assert item["ownership"] == OWNERSHIP == "catalog_channel"
        assert item["channel_id"].startswith("UC")
        assert str(row["creator_name"]) == item["channel_title"]
        assert str(row["youtube_channel_id"]) == item["channel_id"]
        reason = item["bind_reason"].lower()
        assert "not kyc" in reason
        assert "synthetic persona and is not the uploader" not in reason
        assert item["uploads"]
        assert all(str(upload.get("url") or "").startswith("https://www.youtube.com/watch") for upload in item["uploads"])
        assert all(upload.get("channel_id") == item["channel_id"] for upload in item["uploads"])
    unbound = catalog[~catalog["creator_id"].isin(creator_ids)]
    assert len(unbound) == 40
    assert (unbound["youtube_channel_id"].fillna("") == "").all()


def test_top20_names_and_clips_are_the_catalog_channel():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    binds = binds_by_creator_id()
    pack = intensive_read_pack(ranked, posts, n=20)
    html = intensive_read_html(pack)
    assert len(pack) == 20
    assert len(binds) == 20
    for item in pack:
        bind = binds[item["creator_id"]]
        row = catalog[catalog["creator_id"] == item["creator_id"]].iloc[0]
        assert item["creator_name"] == bind["channel_title"] == str(row["creator_name"])
        assert str(row["youtube_channel_id"]) == bind["channel_id"]
        assert item["verified_bind"]["channel_id"] == bind["channel_id"]
        label = verified_row_label(bind)
        assert label == VERIFIED_ROW_LABEL.format(channel_title=bind["channel_title"])
        assert label in html
        assert "Not KYC" in html
        assert "demo persona" not in html.lower()
        youtube_clips = [clip for clip in item["clips"] if clip.get("video_id")]
        assert youtube_clips
        assert all(clip.get("ownership") == OWNERSHIP for clip in youtube_clips)
        assert all(clip.get("channel_id") == str(row["youtube_channel_id"]) for clip in youtube_clips)
        assert all(clip.get("channel_title") == item["creator_name"] for clip in youtube_clips)


def test_attached_channel_still_wins_over_catalog_channel():
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
