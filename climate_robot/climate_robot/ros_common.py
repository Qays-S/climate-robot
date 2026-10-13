"""Small helpers shared by the ROS nodes."""
import math
import os

from ament_index_python.packages import get_package_share_directory
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def default_world_file() -> str:
    return os.path.join(get_package_share_directory("climate_robot"), "config", "world.yaml")


def latched_qos() -> QoSProfile:
    """Late-joining subscribers (e.g. RViz) still receive the last message."""
    return QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                      reliability=ReliabilityPolicy.RELIABLE)


def yaw_to_quaternion(yaw: float):
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def quaternion_to_yaw(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
