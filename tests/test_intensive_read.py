from pathlib import Path

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.intensive_read import intensive_read_html, intensive_read_pack
from src.scoring import rank_creators

ROOT = Path(__file__).resolve().parents[1]
CLAIM_IDS = {"all_day", "pov", "rugged", "360"}


def test_intensive_read_pack_exposes_twenty_creators_clips_and_timestamps():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    posts = load_creator_content()
    ranked = rank_creators(catalog, mission)
    assert len(ranked) >= 20

    pack = intensive_read_pack(ranked, posts, n=20)
    assert len(pack) == 20
    html = intensive_read_html(pack)
    assert 'id="intensive-read-board"' in html
    assert "Top 20 intensive-read clips" in html
    assert "This is not multimodal ASR" in html
    assert "not_collected" in html
    assert "Instagram" not in html
    assert "TikTok" not in html

    clip_n = 0
    stamp_n = 0
    for item in pack:
        assert item["creator_id"]
        assert item["clips"]
        assert f'data-creator-id="{item["creator_id"]}"' in html
        assert item["creator_id"] in html
        for clip in item["clips"]:
            assert clip["asr_status"] == "not_collected"
            assert clip["asr"] in (None, "")
            assert clip["url"].startswith("https://example.com/demo/")
            assert clip["timestamps"]
            assert all(stamp["t"] and stamp["label"] for stamp in clip["timestamps"])
            assert all(stamp["claim_id"] in CLAIM_IDS for stamp in clip["timestamps"])
            clip_n += 1
            stamp_n += len(clip["timestamps"])
            assert clip["url"] in html
            assert clip["timestamps"][0]["t"] in html
            assert clip["timestamps"][0]["claim_id"] in html
    assert clip_n == 60
    assert stamp_n >= 60
    assert "ASR not_collected" in html


def test_intensive_read_html_empty_ranking():
    import pandas as pd

    assert intensive_read_pack(pd.DataFrame()) == []
    html = intensive_read_html([])
    assert 'id="intensive-read-board"' in html
    assert "No gated creators" in html
