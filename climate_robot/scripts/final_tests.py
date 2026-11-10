"""Milestone 5 (offline part): measure the models on the held-out year and choose the five real test windows.

  python3 scripts/final_tests.py --data-dir ~/ros2_ws

Uses only real WeatherSTEM hours from the held-out test years (after --train-through). Nothing is synthetic.

What it does
  1. Wind thresholds p75 / p90 from the training years only (same as Milestone 4).
  2. Runs the Milestone 2 models over every test hour that has a full 4-hour history.
  3. ML accuracy on the test year: wind (MAE, RMSE, R2, vs "same as now" baseline) and rain (accuracy,
     precision, recall, F1, AUC), with the same targets Milestone 2 used.
  4. State accuracy: how often the robot's state equals the state the same rules would give if the next hour's
     wind and the next 3 hours of rain were known exactly.
  5. Picks one real window per required test. Windows are chosen from the OBSERVED weather only, by the
     rules printed in docs/final_tests_offline.md, never by what the models predict, so a failing test cannot
     be hidden by choosing a better window. Then it records what the models say for each hour.

Writes config/final_tests.yaml (read by run_final_tests.py / evaluate_tests.py), docs/final_tests_offline.md and
docs/ml_test_metrics.json.
"""
import argparse
import json
import os
import sys
from datetime import timedelta

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from climate_robot import state_machine as sm  # noqa: E402
from climate_robot.features import HISTORY_NEEDED, build_feature_dict  # noqa: E402
from climate_robot.weather_data import load_observations  # noqa: E402

STATES = [sm.NORMAL, sm.CAUTION, sm.PAUSE, sm.RETURN]
WARMUP_HOURS = HISTORY_NEEDED - 1          # the prediction node needs 4 hours; the first 3 only fill its history
EVAL_HOURS = 6                             # hours judged in tests 1-4
CHANGE_HOURS = 12                          # hours judged in test 5


def build_frame(data_dir, train_through):
    csv_path = os.path.join(data_dir, "weatherstem_cleaned_hourly.csv")
    wind_m = joblib.load(os.path.join(data_dir, "best_wind_model.joblib"))
    rain_m = joblib.load(os.path.join(data_dir, "best_rain_model.joblib"))
    names = list(wind_m.feature_names_in_)
    rain_idx = list(rain_m.classes_).index(1.0)
    rows, skipped = load_observations(csv_path)
    by_time = {r["time"]: r for r in rows}
    train_rows = [r for r in rows if r["time"].year <= train_through]
    p75, p90 = (round(float(np.percentile([r["wind_speed_mph"] for r in train_rows], q)), 2) for q in (75, 90))

    meta, feats, hist = [], [], []
    for r in rows:
        if hist and r["time"] - hist[-1]["time"] != timedelta(hours=1):
            hist = []
        hist = (hist + [r])[-HISTORY_NEEDED:]
        if len(hist) < HISTORY_NEEDED:
            continue
        f = build_feature_dict(hist, r["time"])
        feats.append([f[n] for n in names])
        meta.append(r)
    X = pd.DataFrame(feats, columns=names)
    df = pd.DataFrame(meta)
    df["wind_pred"] = wind_m.predict(X)
    df["rain_p"] = rain_m.predict_proba(X)[:, rain_idx]
    df["rain_pred"] = rain_m.predict(X) == 1.0
    df["state"] = [sm.decide_state(w, b, p75, p90) for w, b in zip(df.wind_pred, df.rain_pred)]

    # what actually happened next (same targets Milestone 2 trained on); NaN when an hour is missing
    wn, rn = [], []
    for t in df.time:
        nxt = by_time.get(t + timedelta(hours=1))
        wn.append(nxt["wind_speed_mph"] if nxt else np.nan)
        fut = [by_time.get(t + timedelta(hours=h)) for h in (1, 2, 3)]
        rn.append(np.nan if any(x is None for x in fut) else float(any(x["rain_rate_in_hr"] > 0 for x in fut)))
    df["wind_next"] = wn
    df["rain_next3"] = rn
    # the state the same rules give if the next hour's wind and the next 3 hours of rain were known exactly
    df["ideal"] = [sm.decide_state(w, bool(r), p75, p90) if not (np.isnan(w) or np.isnan(r)) else None
                   for w, r in zip(df.wind_next, df.rain_next3)]
    return df, train_rows, p75, p90, skipped, len(rows)


def ml_metrics(test):
    out = {}
    w = test.dropna(subset=["wind_next"])
    rmse = lambda a, b: float(np.sqrt(mean_squared_error(a, b)))
    out["wind"] = {
        "n": int(len(w)),
        "mae": float(mean_absolute_error(w.wind_next, w.wind_pred)),
        "rmse": rmse(w.wind_next, w.wind_pred),
        "r2": float(r2_score(w.wind_next, w.wind_pred)),
        "baseline_same_as_now_mae": float(mean_absolute_error(w.wind_next, w.wind_speed_mph)),
        "baseline_same_as_now_rmse": rmse(w.wind_next, w.wind_speed_mph),
    }
    r = test.dropna(subset=["rain_next3"])
    y, yhat = r.rain_next3.astype(int), r.rain_pred.astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    out["rain"] = {
        "n": int(len(r)), "rain_rate": float(y.mean()),
        "accuracy": float(accuracy_score(y, yhat)), "precision": float(precision_score(y, yhat)),
        "recall": float(recall_score(y, yhat)), "f1": float(f1_score(y, yhat)),
        "auc": float(roc_auc_score(y, r.rain_p)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }
    return out


def state_agreement(test, p75, p90):
    d = test.dropna(subset=["ideal"]).copy()
    cm = pd.crosstab(d.ideal, d.state).reindex(index=STATES, columns=STATES, fill_value=0)
    n = int(len(d))
    res = {"n": n, "agree": float((d.ideal == d.state).mean()),
           "confusion_ideal_rows_vs_system_cols": cm.to_dict(orient="index"),
           "recall_by_ideal_state": {s: (float(cm.loc[s, s] / cm.loc[s].sum()) if cm.loc[s].sum() else None) for s in STATES}}
    stop = {sm.PAUSE, sm.RETURN}
    need = d[d.ideal.isin(stop)]
    res["stop_needed_hours"] = int(len(need))
    res["stop_needed_missed_as_normal"] = float((need.state == sm.NORMAL).mean()) if len(need) else None
    res["stop_needed_slowed_or_stopped"] = float((need.state != sm.NORMAL).mean()) if len(need) else None
    calm = d[d.ideal == sm.NORMAL]
    res["calm_hours"] = int(len(calm))
    res["calm_hours_stopped_needlessly"] = float(calm.state.isin(stop).mean()) if len(calm) else None
    return res


def windows(test, n):
    """All runs of n consecutive hours in the test frame."""
    seg = (~test.time.diff().eq(pd.Timedelta(hours=1))).cumsum()
    for _, g in test.groupby(seg):
        g = g.reset_index(drop=True)
        for i in range(len(g) - n + 1):
            yield g.iloc[i:i + n]


def pick(cands, key, take_max=False):
    best = None
    for w in cands:
        k = key(w)
        if best is None or (k > best[0] if take_max else k < best[0]):
            best = (k, w)
    return None if best is None else best[1]


def choose_windows(test, train_rows, p75, p90):
    tr = pd.DataFrame(train_rows)
    lower = lambda col, v: np.searchsorted(np.sort(tr[col].values), v, side="left") / len(tr)   # share of training hours strictly below
    test = test.copy()
    test["risk"] = lower("wind_speed_mph", test.wind_speed_mph) + lower("wind_gust_mph", test.wind_gust_mph) \
        + lower("rain_rate_in_hr", test.rain_rate_in_hr)
    med = test[["wind_speed_mph", "temp_f", "humidity_pct"]].median()
    iqr = (test[["wind_speed_mph", "temp_f", "humidity_pct"]].quantile(.75) - test[["wind_speed_mph", "temp_f", "humidity_pct"]].quantile(.25))
    mid = (p75 + p90) / 2
    all_ideal = lambda w, st: (w.ideal == st).all()

    picks = {}
    picks[1] = pick((w for w in windows(test, EVAL_HOURS) if all_ideal(w, sm.NORMAL) and (w.wind_speed_mph < p75).all()),
                    lambda w: sum(abs(w[c].mean() - med[c]) / iqr[c] for c in med.index))
    picks[2] = pick((w for w in windows(test, EVAL_HOURS)
                     if all_ideal(w, sm.CAUTION) and w.wind_speed_mph.between(p75, p90, inclusive="left").all()),
                    lambda w: (w.wind_next - mid).abs().mean())
    picks[3] = pick((w for w in windows(test, EVAL_HOURS) if (w.rain_rate_in_hr > 0).sum() >= EVAL_HOURS - 1 and (w.wind_speed_mph < p90).all()),
                    lambda w: w.rain_rate_in_hr.sum(), take_max=True)
    picks[4] = pick(windows(test, EVAL_HOURS), lambda w: w.risk.mean(), take_max=True)

    def rising(w):
        st = list(w.ideal)
        order = [sm.NORMAL, sm.CAUTION, sm.PAUSE]
        if st[0] != sm.NORMAL or st[-1] != sm.PAUSE or sm.RETURN in st or any(x not in order for x in st):
            return False, 0
        first = [st.index(x) if x in st else None for x in order]
        return None not in first and first == sorted(first), sum(a != b for a, b in zip(st, st[1:]))
    c5 = [(rising(w)[1], w) for w in windows(test, CHANGE_HOURS) if rising(w)[0]]
    picks[5] = min(c5, key=lambda x: (x[0], x[1].time.iloc[0]))[1] if c5 else None
    return picks, med


TESTS = {
    1: ("Typical weather", ["NORMAL"], "Hours where the real wind is below p75 both now and in the next hour, with no rain, closest to the test-year median wind, temperature and humidity."),
    2: ("Elevated wind", ["CAUTION"], "Hours where the real wind is steadily in the upper band, p75 to p90, both now and in the next hour, with no rain, closest to the middle of that band."),
    3: ("Rain", ["CAUTION", "PAUSE"], "Hours with measured rain in at least 5 of 6 hours, wind below p90, the largest total rain rate."),
    4: ("High environmental risk", ["PAUSE", "RETURN"], "The 6 hours with the highest combined risk of wind speed, gusts and rain rate, each scored by the share of training hours it beats."),
    5: ("Changing weather", ["Multiple states"], "12 hours in which the real next-hour wind rises from below p75, through p75 to p90, to p90 or more, with no rain and the fewest back-and-forth changes."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.path.expanduser("~/ros2_ws"))
    ap.add_argument("--train-through", type=int, default=2025)
    args = ap.parse_args()

    df, train_rows, p75, p90, skipped, n_rows = build_frame(args.data_dir, args.train_through)
    test = df[df.time.dt.year > args.train_through].reset_index(drop=True)
    print(f"{n_rows} usable hours ({skipped} outage hours skipped); {len(train_rows)} training hours; "
          f"{len(test)} test hours with a full history ({test.time.min()} .. {test.time.max()})")
    print(f"wind thresholds from training years: p75 = {p75}  p90 = {p90}")

    metrics = {"thresholds": {"wind_p75": p75, "wind_p90": p90}, "train_hours": len(train_rows), "test_hours": int(len(test)),
               "test_range": [str(test.time.min()), str(test.time.max())]}
    metrics.update(ml_metrics(test))
    metrics["state_agreement"] = state_agreement(test, p75, p90)
    metrics["state_mix_test"] = {s: int((test.state == s).sum()) for s in STATES}

    picks, med = choose_windows(test, train_rows, p75, p90)
    plan, missing = [], []
    for tid, (name, spec, rule) in TESTS.items():
        w = picks[tid]
        if w is None:
            missing.append(tid)
            continue
        w = w.reset_index(drop=True)
        start = w.time.iloc[0] - timedelta(hours=WARMUP_HOURS)
        hrs = [{"time": f"{r.time:%Y-%m-%d %H:%M:%S}", "state": r.state, "ideal_state": r.ideal, "wind_pred": round(float(r.wind_pred), 2),
                "rain_p": round(float(r.rain_p), 3), "wind_now": round(float(r.wind_speed_mph), 2),
                "gust_now": round(float(r.wind_gust_mph), 2), "wind_next": round(float(r.wind_next), 2), "rain_rate_now": round(float(r.rain_rate_in_hr), 6)}
               for r in w.itertuples()]
        plan.append({"id": tid, "name": name, "spec_expected": spec, "selection_rule": rule,
                     "start_time": f"{start:%Y-%m-%d %H:%M:%S}", "first_judged_hour": hrs[0]["time"],
                     "judged_hours": len(hrs), "warmup_hours": WARMUP_HOURS, "hours": hrs})
    if missing:
        sys.exit(f"no real window found for test(s) {missing}")
    # windows must not share hours
    seen = set()
    for t in plan:
        hs = {h["time"] for h in t["hours"]}
        if hs & seen:
            sys.exit(f"test {t['id']} overlaps another test's hours")
        seen |= hs

    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "config", "final_tests.yaml"), "w") as f:
        f.write("# Milestone 5: real held-out windows. Generated by scripts/final_tests.py - do not edit by hand.\n")
        yaml.safe_dump({"wind_p75": p75, "wind_p90": p90, "replay_period_s": 10.0, "tests": plan}, f, sort_keys=False, width=120)
    with open(os.path.join(ROOT, "docs", "ml_test_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # ---- readable summary ----
    L = []
    w, r, sa = metrics["wind"], metrics["rain"], metrics["state_agreement"]
    L += ["# Milestone 5: offline results on the held-out year", "",
          f"Test hours: {len(test)} real hours, {metrics['test_range'][0][:10]} to {metrics['test_range'][1][:10]}. "
          f"Wind thresholds from the {len(train_rows)} training hours: p75 = {p75} mph, p90 = {p90} mph.", "",
          "## Machine learning accuracy (test year)", "",
          "| Model | Measure | Value |", "| --- | --- | --- |",
          f"| Wind, 1 h ahead (random forest) | MAE | {w['mae']:.3f} mph |",
          f"| | RMSE | {w['rmse']:.3f} mph |", f"| | R2 | {w['r2']:.3f} |",
          f"| | Baseline \"same as now\" MAE / RMSE | {w['baseline_same_as_now_mae']:.3f} / {w['baseline_same_as_now_rmse']:.3f} mph |",
          f"| Rain within 3 h (random forest) | Accuracy | {r['accuracy']:.3f} |",
          f"| | Precision | {r['precision']:.3f} |", f"| | Recall | {r['recall']:.3f} |",
          f"| | F1 | {r['f1']:.3f} |", f"| | AUC | {r['auc']:.3f} |",
          f"| | Share of hours followed by rain | {r['rain_rate']:.3f} |", "",
          "## Did the robot pick the right state? (whole test year)", "",
          f"The ideal state is what the same rules give if the next hour's wind and the next 3 hours of rain were known exactly. "
          f"Over {sa['n']} hours the robot's state matched it {sa['agree']*100:.1f}% of the time.", "",
          "| Ideal state | Hours | Robot chose the same |", "| --- | --- | --- |"]
    cm = sa["confusion_ideal_rows_vs_system_cols"]
    for s in STATES:
        tot = sum(cm[s].values())
        rec = sa["recall_by_ideal_state"][s]
        L.append(f"| {s} | {tot} | {'n/a' if rec is None else f'{rec*100:.1f}%'} |")
    L += ["", f"- Hours where PAUSE or RETURN was ideal ({sa['stop_needed_hours']}): the robot kept going at NORMAL in {sa['stop_needed_missed_as_normal']*100:.1f}%.",
          f"- Calm hours ({sa['calm_hours']}): the robot stopped needlessly in {sa['calm_hours_stopped_needlessly']*100:.1f}%.", "",
          "## The five test windows", "",
          "Each window is replayed at 10 s per hour. The first 3 hours only fill the prediction node's history, then 6 hours are judged (12 for test 5).", "",
          "| Test | Spec expects | Replay start_time | Judged hours | Ideal states (real weather) | Model states |", "| --- | --- | --- | --- | --- | --- |"]
    for t in plan:
        seq = " ".join(h["state"][0] for h in t["hours"])
        ideal = " ".join((h["ideal_state"] or "?")[0] for h in t["hours"])
        L.append(f"| {t['id']} {t['name']} | {' / '.join(t['spec_expected'])} | {t['start_time']} | {t['first_judged_hour']} + {t['judged_hours']-1} h | {ideal} | {seq} |")
    L += ["", "(N = NORMAL, C = CAUTION, P = PAUSE, R = RETURN.)", "", "## How each window was chosen", ""]
    for t in plan:
        L.append(f"- **Test {t['id']} {t['name']}:** {t['selection_rule']}")
    L += ["", "## Observed weather in each window", "", "| Test | Hour | Wind now (mph) | Gust (mph) | Rain rate (in/h) | Real wind next hour | Predicted wind next hour | Rain probability | Ideal | State |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for t in plan:
        for h in t["hours"]:
            L.append(f"| {t['id']} | {h['time'][5:16]} | {h['wind_now']} | {h['gust_now']} | {h['rain_rate_now']} | {h['wind_next']} | {h['wind_pred']} | {h['rain_p']} | {h['ideal_state']} | {h['state']} |")
    with open(os.path.join(ROOT, "docs", "final_tests_offline.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:60]))
    print("\nwrote config/final_tests.yaml, docs/final_tests_offline.md, docs/ml_test_metrics.json")


if __name__ == "__main__":
    main()
