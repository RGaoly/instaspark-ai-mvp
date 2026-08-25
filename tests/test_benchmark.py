from __future__ import annotations

import json

from src.benchmark import (
    ARM_BASELINE,
    ARM_MODEL,
    STATUS_NOT_RUN,
    STATUS_OK,
    keyword_predictions,
    load_gold,
    load_report,
    prf,
    run_benchmark,
    save_report,
)
from src.evidence_reader import caption_lines_of
from src.product_dna import claim_ids, load_product_dna
from src.youtube_clips import load_youtube_intensive_clips
from views.growth_review import _benchmark_html


def test_prf_fixture_values():
    assert prf(1, 0, 0) == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 1, "fp": 0, "fn": 0}
    assert prf(0, 0, 0) == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 0}
    mixed = prf(1, 1, 1)
    assert mixed["tp"] == 1
    assert mixed["fp"] == 1
    assert mixed["fn"] == 1
    assert mixed["precision"] == 0.5
    assert mixed["recall"] == 0.5
    assert mixed["f1"] == 0.5


def test_gold_set_is_manual_read_and_quotes_are_in_the_caption():
    gold = load_gold()
    assert gold["method"] == "manual_read"
    assert gold["n_clips"] == len(gold["labels"]) == 12
    assert gold["n_claim_labels"] == 48
    allowed = set(claim_ids(load_product_dna()))
    clips = {clip["post_id"]: clip for clip in load_youtube_intensive_clips().get("clips") or []}
    supported = 0
    for row in gold["labels"]:
        clip = clips[row["post_id"]]
        lines = caption_lines_of(clip)
        texts = [item["text"] for item in lines]
        stamps = {item["t"] for item in lines}
        for item in row["claims"]:
            assert item["claim_id"] in allowed
            if not item["supported"]:
                continue
            supported += 1
            assert item["timestamp"] in stamps
            assert any(item["quote"] in text for text in texts)
    assert supported == 4


def test_keyword_baseline_only_emits_quotes_from_caption_lines():
    clips = {clip["post_id"]: clip for clip in load_youtube_intensive_clips().get("clips") or []}
    clip = clips["POST-C012-01"]
    preds = keyword_predictions(clip, claim_ids(load_product_dna()))
    texts = [item["text"] for item in caption_lines_of(clip)]
    for item in preds:
        assert any(item["quote"] in text for text in texts)
        assert item["source"] == ARM_BASELINE


def test_model_arm_is_not_run_when_the_cache_is_empty_and_no_key(monkeypatch, tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(
        json.dumps(
            {
                "pack_id": "empty",
                "version": 1,
                "prompt_version": "evidence_reader_v1",
                "extractor": "evidence_reader",
                "model": "",
                "caption_source": "youtube_public_timedtext",
                "coverage": {"extracted": 0},
                "clips": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.benchmark.model_available", lambda: False)
    report = run_benchmark(extractions_path=empty)
    model = next(arm for arm in report["arms"] if arm["arm"] == ARM_MODEL)
    baseline = next(arm for arm in report["arms"] if arm["arm"] == ARM_BASELINE)
    assert baseline["status"] == STATUS_OK
    assert model["status"] == STATUS_NOT_RUN
    assert model["metrics"]["tp"] == 0
    assert model["metrics"]["fp"] == 0


def test_report_round_trip_and_growth_review_reads_the_file(tmp_path):
    report = {
        "pack_id": "benchmark_x5_v1",
        "version": 1,
        "gold_pack_id": "gold_evidence_x5_v1",
        "gold_n_clips": 12,
        "gold_method": "manual_read",
        "note": "Fixture report for UI round-trip.",
        "arms": [
            {
                "arm": ARM_BASELINE,
                "status": STATUS_OK,
                "model": "",
                "metrics": {
                    "precision": 0.1111,
                    "recall": 0.2222,
                    "f1": 0.3333,
                    "quote_grounding_accuracy": 1.0,
                    "tp": 1,
                    "fp": 8,
                    "fn": 3,
                },
            },
            {
                "arm": ARM_MODEL,
                "status": STATUS_OK,
                "model": "fixture-model",
                "metrics": {
                    "precision": 0.4242,
                    "recall": 0.5151,
                    "f1": 0.6060,
                    "quote_grounding_accuracy": 1.0,
                    "tp": 2,
                    "fp": 1,
                    "fn": 2,
                },
            },
        ],
    }
    path = tmp_path / "benchmark_report.json"
    save_report(report, path)
    loaded = load_report(path)
    assert loaded["gold_method"] == "manual_read"
    assert loaded["arms"][1]["metrics"]["f1"] == 0.6060
    html = _benchmark_html(loaded)
    assert 'id="claim-evidence-benchmark"' in html
    assert ARM_BASELINE in html
    assert ARM_MODEL in html
    assert "0.4242" in html
    assert "0.6060" in html
    assert "fixture-model" in html
    assert "12" in html
    empty_html = _benchmark_html({"arms": [], "note": "No benchmark report. Run scripts/run_benchmark.py."})
    assert "Run scripts/run_benchmark.py" in empty_html


def test_committed_benchmark_report_if_present_keeps_grounded_quotes():
    report = load_report()
    if not report.get("arms"):
        return
    model = next((arm for arm in report["arms"] if arm["arm"] == ARM_MODEL), None)
    if not model or model.get("status") != STATUS_OK:
        return
    assert model["metrics"]["quote_grounding_accuracy"] == 1.0
    assert model["metrics"]["predicted_quotes"] == model["metrics"]["grounded_quotes"]
