from pathlib import Path

from src.content_evidence import load_creator_content
from src.data_loader import load_creators, load_mission
from src.creator_genome import genome_for, load_genome_pack
from src.product_dna import claim_ids, dna_document, load_product_dna
from src.retrieval import TFIDF_BOOST_CAP, cosine, tfidf_boosts
from src.scoring import passes_hard_gates, rank_creators
from src.scouting import scout_cards

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_has_sixty_unique_creators_without_platforms_column():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    assert len(catalog) == 60
    assert catalog["creator_id"].nunique() == 60
    assert "platforms" not in catalog.columns
    assert set(catalog["creator_id"].head(30)) == {f"C{i:03d}" for i in range(1, 31)}


def test_creator_content_is_one_hundred_eighty_authored_clips():
    posts = load_creator_content()
    assert len(posts) == 180
    creators = {item["creator_id"] for item in posts}
    assert len(creators) == 60
    for post in posts:
        assert post.get("asr") in (None, "")
        assert post.get("asr_status") == "not_collected"
        assert post.get("caption_source") == "labeled_demo"
        assert post.get("keyframe_status") == "labeled_demo_note"
        assert post.get("comment_status") == "labeled_demo_themes"
        assert 1 <= len(post.get("comment_themes") or []) <= 3
        assert post["url"].startswith("https://example.com/demo/")
        assert post["timestamps"]
        assert all(stamp.get("t") and stamp.get("label") for stamp in post["timestamps"])
        assert all(stamp.get("claim_id") in {"all_day", "pov", "rugged", "360"} for stamp in post["timestamps"])
        assert all(stamp.get("caption") and stamp.get("keyframe_note") for stamp in post["timestamps"])
        assert all(stamp.get("caption_source") == "labeled_demo" for stamp in post["timestamps"])


def test_product_dna_is_versionable_visual_object():
    dna = load_product_dna()
    assert dna["dna_id"] == "dna_x5_v1"
    assert dna["sku"] == "Insta360 X5"
    assert dna["version"] == 1
    assert claim_ids(dna) == ("all_day", "pov", "rugged", "360")
    assert "visual_proof" in dna["claims"][0]
    assert dna_document(dna)
    assert "Instagram" not in dna_document(dna)
    assert "TikTok" not in dna_document(dna)


def test_creator_genome_pack_is_versionable_and_honest():
    pack = load_genome_pack()
    assert pack["genome_pack_id"] == "genome_x5_v1"
    assert pack["version"] == 1
    assert len(pack["genomes"]) == 60
    catalog_ids = set(load_creators(ROOT / "data" / "creators.csv")["creator_id"])
    posts = {item["post_id"] for item in load_creator_content()}
    genome_ids = {item["creator_id"] for item in pack["genomes"]}
    assert genome_ids == catalog_ids
    maya = genome_for("C004")
    assert maya is not None
    assert maya["genome_id"] == "genome_C004_v1"
    assert maya["asr_status"] == "not_collected"
    assert maya["comment_status"] == "not_collected"
    assert maya["keyframe_status"] == "not_collected"
    assert maya["commerce"]["status"] == "not_collected"
    assert maya["audience"]["age_status"] == "not_collected"
    assert maya["cost"]["sample_status"] == "not_collected"
    assert set(maya["clip_ids"]) <= posts
    assert "Instagram" not in str(maya)
    assert "TikTok" not in str(maya)


def test_tfidf_is_real_sparse_cosine_not_a_constant():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    dna = dna_document(load_product_dna())
    boosts = tfidf_boosts(catalog, mission, dna_text=dna)
    assert len(boosts) == 60
    assert max(boosts.values()) > min(boosts.values())
    assert max(boosts.values()) <= TFIDF_BOOST_CAP
    assert cosine({"a": 1.0}, {"a": 1.0}) == 1.0
    assert cosine({"a": 1.0}, {"b": 1.0}) == 0.0


def test_hybrid_recall_gates_then_ranks_top_ten():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    mission = load_mission(ROOT / "data" / "launch_mission.json")
    ranked = rank_creators(catalog, mission)
    assert len(catalog) == 60
    assert 10 <= len(ranked) < 60
    assert (ranked["ranking_model_version"] == "claim_underwrite_v1").all()
    assert ranked["spend_ready"].dtype == bool
    assert int(ranked.head(10)["spend_ready"].sum()) >= 1
    assert ranked["genome_id"].notna().all()
    for _, row in ranked.head(10).iterrows():
        passed, reasons = passes_hard_gates(row, mission)
        assert passed is True
        assert reasons == []
        assert float(row["tfidf_boost"]) >= 0
        assert float(row["tfidf_boost"]) <= TFIDF_BOOST_CAP


def test_scout_cards_are_catalog_momentum_not_live_crawl():
    catalog = load_creators(ROOT / "data" / "creators.csv")
    cards = scout_cards(catalog, limit=8)
    assert len(cards) == 8
    assert all(item["source"] == "creator_genome" for item in cards)
    assert all(item.get("genome_id") for item in cards)
    assert all("not a live" in item["note"].lower() for item in cards)
    scores = [item["scout_score"] for item in cards]
    assert scores == sorted(scores, reverse=True)
