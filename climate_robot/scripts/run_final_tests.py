"""Milestone 5: run the five real-weather tests one after another and save a log for each.

  python3 scripts/run_final_tests.py --rviz --confirm      # for the recorded demo: RViz on, wait for Enter before each test
  python3 scripts/run_final_tests.py                       # no RViz, runs all five (about 10 minutes)
  python3 scripts/run_final_tests.py --tests 2 4           # only some tests
  python3 scripts/run_final_tests.py --dry-run             # print the commands and how long each takes

Needs the workspace built and sourced (source ~/ros2_ws/install/setup.bash) and the CSV + models in ~/ros2_ws.
Each test starts the full weather-aware system at its own real start_time (config/final_tests.yaml), lets it run for
the warm-up plus the judged hours, then stops it cleanly (Ctrl+C to the launch). Logs go to docs/tests/test_N.log;
then run scripts/evaluate_tests.py.
"""
import argparse
import os
import shlex
import signal
import subprocess
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTUP_S = 8          # nodes + RViz coming up
TAIL_S = 5             # let the last judged hour finish


def duration_s(test, period):
    return STARTUP_S + (test["warmup_hours"] + test["judged_hours"]) * period + TAIL_S


def stop(proc):
    for sig, wait in ((signal.SIGINT, 25), (signal.SIGTERM, 10), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", type=int, nargs="*", help="test ids to run (default: all)")
    ap.add_argument("--rviz", action="store_true", help="open RViz (for the demo video)")
    ap.add_argument("--confirm", action="store_true", help="wait for Enter before each test (start your screen recorder)")
    ap.add_argument("--period", type=float, default=None, help="seconds per data hour (default from final_tests.yaml: 10)")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "docs", "tests"))
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "final_tests.yaml"))
    ap.add_argument("--launch-cmd", default="ros2 launch climate_robot weather_demo.launch.py")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    period = args.period or cfg["replay_period_s"]
    tests = [t for t in cfg["tests"] if not args.tests or t["id"] in args.tests]
    os.makedirs(args.out_dir, exist_ok=True)
    total = sum(duration_s(t, period) + 8 for t in tests)
    print(f"{len(tests)} test(s), about {total/60:.1f} minutes in total, {period:g} s per data hour\n")

    env = dict(os.environ, RCUTILS_COLORIZED_OUTPUT="0", PYTHONUNBUFFERED="1")
    for t in tests:
        cmd = shlex.split(args.launch_cmd) + [f"rviz:={'true' if args.rviz else 'false'}",
                                              f"replay_period_s:={period}", f"start_time:={t['start_time']}"]
        secs = duration_s(t, period)
        log = os.path.join(args.out_dir, f"test_{t['id']}.log")
        print(f"Test {t['id']} {t['name']}: start_time {t['start_time']}, {secs:.0f} s -> {log}")
        print("  " + " ".join(shlex.quote(c) for c in cmd))
        if args.dry_run:
            continue
        if args.confirm:
            input("  Start your screen recorder, then press Enter to begin... ")
        with open(log, "w") as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            t0 = time.time()
            while time.time() - t0 < secs and proc.poll() is None:
                time.sleep(0.5)
            if proc.poll() is not None:
                print(f"  launch ended early (exit code {proc.returncode}); see {log}")
            stop(proc)
        print("  stopped; saved log")
        if args.confirm:
            input("  Stop your screen recorder, then press Enter for the next test... ")
        time.sleep(3)       # let ports and nodes clear before the next launch
    if not args.dry_run:
        print("\nDone. Next: python3 scripts/evaluate_tests.py")


if __name__ == "__main__":
    sys.exit(main())
