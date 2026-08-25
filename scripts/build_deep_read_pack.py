"""Build the labeled-demo deep-read pack beside creator_content.json.

This is a human-labeler layer grounded in Product DNA claim ids. It is not
ASR, Whisper, YouTube captions, scraped comments, or OCR.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_PATH = ROOT / "data" / "creator_content.json"
GENOME_PATH = ROOT / "data" / "creator_genome.json"
OUT_PATH = ROOT / "data" / "creator_content_deep_read.json"

CAPTIONS = {
    "all_day": (
        "On-screen label: long outdoor take still rolling. No battery minutes.",
        "Labeler caption: daylight trail; camera stays on through the ride.",
        "On-screen: all-day outdoor shooting in real use. No amp-hour figure.",
    ),
    "pov": (
        "On-screen label: handlebar POV, trail filling the frame.",
        "Labeler caption: first-person eye-line at rider height.",
        "On-screen: immersive POV of the path. Not a platform-exclusive format.",
    ),
    "rugged": (
        "On-screen label: water or grit on the housing; take does not cut.",
        "Labeler caption: dusty outdoor trail, camera still in the shot.",
        "On-screen: splash contact without an IP rating claim.",
    ),
    "360": (
        "On-screen label: full-surround establish of a real location.",
        "Labeler caption: 360 rotate, then a detail cut. No resolution number.",
        "On-screen: place captured in the round, then a tight cutaway.",
    ),
}

KEYFRAMES = {
    "all_day": "Would show: long outdoor take still rolling; no battery graphic in frame.",
    "pov": "Would show: POV handle or rider eye-line; trail filling the frame.",
    "rugged": "Would show: rugged outdoor splash or dust on the housing.",
    "360": "Would show: 360 room or location rotate; no resolution number on screen.",
}


def _themes(topics: list[str], scenes: list[str]) -> list[str]:
    themes: list[str] = []
    for topic in topics[:2]:
        cleaned = str(topic).strip()
        if cleaned:
            themes.append(f"Catalog label (not scraped): {cleaned} setup questions")
    for scene in scenes[:1]:
        cleaned = str(scene).strip()
        if cleaned:
            themes.append(f"Catalog label (not scraped): where this {cleaned} was filmed")
    if not themes:
        themes.append("Catalog label (not scraped): outdoor camera questions")
    return themes[:3]


def main() -> None:
    posts = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    genomes = {
        item["creator_id"]: item
        for item in json.loads(GENOME_PATH.read_text(encoding="utf-8"))["genomes"]
    }
    clips = []
    for index, post in enumerate(posts):
        creator_id = post["creator_id"]
        genome = genomes.get(creator_id) or {}
        topic_scene = genome.get("topic_scene") or {}
        topics = list(topic_scene.get("topics") or post.get("keywords") or [])
        scenes = list(topic_scene.get("scenes") or post.get("scenes") or [])
        name = str(genome.get("creator_name") or creator_id).split()[0]
        stamps = []
        for stamp_i, stamp in enumerate(post["timestamps"]):
            claim_id = str(stamp["claim_id"])
            variants = CAPTIONS[claim_id]
            caption = f"{name} · {variants[(index + stamp_i) % len(variants)]}"
            stamps.append(
                {
                    "t": stamp["t"],
                    "claim_id": claim_id,
                    "caption": caption,
                    "keyframe_note": KEYFRAMES[claim_id],
                }
            )
        clips.append(
            {
                "post_id": post["post_id"],
                "caption_source": "labeled_demo",
                "keyframe_status": "labeled_demo_note",
                "comment_status": "labeled_demo_themes",
                "comment_themes": _themes(topics, scenes),
                "stamps": stamps,
            }
        )
    pack = {
        "pack_id": "deep_read_x5_v1",
        "version": 1,
        "layer": "labeled_demo",
        "sku": "Insta360 X5",
        "updated_at": "2026-08-24T00:00:00+00:00",
        "source": (
            "Human-labeler demo layer grounded in Product DNA claim_id. "
            "Not ASR, not Whisper, not YouTube captions, not scraped comments, not OCR."
        ),
        "clips": clips,
    }
    OUT_PATH.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(clips)} clips to {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
