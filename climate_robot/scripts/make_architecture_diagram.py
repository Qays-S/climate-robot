"""Draw the ROS 2 architecture diagram -> docs/architecture.png"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "architecture.png")
fig, ax = plt.subplots(figsize=(13, 6.6))
ax.set_xlim(0, 13); ax.set_ylim(0, 6.6); ax.axis("off")

def box(x, y, w, h, title, sub, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                                fc=color, ec="#333", lw=1.4))
    ax.text(x + w / 2, y + h - 0.25, title, ha="center", va="center", fontsize=11, fontweight="bold")
    ax.text(x + w / 2, y + h / 2 - 0.2, sub, ha="center", va="center", fontsize=8.5)

def arrow(p, q, label, dy=0.15, dx=0.0, style="-|>", ls="-", ha="center"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=14, lw=1.5, color="#222", linestyle=ls))
    ax.text((p[0] + q[0]) / 2 + dx, (p[1] + q[1]) / 2 + dy, label, ha=ha, fontsize=8, color="#7a1f1f",
            bbox=dict(fc="white", ec="none", pad=1))

box(0.2, 4.3, 2.5, 1.6, "Weather Node", "weather\nreplays real WeatherSTEM\nhourly data", "#cfe8ff")
box(3.6, 4.3, 2.5, 1.6, "Prediction Node", "prediction\nM2 models: wind (1 h),\nrain (3 h)", "#cfe8ff")
box(7.0, 4.3, 2.7, 1.6, "Mission Manager", "mission_manager\npatrol logic +\nweather-risk states (M4)", "#ffe3b3")
box(7.0, 1.2, 2.7, 1.6, "Navigation Node", "navigation\nA* planner +\npure-pursuit controller", "#d4f2d0")
box(10.4, 1.2, 2.4, 1.6, "Simulated Robot", "robot_sim\nunicycle model, map,\nTF, markers", "#d4f2d0")
box(10.4, 4.3, 2.4, 1.6, "RViz2", "map, dock, waypoints,\nrobot, planned path", "#eeeeee")
box(0.2, 1.2, 2.9, 1.6, "Data (Milestones 1-2)", "weatherstem_cleaned_hourly.csv\nbest_wind_model.joblib\nbest_rain_model.joblib", "#f4f4f4")

def label(x, y, text, ha="left", color="#7a1f1f"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=8, color=color, bbox=dict(fc="white", ec="none", pad=1))

arrow((2.7, 5.1), (3.6, 5.1), "", dy=0)
label(3.15, 4.7, "TOPIC\n/weather/\nobservation", ha="center")
arrow((6.1, 5.1), (7.0, 5.1), "", dy=0)
label(6.55, 4.7, "TOPIC\n/weather/\nprediction", ha="center")
# mission manager -> navigation
arrow((7.3, 4.3), (7.3, 2.8), "", dy=0)
label(7.2, 3.3, "ACTION /navigate_to\n(goal: dock | wp1..wp4)", ha="right")
arrow((8.6, 4.3), (8.6, 2.8), "", dy=0, ls="--")
label(8.7, 3.8, "TOPIC /mission/speed_scale")
# navigation <-> robot_sim
arrow((9.7, 2.3), (10.4, 2.3), "", dy=0)
label(10.05, 2.55, "/cmd_vel", ha="center")
arrow((10.4, 1.7), (9.7, 1.7), "", dy=0, ls="--")
label(10.05, 1.45, "/odom", ha="center")
# to RViz
arrow((11.6, 2.8), (11.6, 4.3), "", dy=0)
label(11.7, 3.55, "/map\n/robot_marker\n/world_markers\nTF")
arrow((9.4, 2.8), (10.6, 4.3), "", dy=0, ls=":")
label(10.05, 3.3, "/planned_path")
# data files
arrow((1.5, 2.8), (1.5, 4.3), "", dy=0, ls="--")
label(0.4, 3.55, "files read at startup")
# service
box(3.6, 3.3, 1.9, 0.9, "SERVICE", "/mission/set_patrol", "#fff6d6")
arrow((5.5, 3.75), (7.0, 4.5), "", dy=0)
label(5.6, 4.0, "start / pause", ha="left")
ax.text(6.5, 6.35, "Climate-Aware Autonomous Robot: ROS 2 architecture (Milestone 3)", ha="center", fontsize=14, fontweight="bold")
fig.savefig(OUT, dpi=140, bbox_inches="tight")
print(OUT)
