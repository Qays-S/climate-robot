"""World description and planner grid for the patrol simulation.

Pure Python (numpy + yaml only). Nothing here imports ROS, so it can be unit
tested anywhere.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import yaml


@dataclass
class RectObstacle:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def distance(self, px, py):
        """Signed distance from point(s) to the rectangle surface (negative inside)."""
        dx = np.maximum(np.maximum(self.x_min - px, px - self.x_max), 0.0)
        dy = np.maximum(np.maximum(self.y_min - py, py - self.y_max), 0.0)
        outside = np.hypot(dx, dy)
        depth = np.minimum(np.minimum(px - self.x_min, self.x_max - px),
                           np.minimum(py - self.y_min, self.y_max - py))
        return np.where((dx == 0) & (dy == 0), -depth, outside)


@dataclass
class CircleObstacle:
    x: float
    y: float
    r: float

    def distance(self, px, py):
        return np.hypot(px - self.x, py - self.y) - self.r


@dataclass
class Waypoint:
    name: str
    x: float
    y: float


@dataclass
class Dock:
    x: float
    y: float
    yaw: float = 0.0


class World:
    def __init__(self, width, height, resolution, robot_radius, safety_margin,
                 dock: Dock, waypoints: List[Waypoint], obstacles):
        self.width = float(width)
        self.height = float(height)
        self.resolution = float(resolution)
        self.robot_radius = float(robot_radius)
        self.safety_margin = float(safety_margin)
        self.dock = dock
        self.waypoints = waypoints
        self.obstacles = obstacles

    @property
    def inflation(self) -> float:
        return self.robot_radius + self.safety_margin

    def target_xy(self, name: str) -> Tuple[float, float]:
        if name == "dock":
            return self.dock.x, self.dock.y
        for wp in self.waypoints:
            if wp.name == name:
                return wp.x, wp.y
        raise KeyError(f"unknown target '{name}'")

    def has_target(self, name: str) -> bool:
        return name == "dock" or any(wp.name == name for wp in self.waypoints)

    def obstacle_distance(self, px, py):
        """Distance from point(s) to the nearest obstacle surface (ignores walls)."""
        d = np.full(np.shape(px), np.inf)
        for obs in self.obstacles:
            d = np.minimum(d, obs.distance(px, py))
        return d

    def clearance(self, px, py):
        """Distance to the nearest obstacle surface or outer wall."""
        wall = np.minimum(np.minimum(px, self.width - px),
                          np.minimum(py, self.height - py))
        return np.minimum(self.obstacle_distance(px, py), wall)


def load_world(path: str) -> World:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)["world"]
    obstacles = []
    for o in cfg.get("obstacles", []):
        if o["type"] == "rect":
            obstacles.append(RectObstacle(o["x_min"], o["y_min"], o["x_max"], o["y_max"]))
        elif o["type"] == "circle":
            obstacles.append(CircleObstacle(o["x"], o["y"], o["r"]))
        else:
            raise ValueError(f"unknown obstacle type {o['type']}")
    dock = Dock(cfg["dock"]["x"], cfg["dock"]["y"], cfg["dock"].get("yaw", 0.0))
    waypoints = [Waypoint(w["name"], w["x"], w["y"]) for w in cfg["waypoints"]]
    return World(cfg["width"], cfg["height"], cfg["resolution"],
                 cfg["robot_radius"], cfg["safety_margin"], dock, waypoints, obstacles)


class GridMap:
    """Boolean occupancy grid. `blocked[iy, ix]` is True where the robot centre may not go."""

    def __init__(self, world: World, inflation: float):
        self.world = world
        self.res = world.resolution
        self.nx = int(round(world.width / self.res))
        self.ny = int(round(world.height / self.res))
        xs = (np.arange(self.nx) + 0.5) * self.res
        ys = (np.arange(self.ny) + 0.5) * self.res
        px, py = np.meshgrid(xs, ys)
        self.blocked = world.clearance(px, py) <= inflation

    def world_to_cell(self, x: float, y: float) -> Tuple[int, int]:
        ix = min(max(int(math.floor(x / self.res)), 0), self.nx - 1)
        iy = min(max(int(math.floor(y / self.res)), 0), self.ny - 1)
        return ix, iy

    def cell_to_world(self, ix: int, iy: int) -> Tuple[float, float]:
        return (ix + 0.5) * self.res, (iy + 0.5) * self.res

    def is_free_cell(self, ix: int, iy: int) -> bool:
        return 0 <= ix < self.nx and 0 <= iy < self.ny and not self.blocked[iy, ix]

    def is_free_xy(self, x: float, y: float) -> bool:
        if not (0.0 <= x < self.nx * self.res and 0.0 <= y < self.ny * self.res):
            return False
        ix, iy = self.world_to_cell(x, y)
        return not self.blocked[iy, ix]

    def nearest_free(self, ix: int, iy: int, max_radius: int = 15):
        """Closest free cell to (ix, iy), searching outward in square rings."""
        if self.is_free_cell(ix, iy):
            return ix, iy
        for r in range(1, max_radius + 1):
            best, best_d = None, None
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    cx, cy = ix + dx, iy + dy
                    if self.is_free_cell(cx, cy):
                        d = dx * dx + dy * dy
                        if best is None or d < best_d:
                            best, best_d = (cx, cy), d
            if best is not None:
                return best
        return None

    def line_of_sight(self, a: Tuple[float, float], b: Tuple[float, float]) -> bool:
        """True if every sample along the segment a->b lies in a free cell."""
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(int(math.ceil(dist / (self.res * 0.5))), 1)
        for i in range(steps + 1):
            t = i / steps
            if not self.is_free_xy(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])):
                return False
        return True
