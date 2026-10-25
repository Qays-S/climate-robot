"""Risk state table + feature/model checks (model checks need the data files)."""
import os
from datetime import timedelta

import pytest

from climate_robot import state_machine as sm
from climate_robot.features import BASE_COLS, HISTORY_NEEDED, build_feature_dict, to_row
from climate_robot.weather_data import load_observations

P75, P90 = 4.43, 7.22


@pytest.mark.parametrize("wind,rain,expected", [
    (3.0, False, sm.NORMAL),
    (4.42, False, sm.NORMAL),
    (4.43, False, sm.CAUTION),
    (7.1, False, sm.CAUTION),
    (7.22, False, sm.PAUSE),
    (2.0, True, sm.PAUSE),
    (7.0, True, sm.PAUSE),
    (7.22, True, sm.RETURN),
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


def test_thresholds_file_is_sane():
    import yaml
    from conftest import ROOT
    with open(os.path.join(ROOT, "config", "thresholds.yaml")) as f:
        t = yaml.safe_load(f)
    assert 0 < t["wind_p75"] < t["wind_p90"]
    assert t["wind_p75"] == pytest.approx(4.43) and t["wind_p90"] == pytest.approx(7.22)


@pytest.mark.parametrize("state,returning,enabled,expected", [
    (sm.NORMAL, False, True, 1.0),
    (sm.CAUTION, False, True, 0.5),
    (sm.PAUSE, False, True, 0.0),
    (sm.RETURN, False, True, 1.0),
    (sm.NORMAL, False, False, 0.0),      # patrol paused by the service
    (sm.PAUSE, True, True, 1.0),         # already heading home: finish the trip
    (sm.CAUTION, True, True, 1.0),
])
def test_effective_speed_scale(state, returning, enabled, expected):
    assert sm.effective_speed_scale(state, returning, enabled) == expected
