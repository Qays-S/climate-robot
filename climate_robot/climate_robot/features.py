"""Build the Milestone 2 model input row from a short history of observations.

This mirrors the feature engineering in Milestone2_ML_Models.ipynb exactly:
9 current readings, 3 lags of each (1, 2, 3 hours back), and the cyclical
hour / month encodings. The column order is taken from the trained model's
`feature_names_in_`, so it cannot drift from what the model was fitted on.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, List, Sequence

BASE_COLS = [
    "temp_f", "humidity_pct", "wind_speed_mph", "wind_gust_mph",
    "rain_rate_in_hr", "pressure_inhg", "solar_rad_wm2", "uv_index", "wind_dir_deg",
]
LAGS = (1, 2, 3)
HISTORY_NEEDED = max(LAGS) + 1   # current hour plus three previous hours


def build_feature_dict(history: Sequence[Dict[str, float]], when: datetime) -> Dict[str, float]:
    """`history` is oldest -> newest; the last entry is the current hour."""
    if len(history) < HISTORY_NEEDED:
        raise ValueError(f"need {HISTORY_NEEDED} consecutive hours of history, got {len(history)}")
    current = history[-1]
    feats = {c: float(current[c]) for c in BASE_COLS}
    for c in BASE_COLS:
        for lag in LAGS:
            feats[f"{c}_lag{lag}"] = float(history[-1 - lag][c])
    feats["hour_sin"] = math.sin(2 * math.pi * when.hour / 24)
    feats["hour_cos"] = math.cos(2 * math.pi * when.hour / 24)
    feats["month_sin"] = math.sin(2 * math.pi * when.month / 12)
    feats["month_cos"] = math.cos(2 * math.pi * when.month / 12)
    return feats


def to_row(feats: Dict[str, float], feature_names: List[str]):
    """One-row DataFrame in the exact column order the model was trained on."""
    import pandas as pd
    return pd.DataFrame([[feats[n] for n in feature_names]], columns=list(feature_names))
