"""Risk state table + feature/model checks (model checks need the data files)."""
import os
from datetime import timedelta

import pytest

from climate_robot import state_machine as sm
from climate_robot.features import BASE_COLS, HISTORY_NEEDED, build_feature_dict, to_row
from climate_robot.weather_data import load_observations

P75, P90 = 6.0, 9.0


@pytest.mark.parametrize("wind,rain,expected", [
    (3.0, False, sm.NORMAL),
    (5.99, False, sm.NORMAL),
    (6.0, False, sm.CAUTION),
    (8.9, False, sm.CAUTION),
    (9.0, False, sm.PAUSE),
    (2.0, True, sm.PAUSE),
    (7.0, True, sm.PAUSE),
    (9.0, True, sm.RETURN),
    (15.0, True, sm.RETURN),
])
def test_decide_state(wind, rain, expected):
    assert sm.decide_state(wind, rain, P75, P90) == expected


def test_speed_scales():
    assert sm.SPEED_SCALE[sm.NORMAL] == 1.0
    assert sm.SPEED_SCALE[sm.CAUTION] == 0.5
    assert sm.SPEED_SCALE[sm.PAUSE] == 0.0


def test_need_enough_history():
    with pytest.raises(ValueError):
        build_feature_dict([{c: 0.0 for c in BASE_COLS}] * 2, __import__("datetime").datetime(2026, 1, 1))


DATA_DIR = os.environ.get("CLIMATE_DATA_DIR", os.path.expanduser("~/ros2_ws"))
CSV = os.path.join(DATA_DIR, "weatherstem_cleaned_hourly.csv")
MODELS = [os.path.join(DATA_DIR, n) for n in ("best_wind_model.joblib", "best_rain_model.joblib")]
have_data = os.path.exists(CSV) and all(os.path.exists(m) for m in MODELS)


@pytest.mark.skipif(not have_data, reason="set CLIMATE_DATA_DIR to the folder with the csv and joblib files")
def test_models_accept_live_features():
    joblib = pytest.importorskip("joblib")
    wind, rain = (joblib.load(m) for m in MODELS)
    names = list(wind.feature_names_in_)
    assert names == list(rain.feature_names_in_)
    rows, _ = load_observations(CSV)
    # first run of consecutive hours
    run = [rows[0]]
    for r in rows[1:]:
        if r["time"] - run[-1]["time"] != timedelta(hours=1):
            run = [r]
            continue
        run.append(r)
        if len(run) >= HISTORY_NEEDED:
            break
    assert len(run) >= HISTORY_NEEDED
    row = to_row(build_feature_dict(run, run[-1]["time"]), names)
    assert row.shape == (1, len(names)) and not row.isna().any().any()
    assert wind.predict(row)[0] >= 0.0
    p = rain.predict_proba(row)[0]
    assert 0.0 <= p[list(rain.classes_).index(1.0)] <= 1.0
