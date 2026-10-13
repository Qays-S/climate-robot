"""Full pipeline: weather replay -> ML prediction -> mission manager -> navigation -> simulated robot.
weather_aware is off by default in Milestone 3; Milestone 4 turns it on with real thresholds.

  ros2 launch climate_robot full_system.launch.py
  ros2 launch climate_robot full_system.launch.py weather_aware:=true wind_p75:=6.0 wind_p90:=9.0
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    rviz_cfg = PathJoinSubstitution([FindPackageShare("climate_robot"), "rviz", "climate_robot.rviz"])
    data_dir = os.path.expanduser("~/ros2_ws")
    L = LaunchConfiguration
    return LaunchDescription([
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("laps", default_value="0"),
        DeclareLaunchArgument("weather_aware", default_value="false"),
        DeclareLaunchArgument("wind_p75", default_value="0.0"),
        DeclareLaunchArgument("wind_p90", default_value="0.0"),
        DeclareLaunchArgument("start_time", default_value="2026-01-01 00:00:00"),
        DeclareLaunchArgument("replay_period_s", default_value="5.0"),
        DeclareLaunchArgument("data_dir", default_value=data_dir),
        Node(package="climate_robot", executable="robot_sim", name="robot_sim", output="screen"),
        Node(package="climate_robot", executable="navigation", name="navigation", output="screen"),
        Node(package="climate_robot", executable="weather", name="weather", output="screen",
             parameters=[{"csv_path": ParameterValue(PathJoinSubstitution([L("data_dir"), "weatherstem_cleaned_hourly.csv"]), value_type=str),
                          "start_time": ParameterValue(L("start_time"), value_type=str),
                          "replay_period_s": ParameterValue(L("replay_period_s"), value_type=float)}]),
        Node(package="climate_robot", executable="prediction", name="prediction", output="screen",
             parameters=[{"model_dir": ParameterValue(L("data_dir"), value_type=str)}]),
        Node(package="climate_robot", executable="mission_manager", name="mission_manager", output="screen",
             parameters=[{"laps": ParameterValue(L("laps"), value_type=int),
                          "weather_aware": ParameterValue(L("weather_aware"), value_type=bool),
                          "wind_p75": ParameterValue(L("wind_p75"), value_type=float),
                          "wind_p90": ParameterValue(L("wind_p90"), value_type=float)}]),
        Node(package="rviz2", executable="rviz2", name="rviz2", arguments=["-d", rviz_cfg],
             condition=IfCondition(L("rviz"))),
    ])
