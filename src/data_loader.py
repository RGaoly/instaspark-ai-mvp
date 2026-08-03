from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


def load_creators(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["markets", "languages", "topics", "styles", "evidence", "risks"]:
        df[col] = df[col].fillna("").apply(
            lambda value: [item.strip() for item in str(value).split("|") if item.strip()]
        )
    return df


def load_mission(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
