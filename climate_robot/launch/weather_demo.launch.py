"""Milestone 4 demo: the robot reacts to a real storm from the dataset.

Replays a real storm from the held-out 2026 test data (2026-04-18/19: calm -> pause -> caution -> return -> pause
-> caution) at 10 s per dataset hour, with weather_aware on and wind thresholds computed from the training years
(p75 4.43, p90 7.22 mph).

  ros2 launch climate_robot weather_demo.launch.py
  ros2 launch climate_robot weather_demo.launch.py replay_period_s:=8.0

Needs weatherstem_cleaned_hourly.csv and the two .joblib models in ~/ros2_ws (or data_dir:=...).
Watch the state with:  ros2 topic echo /mission/state
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    full = PathJoinSubstitution([FindPackageShare("climate_robot"), "launch", "full_system.launch.py"])
    L = LaunchConfiguration
    return LaunchDescription([
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("replay_period_s", default_value="10.0"),
        DeclareLaunchArgument("data_dir", default_value=os.path.expanduser("~/ros2_ws")),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(full),
            launch_arguments={
                "rviz": L("rviz"),
                "laps": "0",                      # patrol until the weather says otherwise
                "weather_aware": "true",
                "wind_p75": "4.43",
                "wind_p90": "7.22",
                "start_time": "2026-04-18 11:00:00",
                "replay_period_s": L("replay_period_s"),
                "data_dir": L("data_dir"),
            }.items()),
    ])
