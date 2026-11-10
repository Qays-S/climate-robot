"""Milestone 5 figures for the report and the presentation.

  python3 scripts/make_m5_figures.py --data-dir ~/ros2_ws      (run scripts/final_tests.py first)

  docs/ml_test_results.png      real vs predicted next-hour wind, and the rain confusion matrix, on the 2026 test year
  docs/final_tests_overview.png the five real test windows: observed and predicted wind, thresholds, robot state per hour
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from final_tests import build_frame  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"
STATE_FILL = {"NORMAL": "#e9f3ea", "CAUTION": "#fbe9b7", "PAUSE": "#f6c7a8", "RETURN": "#f1a4a3"}


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)


def ml_figure(data_dir, metrics):
    df, _, p75, p90, _, _ = build_frame(data_dir, 2025)
    test = df[df.time.dt.year > 2025].dropna(subset=["wind_next"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.4), gridspec_kw={"width_ratios": [1.25, 1]})
    style(a)
    a.scatter(test.wind_next, test.wind_pred, s=7, alpha=0.22, color=BLUE, linewidths=0)
    lim = max(test.wind_next.max(), test.wind_pred.max()) + 0.5
    a.plot([0, lim], [0, lim], color=MUTED, lw=1, ls="--")
    for v in (p75, p90):
        a.axvline(v, color=GRID, lw=1.2, zorder=0)
        a.axhline(v, color=GRID, lw=1.2, zorder=0)
    a.set_xlim(0, lim); a.set_ylim(0, lim)
    a.set_xlabel("real wind next hour (mph)", color=MUTED); a.set_ylabel("predicted wind (mph)", color=MUTED)
    a.set_title("Wind, 1 hour ahead: 2026 test year", loc="left", color=INK, fontsize=12)
    w = metrics["wind"]
    a.text(0.03, 0.96, f"MAE {w['mae']:.2f} mph   RMSE {w['rmse']:.2f} mph   R² {w['r2']:.2f}\n"
           f"\"same as now\" MAE {w['baseline_same_as_now_mae']:.2f} mph", transform=a.transAxes, va="top", fontsize=9.5, color=INK)
    a.text(p75 + 0.15, 0.25, f"p75 {p75}", fontsize=8, color=MUTED, rotation=90)
    a.text(p90 + 0.15, 0.25, f"p90 {p90}", fontsize=8, color=MUTED, rotation=90)

    r = metrics["rain"]
    cm = np.array([[r["tn"], r["fp"]], [r["fn"], r["tp"]]])
    b.imshow(cm / cm.sum(axis=1, keepdims=True), cmap="Blues", vmin=0, vmax=1)
    for i in range(2):
        for j in range(2):
            share = cm[i, j] / cm[i].sum()
            b.text(j, i, f"{cm[i, j]:,}\n{share*100:.0f}% of row", ha="center", va="center", fontsize=10,
                   color="white" if share > 0.55 else INK)
    b.set_xticks([0, 1], ["no rain\npredicted", "rain\npredicted"], color=MUTED, fontsize=9)
    b.set_yticks([0, 1], ["no rain\nin next 3 h", "rain\nin next 3 h"], color=MUTED, fontsize=9)
    b.spines[:].set_visible(False); b.tick_params(length=0)
    b.set_title("Rain within 3 hours", loc="left", color=INK, fontsize=12)
    b.set_xlabel(f"accuracy {r['accuracy']:.2f}   precision {r['precision']:.2f}   recall {r['recall']:.2f}   F1 {r['f1']:.2f}",
                 color=MUTED, fontsize=9.5)
    fig.tight_layout()
    out = os.path.join(ROOT, "docs", "ml_test_results.png")
    fig.savefig(out, dpi=150)
    print("saved", out)


def tests_figure(cfg):
    p75, p90 = cfg["wind_p75"], cfg["wind_p90"]
    tests = {t["id"]: t for t in cfg["tests"]}
    fig = plt.figure(figsize=(11, 9.4))
    gs = fig.add_gridspec(3, 2, hspace=0.62, wspace=0.16, top=0.9, bottom=0.07, left=0.07, right=0.98)
    slots = {1: gs[0, 0], 2: gs[0, 1], 3: gs[1, 0], 4: gs[1, 1], 5: gs[2, :]}
    ymax = 14.2
    for tid, slot in slots.items():
        t = tests[tid]
        ax = fig.add_subplot(slot)
        style(ax)
        hs = t["hours"]
        x = np.arange(len(hs))
        for i, h in enumerate(hs):
            ax.axvspan(i - 0.5, i + 0.5, ymin=0, ymax=0.1, color=STATE_FILL[h["state"]], lw=0)
            ax.axvspan(i - 0.5, i + 0.5, ymin=0.1, ymax=1, color=STATE_FILL[h["state"]], alpha=0.35, lw=0)
            ax.text(i, ymax * 0.05, h["state"][0], ha="center", va="center", fontsize=8.5, color=INK)
            if h["rain_rate_now"] > 0:
                ax.plot(i, ymax * 0.93, marker="v", color=ORANGE, ms=6, mec="white", mew=0.6)
        ax.plot(x, [h["wind_now"] for h in hs], color=MUTED, lw=1.3, ls=":", marker="o", ms=3.5, label="observed wind now")
        ax.plot(x, [h["wind_pred"] for h in hs], color=BLUE, lw=2.2, marker="o", ms=5, mec="white", label="predicted wind, next hour")
        for v, lab in ((p75, f"p75 {p75}"), (p90, f"p90 {p90}")):
            ax.axhline(v, color=MUTED, lw=0.9, ls="--")
            ax.text(len(hs) - 0.45, v + 0.15, lab, fontsize=8, color=MUTED, ha="right", va="bottom")
        ax.set_ylim(0, ymax); ax.set_xlim(-0.5, len(hs) - 0.5)
        ax.set_xticks(x[::1 if len(hs) <= 6 else 2], [h["time"][5:13].replace(" ", " ") + "h" for h in hs][::1 if len(hs) <= 6 else 2], fontsize=8)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_ylabel("wind (mph)", color=MUTED, fontsize=9)
        ax.set_title(f"Test {tid}: {t['name']}   (spec expects {' / '.join(t['spec_expected'])})", loc="left", color=INK, fontsize=10.5)
        if tid == 1:
            ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, 0.9))
    fig.suptitle("Five real test windows from the held-out 2026 data", x=0.07, ha="left", fontsize=14, color=INK, y=0.975)
    handles = [Patch(color=STATE_FILL[s], label=f"{s[0]} = {s}") for s in STATE_FILL]
    handles.append(plt.Line2D([], [], marker="v", color=ORANGE, ls="", ms=6, label="rain measured that hour"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.065, 0.955), ncol=5, frameon=False, fontsize=8.5)
    out = os.path.join(ROOT, "docs", "final_tests_overview.png")
    fig.savefig(out, dpi=150)
    print("saved", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.path.expanduser("~/ros2_ws"))
    args = ap.parse_args()
    metrics = json.load(open(os.path.join(ROOT, "docs", "ml_test_metrics.json")))
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "final_tests.yaml")))
    ml_figure(args.data_dir, metrics)
    tests_figure(cfg)
