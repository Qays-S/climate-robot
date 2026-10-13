"""Tests for the ROS-free core (no ROS install needed): pytest test/"""
import math

import pytest
from conftest import WORLD_FILE

from climate_robot.controller import ControllerConfig, PathFollower
from climate_robot.kinematics import Unicycle
from climate_robot.planner import plan_path
from climate_robot.sim_runner import make_robot, run_navigation
from climate_robot.world import GridMap, load_world


@pytest.fixture(scope="module")
def world():
    return load_world(WORLD_FILE)


@pytest.fixture(scope="module")
def grid(world):
    return GridMap(world, world.inflation)


def test_world_contents(world):
    assert len(world.waypoints) >= 3
    assert len(world.obstacles) >= 1
    assert world.has_target("dock") and world.has_target("wp1")
    assert not world.has_target("nowhere")


def test_dock_and_waypoints_are_free(world, grid):
    for name in ["dock"] + [w.name for w in world.waypoints]:
        assert grid.is_free_xy(*world.target_xy(name)), name


def test_planned_paths_are_collision_free(world, grid):
    names = [w.name for w in world.waypoints]
    stops = ["dock"] + names + ["dock"]
    for a, b in zip(stops, stops[1:]):
        path = plan_path(grid, world.target_xy(a), world.target_xy(b))
        assert path is not None, f"{a}->{b}"
        for p, q in zip(path, path[1:]):
            assert grid.line_of_sight(p, q)


def test_no_path_into_obstacle(world, grid):
    ob = world.obstacles[0]
    if hasattr(ob, "x_min"):
        centre = ((ob.x_min + ob.x_max) / 2, (ob.y_min + ob.y_max) / 2)
    else:
        centre = (ob.x, ob.y)
    assert not grid.is_free_xy(*centre)


def test_full_patrol_lap_and_return(world, grid):
    robot = make_robot(world)
    stops = [w.name for w in world.waypoints] + ["dock"]
    for name in stops:
        res = run_navigation(world, grid, robot, world.target_xy(name))
        assert res["success"], (name, res["reason"])
        assert res["final_distance"] <= 0.15 + 1e-6
        assert res["min_clearance"] > 0.0, f"collision on the way to {name}"
    d = world.dock
    assert math.hypot(robot.x - d.x, robot.y - d.y) < 0.2


def test_speed_scale_zero_holds_robot(world, grid):
    robot = make_robot(world)
    res = run_navigation(world, grid, robot, world.target_xy("wp1"),
                         speed_scale_fn=lambda t: 0.0, max_time=5.0)
    assert not res["success"]
    assert math.hypot(robot.x - world.dock.x, robot.y - world.dock.y) < 1e-6


def test_caution_scale_is_slower_but_succeeds(world, grid):
    fast = run_navigation(world, grid, make_robot(world), world.target_xy("wp1"))
    slow = run_navigation(world, grid, make_robot(world), world.target_xy("wp1"),
                          speed_scale_fn=lambda t: 0.5)
    assert fast["success"] and slow["success"]
    assert slow["time"] > 1.6 * fast["time"]


def test_pause_then_resume_continues_goal(world, grid):
    # paused between t=5 and t=10 s, then resumes and still reaches the goal
    res = run_navigation(world, grid, make_robot(world), world.target_xy("wp1"),
                         speed_scale_fn=lambda t: 0.0 if 5.0 <= t < 10.0 else 1.0)
    assert res["success"]


def test_kinematics_limits():
    r = Unicycle(0, 0, 0, max_v=1.0, max_w=2.0, max_accel=1.5, max_alpha=4.0)
    r.step(100.0, 100.0, 0.1)
    assert r.v <= 0.15 + 1e-9 and r.w <= 0.4 + 1e-9
    for _ in range(200):
        r.step(100.0, 100.0, 0.1)
    assert r.v == pytest.approx(1.0) and r.w == pytest.approx(2.0)


def test_follower_stops_at_goal():
    f = PathFollower([(0, 0), (1, 0)], ControllerConfig())
    v, w, done = f.update(0.95, 0.0, 0.0)
    assert done and v == 0.0 and w == 0.0
