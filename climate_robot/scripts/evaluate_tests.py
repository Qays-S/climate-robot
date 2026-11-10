"""Milestone 5: judge the five test runs from their logs and write the results table.

  python3 scripts/evaluate_tests.py                 # reads docs/tests/test_1.log .. test_5.log
  python3 scripts/evaluate_tests.py --logs ~/m5_logs

Writes docs/final_test_results.md and docs/final_test_results.json (the table the spec asks for, plus per-hour detail).
"""
import argparse
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from climate_robot.final_eval import judge, parse_log  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--logs", default=os.path.join(ROOT, "docs", "tests"))
ap.add_argument("--tests", default=os.path.join(ROOT, "config", "final_tests.yaml"))
ap.add_argument("--out-dir", default=os.path.join(ROOT, "docs"))
args = ap.parse_args()

cfg = yaml.safe_load(open(args.tests))
results = []
for t in cfg["tests"]:
    path = os.path.join(args.logs, f"test_{t['id']}.log")
    if not os.path.exists(path):
        results.append({"id": t["id"], "name": t["name"], "spec_expected": t["spec_expected"], "missing": True})
        continue
    results.append(judge(t, parse_log(open(path, errors="replace").read())))

L = ["# Milestone 5: final test results (robot system)", "",
     "Each test replays a real held-out 2026 window at 10 s per data hour. The first 3 hours only fill the prediction node's history.", "",
     "| Test | Expected state | Actual state | Correct behavior? | Navigation successful? |", "| --- | --- | --- | --- | --- |"]
for r in results:
    if r.get("missing"):
        L.append(f"| {r['name']} | {' / '.join(r['spec_expected'])} | not run | | |")
    else:
        L.append(f"| {r['name']} | {' / '.join(r['spec_expected'])} | {r['actual_text']} | {r['spec_text']} | {r['nav_text']} |")

L += ["", "## Did the integrated system do what the models said? (state per hour)", "",
      "The robot's state for each hour is compared with the state the same models and rules give offline (`final_tests.py`), "
      "and with the ideal state for the real weather.", "",
      "| Test | Robot = offline model | Robot = ideal for real weather | Waypoints reached | RETURNs | Docked after every RETURN | Goal failures |",
      "| --- | --- | --- | --- | --- | --- | --- |"]
for r in results:
    if r.get("missing"):
        continue
    dk = {None: "n/a", True: "yes", False: "NO"}[r["docked_after_every_return"]]
    L.append(f"| {r['name']} | {r['match_model_hours']} of {r['judged_hours']} h | {r['match_ideal_hours']} of {r['judged_hours']} h | "
             f"{r['waypoints_reached']} | {r['returns']} | {dk} | {len(r['failures'])} |")

L += ["", "## Hour by hour", ""]
for r in results:
    if r.get("missing"):
        continue
    L += [f"**Test {r['id']}: {r['name']}**", "", "| Hour | Ideal (real weather) | Offline model | Robot |", "| --- | --- | --- | --- |"]
    for h in r["hour_table"]:
        L.append(f"| {h['time'][5:16]} | {h['ideal']} | {h['model_offline']} | {h['robot'] or 'not logged'} |")
    L.append("")

os.makedirs(args.out_dir, exist_ok=True)
with open(os.path.join(args.out_dir, "final_test_results.md"), "w") as f:
    f.write("\n".join(L) + "\n")
with open(os.path.join(args.out_dir, "final_test_results.json"), "w") as f:
    json.dump(results, f, indent=2)
print("\n".join(L[:14]))
print("\nwrote", os.path.join(args.out_dir, "final_test_results.md"))
