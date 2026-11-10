"""Judge one Milestone 5 test run from its ROS 2 launch log. Plain Python, no ROS needed.

The log lines it reads are the ones the nodes already print:

  prediction:       2026-04-18 14:00:00: wind now 4.6 -> next hour 4.5 mph, rain within 3h: False (p=0.01)
  mission_manager:  state NORMAL -> CAUTION (predicted wind 4.5 mph, rain predicted: False)
  mission_manager:  RETURN state: heading back to the dock  /  sending goal: wp2  /  docked, waiting ...
  navigation:       reached 'wp1'  /  reached 'dock'  /  no path to 'x'

A state change and the prediction that caused it are logged within a few milliseconds of each other, so each change is
matched to the nearest prediction line in time. The state for a data hour is the last state set at or before that hour.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

NORMAL, CAUTION, PAUSE, RETURN = "NORMAL", "CAUTION", "PAUSE", "RETURN"
SEVERITY = {NORMAL: 0, CAUTION: 1, PAUSE: 2, RETURN: 3}

LINE = re.compile(r"\[(?P<proc>[\w.-]+)\] \[(?P<level>[A-Z]+)\] \[(?P<t>\d+\.\d+)\] \[(?P<node>[\w./]+)\]: (?P<msg>.*?)\s*$")
PRED = re.compile(r"^(?P<hour>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}): wind now (?P<now>[\d.]+) -> next hour (?P<nxt>[\d.]+) mph, "
                  r"rain within 3h: (?P<rain>True|False) \(p=(?P<p>[\d.]+)\)")
CHANGE = re.compile(r"^state (?P<a>[A-Z]+) -> (?P<b>[A-Z]+) \(predicted wind")
REACHED = re.compile(r"^reached '(?P<name>\w+)'")
SENDING = re.compile(r"^sending goal: (?P<name>\w+)")
FAILURE = re.compile(r"(^goal '.*' failed)|(^skipping ')|(^no path to ')")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MATCH_WINDOW_S = 2.0          # a state change belongs to the prediction logged within this many seconds


@dataclass
class Run:
    predictions: List[dict] = field(default_factory=list)     # {t, hour, wind_next, rain, p}
    changes: List[dict] = field(default_factory=list)         # {t, from, to}
    reached: List[dict] = field(default_factory=list)         # {t, name}
    returns: List[float] = field(default_factory=list)        # time each RETURN started
    failures: List[str] = field(default_factory=list)
    rejections: int = 0
    first_line_t: Optional[float] = None
    last_line_t: Optional[float] = None


def parse_log(text: str) -> Run:
    run = Run()
    for raw in text.splitlines():
        m = LINE.search(ANSI.sub("", raw))
        if not m:
            continue
        t, msg = float(m["t"]), m["msg"]
        run.first_line_t = t if run.first_line_t is None else run.first_line_t
        run.last_line_t = t
        if m["node"] == "prediction":
            p = PRED.match(msg)
            if p:
                run.predictions.append({"t": t, "hour": p["hour"], "wind_next": float(p["nxt"]),
                                        "rain": p["rain"] == "True", "p": float(p["p"])})
            continue
        if m["node"] == "mission_manager":
            c = CHANGE.match(msg)
            if c:
                run.changes.append({"t": t, "from": c["a"], "to": c["b"]})
            elif msg.startswith("RETURN state: heading back to the dock"):
                run.returns.append(t)
            elif FAILURE.search(msg):
                run.failures.append(msg)
            elif re.match(r"^goal '.*' rejected", msg):
                run.rejections += 1
        elif m["node"] == "navigation":
            r = REACHED.match(msg)
            if r:
                run.reached.append({"t": t, "name": r["name"]})
            elif FAILURE.search(msg):
                run.failures.append(msg)
    return run


def states_by_hour(run: Run) -> Dict[str, str]:
    """State the robot was in for each predicted data hour."""
    if not run.predictions:
        return {}
    state_after = [None] * len(run.predictions)          # last change assigned to each prediction
    for c in run.changes:
        j = min(range(len(run.predictions)), key=lambda i: abs(run.predictions[i]["t"] - c["t"]))
        if abs(run.predictions[j]["t"] - c["t"]) <= MATCH_WINDOW_S:
            state_after[j] = c["to"]
    out, cur = {}, NORMAL                                 # the mission manager starts in NORMAL
    for pr, ch in zip(run.predictions, state_after):
        cur = ch or cur
        out[pr["hour"]] = cur
    return out


def run_length(seq: List[str]) -> List[tuple]:
    out = []
    for s in seq:
        if out and out[-1][0] == s:
            out[-1][1] += 1
        else:
            out.append([s, 1])
    return [tuple(x) for x in out]


def describe(seq: List[str], counts: bool = True) -> str:
    rl = run_length(seq)
    return " -> ".join(f"{s} ({n} h)" if counts else s for s, n in rl) if rl else "no data"


def judge(test: dict, run: Run) -> dict:
    """`test` is one entry of config/final_tests.yaml."""
    hours = [h["time"] for h in test["hours"]]
    exp_model = {h["time"]: h["state"] for h in test["hours"]}
    ideal = {h["time"]: h["ideal_state"] for h in test["hours"]}
    by_hour = states_by_hour(run)
    judged = {h: by_hour[h] for h in hours if h in by_hour}
    complete = len(judged) == len(hours)
    allowed = set(test["spec_expected"])
    multiple = "Multiple states" in allowed

    actual_seq = [judged[h] for h in hours if h in judged]
    # the robot always starts in NORMAL while the prediction node warms up; test 5 counts that as its first state
    seq_for_change = ([NORMAL] if multiple else []) + actual_seq
    actual_text = describe(seq_for_change if multiple else actual_seq)

    if multiple:
        distinct = [s for s, _ in run_length(seq_for_change)]
        ordered = all(SEVERITY[a] < SEVERITY[b] for a, b in zip(distinct, distinct[1:]))
        spec_ok = complete and len(distinct) >= 3 and ordered
        spec_text = "Yes" if spec_ok else ("Incomplete" if not complete else f"No ({' -> '.join(distinct)})")
    else:
        n_ok = sum(s in allowed for s in actual_seq)
        spec_ok = complete and n_ok == len(hours)
        spec_text = "Yes" if spec_ok else ("Incomplete" if not complete else f"No ({n_ok} of {len(hours)} h)")

    match_model = sum(judged.get(h) == exp_model[h] for h in hours)
    match_ideal = sum(judged.get(h) == ideal[h] for h in hours)

    # navigation
    wp_reached = [r for r in run.reached if r["name"] != "dock"]
    docked_after = []
    for rt in run.returns:
        docked_after.append(any(r["name"] == "dock" and r["t"] >= rt for r in run.reached))
    moving_states = sum(s in (NORMAL, CAUTION) for s in actual_seq)
    needs_progress = moving_states >= max(1, len(actual_seq) // 2)
    reasons = []
    if run.failures:
        reasons.append(f"{len(run.failures)} goal failure(s)")
    if not all(docked_after):
        reasons.append("did not reach the dock after RETURN")
    if needs_progress and len(wp_reached) < 2:
        reasons.append(f"only {len(wp_reached)} waypoint(s) reached while moving was allowed")
    if not complete:
        reasons.append("log is shorter than the test window")
    nav_ok = not reasons
    return {
        "id": test["id"], "name": test["name"], "spec_expected": test["spec_expected"],
        "judged_hours": len(hours), "hours_logged": len(judged), "complete": complete,
        "actual_text": actual_text, "spec_ok": spec_ok, "spec_text": spec_text,
        "match_model_hours": match_model, "match_ideal_hours": match_ideal,
        "hour_table": [{"time": h, "ideal": ideal[h], "model_offline": exp_model[h], "robot": judged.get(h)} for h in hours],
        "waypoints_reached": len(wp_reached), "returns": len(run.returns),
        "docked_after_every_return": all(docked_after) if docked_after else None,
        "failures": run.failures[:5], "rejections": run.rejections,
        "nav_ok": nav_ok, "nav_text": "Yes" if nav_ok else "No: " + "; ".join(reasons),
    }
