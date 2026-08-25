"""Populate the Evidence Reader cache from real public YouTube captions.

Reads every clip in ``data/youtube_intensive_clips.json`` whose
``caption_body_status`` is ``downloaded_public_timedtext``, sends only the caption
lines plus the Product DNA claim list to the configured LLM, validates the returned
quotes against those caption lines, and writes the versioned pack to
``data/evidence_extractions.json`` so 8501 works offline afterwards.

Usage:
    .venv/bin/python -m scripts.run_evidence_reader [--limit N] [--workers N] [--out PATH]

No secret value is printed. Without a model key every row is written as
``unavailable_no_model``.
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import evidence_reader  # noqa: E402
from src.product_dna import load_product_dna  # noqa: E402
from src.youtube_clips import load_youtube_intensive_clips  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Evidence Reader agent over public caption bodies.")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of clips (recorded in coverage).")
    parser.add_argument("--workers", type=int, default=6, help="Parallel model calls.")
    parser.add_argument("--out", type=Path, default=evidence_reader.DEFAULT_EXTRACTIONS_PATH)
    args = parser.parse_args()

    dna = load_product_dna()
    clips = load_youtube_intensive_clips().get("clips") or []
    pool = evidence_reader.eligible_clips(clips)
    available = evidence_reader.model_available()
    print(f"eligible caption-body clips: {len(pool)} · model configured: {available}")
    if not available:
        print("No model key resolved. Writing an honest unavailable_no_model pack.")

    lock = threading.Lock()
    seen = {"n": 0}

    def on_result(result: dict) -> None:
        with lock:
            seen["n"] += 1
            supported = sum(1 for claim in result["claims"] if claim["supported"])
            rejected = int(result["grounding"].get("rejected_hallucinated_quotes", 0)) + int(
                result["grounding"].get("rejected_unknown_timestamps", 0)
            )
            print(
                f"[{seen['n']}] {result['post_id']} {result['creator_id']} "
                f"status={result['status']} supported={supported} rejected={rejected}",
                flush=True,
            )

    pack = evidence_reader.extract_pack(
        clips,
        dna,
        limit=args.limit,
        workers=max(1, int(args.workers)),
        on_result=on_result,
    )
    path = evidence_reader.save_pack(pack, args.out)
    coverage = pack["coverage"]
    print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    print(
        "coverage: "
        f"eligible={coverage['eligible_clips']} attempted={coverage['attempted_clips']} "
        f"extracted={coverage['extracted']} error={coverage['error']} "
        f"no_model={coverage['unavailable_no_model']} supported_claims={coverage['supported_claims']} "
        f"grounded_clips={coverage['grounded_clips']} grounded_creators={coverage['grounded_creators']} "
        f"rejected_quotes={coverage['rejected_hallucinated_quotes']} "
        f"rejected_timestamps={coverage['rejected_unknown_timestamps']} retimed={coverage['retimed_quotes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
