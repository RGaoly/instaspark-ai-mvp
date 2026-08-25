"""Score the keyword baseline and Evidence Reader against the gold set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.benchmark import load_gold, run_benchmark, save_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default="", help="Optional gold-set path")
    parser.add_argument("--out", default="", help="Optional report path")
    args = parser.parse_args()
    kwargs = {}
    if args.gold:
        kwargs["gold_path"] = args.gold
    report = run_benchmark(**kwargs)
    target = Path(args.out) if args.out else ROOT / "data" / "benchmark_report.json"
    save_report(report, target)
    print(json.dumps({
        "gold_n_clips": report["gold_n_clips"],
        "gold_method": report["gold_method"],
        "arms": [
            {
                "arm": arm["arm"],
                "status": arm["status"],
                "metrics": arm["metrics"],
                "model": arm.get("model") or None,
            }
            for arm in report["arms"]
        ],
    }, ensure_ascii=False, indent=2))
    load_gold(args.gold or ROOT / "data" / "gold_evidence_labels.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
