"""Differential-drive (unicycle) vehicle model with velocity and acceleration limits."""
from __future__ import annotations

import math


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


class Unicycle:
    def __init__(self, x: float, y: float, yaw: float = 0.0,
                 max_v: float = 1.0, max_w: float = 2.0,
                 max_accel: float = 1.5, max_alpha: float = 4.0):
        self.x, self.y, self.yaw = x, y, yaw
        self.v = 0.0
        self.w = 0.0
        self.max_v, self.max_w = max_v, max_w
        self.max_accel, self.max_alpha = max_accel, max_alpha

    def step(self, cmd_v: float, cmd_w: float, dt: float) -> None:
        cmd_v = clamp(cmd_v, -self.max_v, self.max_v)
        cmd_w = clamp(cmd_w, -self.max_w, self.max_w)
        self.v += clamp(cmd_v - self.v, -self.max_accel * dt, self.max_accel * dt)
        self.w += clamp(cmd_w - self.w, -self.max_alpha * dt, self.max_alpha * dt)
        mid_yaw = self.yaw + 0.5 * self.w * dt
        self.x += self.v * math.cos(mid_yaw) * dt
        self.y += self.v * math.sin(mid_yaw) * dt
        self.yaw = wrap_angle(self.yaw + self.w * dt)

    @property
    def pose(self):
        return self.x, self.y, self.yaw
