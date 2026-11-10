"""Milestone 5 log judge, checked against real log lines from the Milestone 4 run (Linux machine, 2026-10-26)."""
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from climate_robot.final_eval import judge, parse_log, states_by_hour  # noqa: E402

REAL_LOG = """\
[navigation-2] [INFO] [1793034572.075656154] [navigation]: reached 'wp1'
[mission_manager-5] [INFO] [1793034573.142998062] [mission_manager]: sending goal: wp2
[prediction-4] [INFO] [1793034565.827067948] [prediction]: warming up (1/4 hours)
[prediction-4] [INFO] [1793034585.819578096] [prediction]: warming up (3/4 hours)
[navigation-2] [INFO] [1793034583.764382628] [navigation]: reached 'wp2'
[mission_manager-5] [INFO] [1793034595.998369538] [mission_manager]: state NORMAL -> CAUTION (predicted wind 4.5 mph, rain predicted: False)
[prediction-4] [INFO] [1793034595.998522962] [prediction]: 2026-04-18 14:00:00: wind now 4.6 -> next hour 4.5 mph, rain within 3h: False (p=0.01)
[prediction-4] [INFO] [1793034606.186549174] [prediction]: 2026-04-18 15:00:00: wind now 5.0 -> next hour 4.9 mph, rain within 3h: False (p=0.01)
[mission_manager-5] [INFO] [1793034616.028695706] [mission_manager]: state CAUTION -> NORMAL (predicted wind 4.0 mph, rain predicted: False)
[prediction-4] [INFO] [1793034616.028844313] [prediction]: 2026-04-18 16:00:00: wind now 4.1 -> next hour 4.0 mph, rain within 3h: False (p=0.01)
[prediction-4] [INFO] [1793034626.113308298] [prediction]: 2026-04-18 17:00:00: wind now 3.1 -> next hour 2.8 mph, rain within 3h: False (p=0.02)
[prediction-4] [INFO] [1793034636.115758303] [prediction]: 2026-04-18 18:00:00: wind now 2.8 -> next hour 2.3 mph, rain within 3h: False (p=0.03)
[prediction-4] [INFO] [1793034646.181577111] [prediction]: 2026-04-18 19:00:00: wind now 3.0 -> next hour 2.6 mph, rain within 3h: False (p=0.07)
[prediction-4] [INFO] [1793034656.172665712] [prediction]: 2026-04-18 20:00:00: wind now 1.6 -> next hour 1.4 mph, rain within 3h: False (p=0.13)
[mission_manager-5] [INFO] [1793034666.052701265] [mission_manager]: state NORMAL -> PAUSE (predicted wind 3.4 mph, rain predicted: True)
[prediction-4] [INFO] [1793034666.052881369] [prediction]: 2026-04-18 21:00:00: wind now 3.6 -> next hour 3.4 mph, rain within 3h: True (p=0.66)
[prediction-4] [INFO] [1793034676.077192295] [prediction]: 2026-04-18 22:00:00: wind now 2.6 -> next hour 3.6 mph, rain within 3h: True (p=0.57)
[mission_manager-5] [INFO] [1793034686.000523022] [mission_manager]: state PAUSE -> CAUTION (predicted wind 4.9 mph, rain predicted: False)
[prediction-4] [INFO] [1793034686.001016262] [prediction]: 2026-04-18 23:00:00: wind now 4.9 -> next hour 4.9 mph, rain within 3h: False (p=0.32)
[prediction-4] [INFO] [1793034696.150786504] [prediction]: 2026-04-19 00:00:00: wind now 6.9 -> next hour 6.8 mph, rain within 3h: False (p=0.32)
[prediction-4] [INFO] [1793034706.093045844] [prediction]: 2026-04-19 01:00:00: wind now 7.5 -> next hour 7.6 mph, rain within 3h: True (p=0.72)
[mission_manager-5] [INFO] [1793034706.093625373] [mission_manager]: state CAUTION -> RETURN (predicted wind 7.6 mph, rain predicted: True)
[mission_manager-5] [WARN] [1793034706.145437314] [mission_manager]: RETURN state: heading back to the dock
[mission_manager-5] [INFO] [1793034706.182748690] [mission_manager]: goal 'wp4' canceled
[mission_manager-5] [INFO] [1793034706.343324849] [mission_manager]: sending goal: dock
[mission_manager-5] [INFO] [1793034715.982010742] [mission_manager]: state RETURN -> PAUSE (predicted wind 7.6 mph, rain predicted: False)
[prediction-4] [INFO] [1793034715.982024026] [prediction]: 2026-04-19 02:00:00: wind now 7.5 -> next hour 7.6 mph, rain within 3h: False (p=0.33)
[navigation-2] [INFO] [1793034717.491506625] [navigation]: reached 'dock'
"""

HOURS = ["2026-04-18 14:00:00", "2026-04-18 15:00:00", "2026-04-18 16:00:00", "2026-04-18 17:00:00", "2026-04-18 18:00:00",
         "2026-04-18 19:00:00", "2026-04-18 20:00:00", "2026-04-18 21:00:00", "2026-04-18 22:00:00", "2026-04-18 23:00:00",
         "2026-04-19 00:00:00", "2026-04-19 01:00:00", "2026-04-19 02:00:00"]
REAL_STATES = ["CAUTION", "CAUTION", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "PAUSE", "PAUSE", "CAUTION",
               "CAUTION", "RETURN", "PAUSE"]


def make_test(tid, name, spec, states):
    return {"id": tid, "name": name, "spec_expected": spec,
            "hours": [{"time": h, "state": s, "ideal_state": s} for h, s in zip(HOURS, states)]}


def test_parser_reads_real_lines():
    run = parse_log(REAL_LOG)
    assert len(run.predictions) == 13 and len(run.changes) == 6
    assert run.returns and [r["name"] for r in run.reached] == ["wp1", "wp2", "dock"]
    assert not run.failures


def test_states_by_hour_matches_the_real_demo():
    got = states_by_hour(parse_log(REAL_LOG))
    assert [got[h] for h in HOURS] == REAL_STATES


def test_change_logged_before_or_after_its_prediction_line():
    # in the real log the state change sometimes comes a few ms before the prediction and sometimes after
    swapped = REAL_LOG.replace("1793034595.998369538", "1793034596.003369538")
    assert [states_by_hour(parse_log(swapped))[h] for h in HOURS] == REAL_STATES


def test_changing_weather_counts_the_warmup_normal():
    t = make_test(5, "Changing weather", ["Multiple states"], REAL_STATES)
    j = judge(t, parse_log(REAL_LOG))
    assert j["spec_ok"] is False          # RETURN -> PAUSE steps back down, so this window is not a clean escalation
    t2 = make_test(5, "Changing weather", ["Multiple states"], REAL_STATES)
    t2["hours"] = t2["hours"][:9]         # first 9 hours: CAUTION, NORMAL, ..., PAUSE, PAUSE
    j2 = judge(t2, parse_log(REAL_LOG))
    assert j2["complete"] and j2["match_model_hours"] == 9


def test_single_state_test_and_navigation():
    t = make_test(1, "Typical weather", ["NORMAL"], REAL_STATES[2:7])
    t["hours"] = [h for h in t["hours"]]
    t["hours"] = [{"time": h, "state": "NORMAL", "ideal_state": "NORMAL"} for h in HOURS[2:7]]
    j = judge(t, parse_log(REAL_LOG))
    assert j["spec_ok"] and j["match_model_hours"] == 5
    assert j["waypoints_reached"] == 2 and j["nav_ok"]


def test_wrong_state_is_reported_not_hidden():
    t = make_test(2, "Elevated wind", ["CAUTION"], ["CAUTION"] * 2)
    t["hours"] = [{"time": h, "state": "CAUTION", "ideal_state": "CAUTION"} for h in HOURS[1:4]]   # 15:00 C, 16:00 N, 17:00 N
    j = judge(t, parse_log(REAL_LOG))
    assert not j["spec_ok"] and j["spec_text"].startswith("No (1 of 3")


def test_return_must_reach_the_dock_and_failures_count():
    log = REAL_LOG.replace("[navigation-2] [INFO] [1793034717.491506625] [navigation]: reached 'dock'\n", "")
    t = make_test(4, "High risk", ["PAUSE", "RETURN"], REAL_STATES)
    j = judge(t, parse_log(log))
    assert not j["nav_ok"] and "dock" in j["nav_text"]
    failed = REAL_LOG + "[mission_manager-5] [WARN] [1793034720.0] [mission_manager]: goal 'wp3' failed: blocked\n"
    assert not judge(t, parse_log(failed))["nav_ok"]


def test_incomplete_log_is_flagged():
    t = make_test(1, "Typical", ["NORMAL"], ["NORMAL"] * 13)
    j = judge(t, parse_log(REAL_LOG.split("2026-04-19 00:00:00")[0]))
    assert not j["complete"] and j["spec_text"] == "Incomplete"


def test_final_tests_yaml_is_real_test_data_only():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "final_tests.yaml")
    if not os.path.exists(path):
        pytest.skip("run scripts/final_tests.py first")
    cfg = yaml.safe_load(open(path))
    assert len(cfg["tests"]) == 5
    seen = set()
    for t in cfg["tests"]:
        assert t["start_time"] >= "2026-01-01"                      # held-out test year only
        assert t["warmup_hours"] == 3 and len(t["hours"]) == t["judged_hours"]
        hrs = {h["time"] for h in t["hours"]}
        assert not hrs & seen
        seen |= hrs
