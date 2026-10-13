"""A* path planner on the inflated occupancy grid, plus line-of-sight smoothing."""
from __future__ import annotations

import heapq
import math
from typing import List, Optional, Tuple

import numpy as np

from .world import GridMap

_SQRT2 = math.sqrt(2.0)
_MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, _SQRT2), (1, -1, _SQRT2), (-1, 1, _SQRT2), (-1, -1, _SQRT2)]


def _octile(dx: int, dy: int) -> float:
    dx, dy = abs(dx), abs(dy)
    return (dx + dy) + (_SQRT2 - 2.0) * min(dx, dy)


def _astar(grid: GridMap, start: Tuple[int, int], goal: Tuple[int, int]):
    ny, nx = grid.ny, grid.nx
    g = np.full((ny, nx), np.inf)
    parent = np.full((ny, nx, 2), -1, dtype=np.int32)
    closed = np.zeros((ny, nx), dtype=bool)
    g[start[1], start[0]] = 0.0
    heap = [(_octile(goal[0] - start[0], goal[1] - start[1]), 0.0, start)]
    while heap:
        _, gc, (cx, cy) = heapq.heappop(heap)
        if closed[cy, cx]:
            continue
        closed[cy, cx] = True
        if (cx, cy) == goal:
            cells = [(cx, cy)]
            while (cx, cy) != start:
                cx, cy = parent[cy, cx]
                cells.append((int(cx), int(cy)))
            return cells[::-1]
        for dx, dy, cost in _MOVES:
            nx_, ny_ = cx + dx, cy + dy
            if not grid.is_free_cell(nx_, ny_) or closed[ny_, nx_]:
                continue
            # no corner cutting: both orthogonal neighbours must be free on a diagonal move
            if dx != 0 and dy != 0 and not (grid.is_free_cell(cx + dx, cy) and grid.is_free_cell(cx, cy + dy)):
                continue
            ng = gc + cost
            if ng < g[ny_, nx_]:
                g[ny_, nx_] = ng
                parent[ny_, nx_] = (cx, cy)
                heapq.heappush(heap, (ng + _octile(goal[0] - nx_, goal[1] - ny_), ng, (nx_, ny_)))
    return None


def _smooth(grid: GridMap, pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Greedy string pulling: jump to the farthest point that is still in line of sight."""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not grid.line_of_sight(pts[i], pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return out


def plan_path(grid: GridMap, start_xy: Tuple[float, float], goal_xy: Tuple[float, float],
              smooth: bool = True) -> Optional[List[Tuple[float, float]]]:
    """Return a list of (x, y) points from start to goal, or None if no route exists."""
    s = grid.nearest_free(*grid.world_to_cell(*start_xy))
    g = grid.nearest_free(*grid.world_to_cell(*goal_xy))
    if s is None or g is None:
        return None
    cells = _astar(grid, s, g)
    if cells is None:
        return None
    pts = [grid.cell_to_world(ix, iy) for ix, iy in cells]
    if smooth:
        pts = _smooth(grid, pts)
    # begin at the true robot position and end exactly on the requested goal
    path = [tuple(start_xy)] + pts[1:-1] + [tuple(goal_xy)] if len(pts) > 1 else [tuple(start_xy), tuple(goal_xy)]
    cleaned = [path[0]]
    for p in path[1:]:
        if math.hypot(p[0] - cleaned[-1][0], p[1] - cleaned[-1][1]) > 1e-3:
            cleaned.append(p)
    if len(cleaned) == 1:
        cleaned.append(tuple(goal_xy))
    return cleaned


def path_length(path: List[Tuple[float, float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))
