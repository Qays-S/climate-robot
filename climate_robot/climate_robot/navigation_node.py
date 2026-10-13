"""Navigation node: plans with A* and follows the path with pure pursuit.

Action server : /navigate_to  (climate_robot_interfaces/action/NavigateTo)
Subscribes    : /odom, /mission/speed_scale (std_msgs/Float32)
Publishes     : /cmd_vel (geometry_msgs/Twist), /planned_path (nav_msgs/Path)

The speed scale lets the mission manager slow the robot (CAUTION) or hold it in
place (PAUSE) without cancelling the current goal.
"""
import time

import rclpy
from climate_robot_interfaces.action import NavigateTo
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, Path
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Float32

from .controller import ControllerConfig, PathFollower
from .planner import plan_path
from .ros_common import default_world_file, latched_qos, quaternion_to_yaw
from .world import GridMap, load_world


class NavigationNode(Node):
    def __init__(self):
        super().__init__("navigation")
        self.declare_parameter("world_file", default_world_file())
        self.declare_parameter("max_speed", 0.8)
        self.declare_parameter("max_yaw_rate", 1.5)
        self.declare_parameter("lookahead", 0.5)
        self.declare_parameter("goal_tolerance", 0.15)
        self.declare_parameter("control_rate_hz", 20.0)
        self.declare_parameter("goal_timeout_s", 240.0)   # counted only while the robot is allowed to move

        self.world = load_world(self.get_parameter("world_file").value)
        self.grid = GridMap(self.world, self.world.inflation)
        self.cfg = ControllerConfig(
            max_speed=self.get_parameter("max_speed").value,
            max_yaw_rate=self.get_parameter("max_yaw_rate").value,
            lookahead=self.get_parameter("lookahead").value,
            goal_tolerance=self.get_parameter("goal_tolerance").value,
        )
        self.period = 1.0 / float(self.get_parameter("control_rate_hz").value)
        self.goal_timeout = float(self.get_parameter("goal_timeout_s").value)

        self.pose = None            # (x, y, yaw) from /odom
        self.speed_scale = 1.0
        self.busy = False

        group = ReentrantCallbackGroup()
        self.create_subscription(Odometry, "odom", self.on_odom, 10, callback_group=group)
        self.create_subscription(Float32, "mission/speed_scale", self.on_speed_scale, 10, callback_group=group)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.path_pub = self.create_publisher(Path, "planned_path", latched_qos())

        self.server = ActionServer(
            self, NavigateTo, "navigate_to",
            execute_callback=self.execute,
            goal_callback=self.on_goal,
            cancel_callback=self.on_cancel,
            callback_group=group,
        )
        self.get_logger().info("navigation ready: action server /navigate_to")

    # ----- subscriptions -----
    def on_odom(self, msg: Odometry):
        p = msg.pose.pose
        self.pose = (p.position.x, p.position.y, quaternion_to_yaw(p.orientation))

    def on_speed_scale(self, msg: Float32):
        self.speed_scale = float(msg.data)

    # ----- action server -----
    def on_goal(self, goal_request):
        if self.busy:
            self.get_logger().warn("rejecting goal: already navigating")
            return GoalResponse.REJECT
        if self.pose is None:
            self.get_logger().warn("rejecting goal: no odometry yet")
            return GoalResponse.REJECT
        if not self.world.has_target(goal_request.target):
            self.get_logger().warn(f"rejecting goal: unknown target '{goal_request.target}'")
            return GoalResponse.REJECT
        self.busy = True
        return GoalResponse.ACCEPT

    def on_cancel(self, goal_handle):
        return CancelResponse.ACCEPT

    def stop(self):
        try:
            self.cmd_pub.publish(Twist())
        except Exception:   # node is shutting down (Ctrl+C); nothing left to stop
            pass

    def publish_path(self, path):
        msg = Path()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        for x, y in path:
            ps = PoseStamped()
            ps.header = msg.header
            ps.pose.position.x, ps.pose.position.y = x, y
            ps.pose.orientation.w = 1.0
            msg.poses.append(ps)
        self.path_pub.publish(msg)

    def execute(self, goal_handle):
        target = goal_handle.request.target
        result = NavigateTo.Result()
        try:
            goal_xy = self.world.target_xy(target)
            x, y, _ = self.pose
            path = plan_path(self.grid, (x, y), goal_xy)
            if path is None:
                self.get_logger().error(f"no path to '{target}'")
                goal_handle.abort()
                result.success, result.message = False, f"no path to {target}"
                result.final_distance_to_goal = 0.0
                return result

            self.publish_path(path)
            self.get_logger().info(f"navigating to '{target}' ({len(path)} path points)")
            follower = PathFollower(path, self.cfg)
            moving_time = 0.0

            while rclpy.ok():
                if goal_handle.is_cancel_requested:
                    self.stop()
                    goal_handle.canceled()
                    result.success, result.message = False, "canceled"
                    result.final_distance_to_goal = float(follower.distance_to_goal)
                    return result

                x, y, yaw = self.pose
                v, w, done = follower.update(x, y, yaw, self.speed_scale)
                if done:
                    self.stop()
                    goal_handle.succeed()
                    result.success, result.message = True, f"reached {target}"
                    result.final_distance_to_goal = float(follower.distance_to_goal)
                    self.get_logger().info(f"reached '{target}'")
                    return result

                cmd = Twist()
                cmd.linear.x, cmd.angular.z = float(v), float(w)
                self.cmd_pub.publish(cmd)

                fb = NavigateTo.Feedback()
                fb.distance_remaining = float(follower.distance_to_goal)
                fb.x, fb.y = float(x), float(y)
                goal_handle.publish_feedback(fb)

                if self.speed_scale > 0.0:
                    moving_time += self.period
                if moving_time > self.goal_timeout:
                    self.stop()
                    goal_handle.abort()
                    result.success, result.message = False, f"timeout going to {target}"
                    result.final_distance_to_goal = float(follower.distance_to_goal)
                    return result
                time.sleep(self.period)

            self.stop()
            goal_handle.abort()
            result.success, result.message = False, "shutdown"
            return result
        finally:
            self.busy = False


def main(args=None):
    rclpy.init(args=args)
    node = NavigationNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
