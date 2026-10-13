"""Simulated differential-drive robot in the 2D patrol world (no Gazebo).

Subscribes : /cmd_vel (geometry_msgs/Twist)
Publishes  : /odom (nav_msgs/Odometry, ground truth), TF map -> base_link,
             /map (nav_msgs/OccupancyGrid, latched), /world_markers and
             /robot_marker (visualization_msgs/MarkerArray, Marker)
"""
import rclpy
from geometry_msgs.msg import Point, Quaternion, TransformStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from visualization_msgs.msg import Marker, MarkerArray

from .kinematics import Unicycle
from .ros_common import default_world_file, latched_qos, yaw_to_quaternion
from .world import GridMap, load_world


class RobotSim(Node):
    def __init__(self):
        super().__init__("robot_sim")
        self.declare_parameter("world_file", default_world_file())
        self.declare_parameter("update_rate_hz", 50.0)
        self.declare_parameter("cmd_timeout_s", 0.5)

        self.world = load_world(self.get_parameter("world_file").value)
        d = self.world.dock
        self.robot = Unicycle(d.x, d.y, d.yaw)
        self.cmd_v = 0.0
        self.cmd_w = 0.0
        self.last_cmd_time = self.get_clock().now()
        self.last_step_time = self.get_clock().now()
        self.cmd_timeout = float(self.get_parameter("cmd_timeout_s").value)
        self.tick = 0

        self.create_subscription(Twist, "cmd_vel", self.on_cmd, 10)
        self.odom_pub = self.create_publisher(Odometry, "odom", 10)
        self.map_pub = self.create_publisher(OccupancyGrid, "map", latched_qos())
        self.world_marker_pub = self.create_publisher(MarkerArray, "world_markers", latched_qos())
        self.robot_marker_pub = self.create_publisher(Marker, "robot_marker", 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        self.publish_map()
        self.publish_world_markers()

        rate = float(self.get_parameter("update_rate_hz").value)
        self.create_timer(1.0 / rate, self.step)
        self.get_logger().info(
            f"robot_sim ready: robot at dock ({d.x:.1f}, {d.y:.1f}), "
            f"{len(self.world.waypoints)} waypoints, {len(self.world.obstacles)} obstacles")

    # ----- input -----
    def on_cmd(self, msg: Twist):
        self.cmd_v = msg.linear.x
        self.cmd_w = msg.angular.z
        self.last_cmd_time = self.get_clock().now()

    # ----- simulation step -----
    def step(self):
        now = self.get_clock().now()
        dt = min((now - self.last_step_time).nanoseconds * 1e-9, 0.1)
        self.last_step_time = now
        if (now - self.last_cmd_time).nanoseconds * 1e-9 > self.cmd_timeout:
            self.cmd_v, self.cmd_w = 0.0, 0.0     # watchdog: stop if commands stop arriving
        self.robot.step(self.cmd_v, self.cmd_w, dt)
        self.publish_state(now)
        self.tick += 1
        if self.tick % 5 == 0:
            self.publish_robot_marker(now)

    def publish_state(self, now):
        qx, qy, qz, qw = yaw_to_quaternion(self.robot.yaw)
        stamp = now.to_msg()

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = "map"
        odom.child_frame_id = "base_link"
        odom.pose.pose.position.x = self.robot.x
        odom.pose.pose.position.y = self.robot.y
        odom.pose.pose.orientation = Quaternion(x=qx, y=qy, z=qz, w=qw)
        odom.twist.twist.linear.x = self.robot.v
        odom.twist.twist.angular.z = self.robot.w
        self.odom_pub.publish(odom)

        tf = TransformStamped()
        tf.header.stamp = stamp
        tf.header.frame_id = "map"
        tf.child_frame_id = "base_link"
        tf.transform.translation.x = self.robot.x
        tf.transform.translation.y = self.robot.y
        tf.transform.rotation = Quaternion(x=qx, y=qy, z=qz, w=qw)
        self.tf_broadcaster.sendTransform(tf)

    # ----- visualisation -----
    def publish_map(self):
        grid = GridMap(self.world, inflation=0.0)       # real obstacles, not inflated
        msg = OccupancyGrid()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.info.resolution = grid.res
        msg.info.width = grid.nx
        msg.info.height = grid.ny
        msg.info.origin.orientation.w = 1.0
        msg.data = [int(v) for v in (grid.blocked.astype(int) * 100).flatten()]
        self.map_pub.publish(msg)

    def _marker(self, mid, ns, mtype, x, y, sx, sy, sz, rgba, text=None):
        m = Marker()
        m.header.frame_id = "map"
        m.ns = ns
        m.id = mid
        m.type = mtype
        m.action = Marker.ADD
        m.pose.position = Point(x=x, y=y, z=sz / 2.0 if mtype != Marker.TEXT_VIEW_FACING else 0.6)
        m.pose.orientation.w = 1.0
        m.scale.x, m.scale.y, m.scale.z = sx, sy, sz
        m.color.r, m.color.g, m.color.b, m.color.a = rgba
        if text is not None:
            m.text = text
        return m

    def publish_world_markers(self):
        markers = MarkerArray()
        d = self.world.dock
        markers.markers.append(self._marker(0, "dock", Marker.CUBE, d.x, d.y, 0.8, 0.8, 0.05, (0.1, 0.8, 0.2, 0.9)))
        markers.markers.append(self._marker(1, "dock_label", Marker.TEXT_VIEW_FACING, d.x, d.y, 0.3, 0.3, 0.3,
                                            (1.0, 1.0, 1.0, 1.0), "DOCK"))
        for i, wp in enumerate(self.world.waypoints):
            markers.markers.append(self._marker(10 + i, "waypoint", Marker.CYLINDER, wp.x, wp.y, 0.4, 0.4, 0.05,
                                                (0.2, 0.4, 1.0, 0.9)))
            markers.markers.append(self._marker(30 + i, "waypoint_label", Marker.TEXT_VIEW_FACING, wp.x, wp.y,
                                                0.3, 0.3, 0.3, (1.0, 1.0, 1.0, 1.0), wp.name.upper()))
        # obstacles as plain markers (the OccupancyGrid display fails on some WSL graphics stacks)
        for i, ob in enumerate(self.world.obstacles):
            grey = (0.45, 0.45, 0.45, 1.0)
            if hasattr(ob, "x_min"):
                markers.markers.append(self._marker(
                    50 + i, "obstacle", Marker.CUBE, (ob.x_min + ob.x_max) / 2, (ob.y_min + ob.y_max) / 2,
                    ob.x_max - ob.x_min, ob.y_max - ob.y_min, 0.6, grey))
            else:
                markers.markers.append(self._marker(
                    50 + i, "obstacle", Marker.CYLINDER, ob.x, ob.y, 2 * ob.r, 2 * ob.r, 0.6, grey))
        self.world_marker_pub.publish(markers)

    def publish_robot_marker(self, now):
        qx, qy, qz, qw = yaw_to_quaternion(self.robot.yaw)
        m = Marker()
        m.header.frame_id = "map"
        m.header.stamp = now.to_msg()
        m.ns = "robot"
        m.id = 0
        m.type = Marker.ARROW
        m.action = Marker.ADD
        m.pose.position = Point(x=self.robot.x, y=self.robot.y, z=0.15)
        m.pose.orientation = Quaternion(x=qx, y=qy, z=qz, w=qw)
        m.scale.x = 0.7
        m.scale.y = 0.45
        m.scale.z = 0.3
        m.color.r, m.color.g, m.color.b, m.color.a = 1.0, 0.55, 0.0, 1.0
        self.robot_marker_pub.publish(m)


def main(args=None):
    rclpy.init(args=args)
    node = RobotSim()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
