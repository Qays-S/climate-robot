"""Headless navigation runner: plan, drive the unicycle model, and record the result.

Used by the unit tests and the offline demo. The ROS navigation node uses the
same planner, controller and vehicle model.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from .controller import ControllerConfig, PathFollower
from .kinematics import Unicycle
from .planner import plan_path
from .world import GridMap, World


def make_robot(world: World) -> Unicycle:
    return Unicycle(world.dock.x, world.dock.y, world.dock.yaw)


def run_navigation(world: World, grid: GridMap, robot: Unicycle, target_xy,
                   cfg: Optional[ControllerConfig] = None, dt: float = 0.05,
                   max_time: float = 180.0,
                   speed_scale_fn: Optional[Callable[[float], float]] = None,
                   t0: float = 0.0):
    """Drive `robot` to `target_xy`. Returns a result dict (trajectory, clearance, time...)."""
    cfg = cfg or ControllerConfig()
    path = plan_path(grid, (robot.x, robot.y), target_xy)
    if path is None:
        return {"success": False, "reason": "no path", "path": None, "trajectory": [],
                "time": 0.0, "min_clearance": math.inf, "final_distance": math.inf}
    follower = PathFollower(path, cfg)
    traj = [(robot.x, robot.y)]
    min_clear = math.inf
    t = 0.0
    success = False
    while t < max_time:
        scale = speed_scale_fn(t0 + t) if speed_scale_fn else 1.0
        v, w, done = follower.update(robot.x, robot.y, robot.yaw, scale)
        if done:
            success = True
            break
        robot.step(v, w, dt)
        t += dt
        traj.append((robot.x, robot.y))
        # physical clearance: distance from robot edge to the nearest obstacle / wall
        clear = float(world.clearance(robot.x, robot.y)) - world.robot_radius
        min_clear = min(min_clear, clear)
    return {"success": success, "reason": "ok" if success else "timeout", "path": path,
            "trajectory": traj, "time": t, "min_clearance": min_clear,
            "final_distance": follower.distance_to_goal}
