"""Load the cleaned WeatherSTEM CSV for replay. Only real observations are used."""
from __future__ import annotations

import csv
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .features import BASE_COLS

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_time(text: str) -> datetime:
    return datetime.strptime(text.strip()[:19], TIME_FORMAT)


def load_observations(csv_path: str, start: Optional[datetime] = None,
                      end: Optional[datetime] = None) -> Tuple[List[Dict], int]:
    """Return (rows, skipped). Rows are dicts with a datetime under 'time'.

    Hours the station did not report (blank values left by Milestone 1) are
    skipped, never filled in; the prediction node sees the resulting time gap
    and restarts its history.
    """
    rows, skipped = [], 0
    with open(csv_path, newline="") as f:
        for rec in csv.DictReader(f):
            t = parse_time(rec["datetime"])
            if start is not None and t < start:
                continue
            if end is not None and t > end:
                continue
            try:
                vals = {c: float(rec[c]) for c in BASE_COLS}
            except (ValueError, KeyError):
                skipped += 1
                continue
            if any(math.isnan(v) for v in vals.values()):
                skipped += 1
                continue
            vals["time"] = t
            rows.append(vals)
    return rows, skipped
