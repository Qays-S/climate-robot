"""Run one full patrol (dock -> wp1..wp4 -> dock) without ROS and save a picture + GIF.

  python3 scripts/offline_demo.py [output_dir]
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Circle, Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from climate_robot.sim_runner import make_robot, run_navigation  # noqa: E402
from climate_robot.world import GridMap, load_world  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs")
os.makedirs(out, exist_ok=True)
world = load_world(os.path.join(ROOT, "config", "world.yaml"))
grid = GridMap(world, world.inflation)
robot = make_robot(world)

traj, legs = [(robot.x, robot.y)], []
for name in [w.name for w in world.waypoints] + ["dock"]:
    res = run_navigation(world, grid, robot, world.target_xy(name))
    legs.append((name, res["success"], res["time"], res["min_clearance"]))
    traj += res["trajectory"][1:]
for name, ok, t, c in legs:
    print(f"{name:>5}: {'reached' if ok else 'FAILED'}  {t:5.1f}s  min clearance {c:.2f} m")


def draw_world(ax):
    ax.set_xlim(0, world.width); ax.set_ylim(0, world.height); ax.set_aspect("equal")
    for ob in world.obstacles:
        if hasattr(ob, "x_min"):
            ax.add_patch(Rectangle((ob.x_min, ob.y_min), ob.x_max - ob.x_min, ob.y_max - ob.y_min, color="#555"))
        else:
            ax.add_patch(Circle((ob.x, ob.y), ob.r, color="#555"))
    d = world.dock
    ax.add_patch(Rectangle((d.x - 0.4, d.y - 0.4), 0.8, 0.8, color="#2ca02c"))
    ax.text(d.x, d.y + 0.65, "DOCK", ha="center", fontsize=9)
    for wp in world.waypoints:
        ax.add_patch(Circle((wp.x, wp.y), 0.2, color="#1f77b4"))
        ax.text(wp.x, wp.y + 0.45, wp.name.upper(), ha="center", fontsize=9)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")


fig, ax = plt.subplots(figsize=(8, 6.8))
draw_world(ax)
ax.plot(*zip(*traj), color="#ff7f0e", lw=1.8, label="robot trajectory")
ax.set_title("Patrol lap: dock -> waypoints -> dock (offline run of the same navigation code)")
ax.legend(loc="lower right")
fig.tight_layout(); fig.savefig(os.path.join(out, "patrol_trajectory.png"), dpi=130); plt.close(fig)

step = max(1, len(traj) // 150)
frames = traj[::step]
fig, ax = plt.subplots(figsize=(6, 5))
draw_world(ax)
line, = ax.plot([], [], color="#ff7f0e", lw=1.5)
dot, = ax.plot([], [], "o", color="#d62728", ms=9)
def upd(i):
    xs, ys = zip(*frames[:i + 1]); line.set_data(xs, ys); dot.set_data([xs[-1]], [ys[-1]]); return line, dot
FuncAnimation(fig, upd, frames=len(frames), interval=40).save(os.path.join(out, "patrol.gif"), writer=PillowWriter(fps=25))
print("saved", out)
