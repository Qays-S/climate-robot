"""Pure-pursuit path follower for the unicycle robot."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from .kinematics import clamp, wrap_angle


@dataclass
class ControllerConfig:
    max_speed: float = 0.8            # m/s at speed_scale = 1.0
    max_yaw_rate: float = 1.5         # rad/s
    lookahead: float = 0.5            # m
    goal_tolerance: float = 0.15      # m
    slow_radius: float = 0.8          # start slowing this far from the goal
    min_speed: float = 0.05           # m/s, keeps the robot creeping into the goal
    heading_gain: float = 2.0
    rotate_in_place_angle: float = math.radians(50.0)


class PathFollower:
    def __init__(self, path: List[Tuple[float, float]], cfg: ControllerConfig = None):
        self.cfg = cfg or ControllerConfig()
        self.path = path
        self.seg = 0
        self.distance_to_goal = float("inf")

    def _project(self, x, y, i):
        ax, ay = self.path[i]
        bx, by = self.path[i + 1]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return 0.0, 0.0, (ax, ay), (0.0, 0.0)
        ux, uy = dx / length, dy / length
        t = (x - ax) * ux + (y - ay) * uy
        return t, length, (ax, ay), (ux, uy)

    def _lookahead_point(self, x, y):
        # advance past segments the robot has finished
        while self.seg < len(self.path) - 2:
            t, length, _, _ = self._project(x, y, self.seg)
            if t >= length:
                self.seg += 1
            else:
                break
        t, length, (ax, ay), (ux, uy) = self._project(x, y, self.seg)
        t = clamp(t, 0.0, length)
        px, py = ax + ux * t, ay + uy * t
        remaining = self.cfg.lookahead
        i = self.seg
        while True:
            bx, by = self.path[i + 1]
            to_end = math.hypot(bx - px, by - py)
            if remaining <= to_end:
                if to_end < 1e-9:
                    return bx, by
                f = remaining / to_end
                return px + (bx - px) * f, py + (by - py) * f
            remaining -= to_end
            px, py = bx, by
            i += 1
            if i >= len(self.path) - 1:
                return self.path[-1]

    def update(self, x: float, y: float, yaw: float, speed_scale: float = 1.0):
        """Return (linear velocity, angular velocity, goal_reached)."""
        gx, gy = self.path[-1]
        self.distance_to_goal = math.hypot(gx - x, gy - y)
        if self.distance_to_goal <= self.cfg.goal_tolerance:
            return 0.0, 0.0, True
        if speed_scale <= 0.0:
            return 0.0, 0.0, False

        tx, ty = self._lookahead_point(x, y)
        err = wrap_angle(math.atan2(ty - y, tx - x) - yaw)
        w = clamp(self.cfg.heading_gain * err, -self.cfg.max_yaw_rate, self.cfg.max_yaw_rate)
        if abs(err) > self.cfg.rotate_in_place_angle:
            v = 0.0
        else:
            v = self.cfg.max_speed * max(0.0, math.cos(err)) ** 2
            v = min(v, self.cfg.max_speed * min(1.0, self.distance_to_goal / self.cfg.slow_radius))
            v = max(v, self.cfg.min_speed)
        return v * speed_scale, w * speed_scale, False
