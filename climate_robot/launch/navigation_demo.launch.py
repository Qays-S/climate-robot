"""Milestone 3 demo: simulated robot patrols the waypoints and returns to the dock.
No weather nodes needed.

  ros2 launch climate_robot navigation_demo.launch.py
  ros2 launch climate_robot navigation_demo.launch.py laps:=2 rviz:=false
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    rviz_cfg = PathJoinSubstitution([FindPackageShare("climate_robot"), "rviz", "climate_robot.rviz"])
    return LaunchDescription([
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("laps", default_value="1", description="patrol laps, 0 = forever"),
        Node(package="climate_robot", executable="robot_sim", name="robot_sim", output="screen"),
        Node(package="climate_robot", executable="navigation", name="navigation", output="screen"),
        Node(package="climate_robot", executable="mission_manager", name="mission_manager", output="screen",
             parameters=[{"laps": ParameterValue(LaunchConfiguration("laps"), value_type=int),
                          "weather_aware": False}]),
        Node(package="rviz2", executable="rviz2", name="rviz2", arguments=["-d", rviz_cfg],
             condition=IfCondition(LaunchConfiguration("rviz"))),
    ])
