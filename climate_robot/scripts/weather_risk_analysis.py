"""Milestone 4 analysis: wind thresholds, risk-state distribution, and a demo replay window.

  python3 scripts/weather_risk_analysis.py --data-dir ~/ros2_ws

Reads weatherstem_cleaned_hourly.csv + the two Milestone 2 models, then
  1. computes the wind p75 / p90 thresholds from the real data,
  2. runs the models over every hour with a full 4-hour history and applies the risk rules,
  3. finds a real period that passes through NORMAL -> CAUTION -> PAUSE -> RETURN,
  4. writes config/thresholds.yaml and docs/weather_event.png.
"""
import argparse
import os
import sys
from datetime import timedelta

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from climate_robot import state_machine as sm  # noqa: E402
from climate_robot.features import HISTORY_NEEDED, build_feature_dict  # noqa: E402
from climate_robot.weather_data import load_observations  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default=os.path.expanduser("~/ros2_ws"))
ap.add_argument("--window-hours", type=int, default=14)
ap.add_argument("--train-through", type=int, default=2025,
                help="thresholds use data up to this year (the Milestone 2 training years); later years are the held-out test set")
args = ap.parse_args()

csv_path = os.path.join(args.data_dir, "weatherstem_cleaned_hourly.csv")
wind_m = joblib.load(os.path.join(args.data_dir, "best_wind_model.joblib"))
rain_m = joblib.load(os.path.join(args.data_dir, "best_rain_model.joblib"))
names = list(wind_m.feature_names_in_)
rain_idx = list(rain_m.classes_).index(1.0)

rows, skipped = load_observations(csv_path)
wind_obs = np.array([r["wind_speed_mph"] for r in rows if r["time"].year <= args.train_through])
P75, P90 = (round(float(np.percentile(wind_obs, q)), 2) for q in (75, 90))
print(f"{len(rows)} usable hours ({skipped} outage hours skipped); thresholds from {len(wind_obs)} training hours (<= {args.train_through})")
print(f"wind_speed_mph  p75 = {P75}   p90 = {P90}")

meta, feats, hist = [], [], []
for r in rows:
    if hist and r["time"] - hist[-1]["time"] != timedelta(hours=1):
        hist = []
    hist = (hist + [r])[-HISTORY_NEEDED:]
    if len(hist) < HISTORY_NEEDED:
        continue
    f = build_feature_dict(hist, r["time"])
    feats.append([f[n] for n in names])
    meta.append((r["time"], r["wind_speed_mph"]))
X = pd.DataFrame(feats, columns=names)
df = pd.DataFrame(meta, columns=["time", "wind_now"])
df["wind_pred"] = wind_m.predict(X)
df["rain_p"] = rain_m.predict_proba(X)[:, rain_idx]
df["rain_pred"] = rain_m.predict(X) == 1.0
df["state"] = [sm.decide_state(w, b, P75, P90) for w, b in zip(df.wind_pred, df.rain_pred)]
print((df.state.value_counts(normalize=True) * 100).round(1).to_string())

df = df[df.time.dt.year > args.train_through].reset_index(drop=True)   # held-out test data only
print((df.state.value_counts(normalize=True) * 100).round(1).to_string(), "(test years only)")

# first window in the held-out test years with all four states and a recovery after the last RETURN
order = [sm.NORMAL, sm.CAUTION, sm.PAUSE, sm.RETURN]
consecutive = df.time.diff().eq(pd.Timedelta(hours=1))
seg = (~consecutive).cumsum()
L = args.window_hours
found = None
for _, g in df.groupby(seg):
    g = g.reset_index(drop=True)
    for i in range(len(g) - L + 1):
        w = g.iloc[i:i + L]
        st = list(w.state)
        if not set(order) <= set(st):
            continue
        if st.index(sm.NORMAL) > st.index(sm.RETURN):   # tell the story in order: calm first
            continue
        last_return = max(k for k, x in enumerate(st) if x == sm.RETURN)
        if any(x in (sm.NORMAL, sm.CAUTION) for x in st[last_return + 1:]):
            found = w
            break
    if found is not None:
        break
if found is None:
    sys.exit("no window with all four states and a recovery in the test years")
start_replay = found.time.iloc[0] - timedelta(hours=HISTORY_NEEDED - 1)
print(f"demo window: {found.time.iloc[0]} .. {found.time.iloc[-1]}")
print(f"start the replay at start_time = {start_replay:%Y-%m-%d %H:%M:%S}")

with open(os.path.join(ROOT, "config", "thresholds.yaml"), "w") as f:
    f.write(f"# Wind thresholds from real WeatherSTEM data, training years only (<= {args.train_through}), observed hours only\n")
    f.write(f"wind_p75: {P75}\nwind_p90: {P90}\n")
    f.write(f"demo_start_time: \"{start_replay:%Y-%m-%d %H:%M:%S}\"\n")

# ---- figure ----
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"
STATE_FILL = {sm.NORMAL: "#e9f3ea", sm.CAUTION: "#fbe9b7", sm.PAUSE: "#f6c7a8", sm.RETURN: "#f1a4a3"}
t = found.time
fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 7.2), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 2, 1]})
for ax in (a1, a2, a3):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
a1.plot(t, found.wind_pred, color=BLUE, lw=2, marker="o", ms=5, mec="white", label="predicted wind, next hour")
a1.plot(t, found.wind_now, color=MUTED, lw=1.2, ls=":", label="observed wind now")
for val, lab, dy, va in ((P75, f"p75 = {P75} mph", -0.12, "top"), (P90, f"p90 = {P90} mph", 0.12, "bottom")):
    a1.axhline(val, color=MUTED, lw=1, ls="--")
    a1.text(t.iloc[len(t) // 2], val + dy, lab, color=MUTED, fontsize=9, ha="center", va=va)
a1.set_ylabel("wind (mph)", color=MUTED)
a1.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, 0.88))
a1.set_title("Real weather event: model predictions and the robot's risk state", loc="left", color=INK, fontsize=13)
a2.plot(t, found.rain_p, color=ORANGE, lw=2, marker="o", ms=5, mec="white")
a2.axhline(0.5, color=MUTED, lw=1, ls="--")
a2.text(t.iloc[1], 0.53, "rain predicted when probability >= 0.5", color=MUTED, fontsize=9, ha="left")
a2.set_ylim(0, 1); a2.set_ylabel("P(rain in 3 h)", color=MUTED)
for ax in (a1, a2):
    ax.grid(axis="y", color=GRID, lw=0.8)
for i, (ts, s) in enumerate(zip(t, found.state)):
    a3.axvspan(ts - timedelta(minutes=30), ts + timedelta(minutes=30), color=STATE_FILL[s], lw=0)
    a3.text(ts, 0.5, s, ha="center", va="center", fontsize=8, color=INK, rotation=90)
a3.set_yticks([]); a3.set_ylabel("state", color=MUTED)
a3.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))
a3.set_xlabel(f"hour on {t.iloc[0]:%Y-%m-%d}", color=MUTED)
fig.tight_layout()
out = os.path.join(ROOT, "docs", "weather_event.png")
fig.savefig(out, dpi=140)
print("saved", out)
