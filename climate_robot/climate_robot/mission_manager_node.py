"""Mission manager: runs the patrol and (optionally) reacts to weather predictions.

Service       : /mission/set_patrol (std_srvs/SetBool)  true = start/resume, false = pause
Action client : /navigate_to
Subscribes    : /weather/prediction (used only when weather_aware is true)
Publishes     : /mission/state (std_msgs/String), /mission/speed_scale (std_msgs/Float32)

Patrol: dock -> wp1 -> wp2 -> ... -> (repeat) and back to the dock when `laps`
is reached. With weather_aware=true the weather-risk state machine
(NORMAL / CAUTION / PAUSE / RETURN) scales speed, holds the robot, or sends it home.
"""
import time

import rclpy
from action_msgs.msg import GoalStatus
from climate_robot_interfaces.action import NavigateTo
from climate_robot_interfaces.msg import WeatherPrediction
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Float32, String
from std_srvs.srv import SetBool

from . import state_machine as sm
from .ros_common import default_world_file, latched_qos
from .world import load_world

DOCKED, PATROL, RETURNING = "DOCKED", "PATROL", "RETURNING"


class MissionManager(Node):
    def __init__(self):
        super().__init__("mission_manager")
        self.declare_parameter("world_file", default_world_file())
        self.declare_parameter("weather_aware", False)
        self.declare_parameter("wind_p75", 0.0)      # filled in from the dataset in Milestone 4
        self.declare_parameter("wind_p90", 0.0)
        self.declare_parameter("laps", 0)            # 0 = patrol forever
        self.declare_parameter("dwell_s", 1.0)       # pause at each waypoint
        self.declare_parameter("start_active", True)

        world = load_world(self.get_parameter("world_file").value)
        self.waypoint_names = [w.name for w in world.waypoints]
        self.weather_aware = bool(self.get_parameter("weather_aware").value)
        self.wind_p75 = float(self.get_parameter("wind_p75").value)
        self.wind_p90 = float(self.get_parameter("wind_p90").value)
        self.laps = int(self.get_parameter("laps").value)
        self.dwell_s = float(self.get_parameter("dwell_s").value)
        self.patrol_enabled = bool(self.get_parameter("start_active").value)

        self.state = sm.NORMAL
        self.mode = DOCKED
        self.wp_index = 0
        self.laps_done = 0
        self.finished = False
        self.final_return = False
        self.failures = 0
        self.dwell_until = 0.0
        self.odom_ready = False   # navigation rejects goals until the first /odom arrives

        self.busy = False
        self.goal_handle = None
        self.cancel_requested = False
        self.current_target = None

        self.state_pub = self.create_publisher(String, "mission/state", latched_qos())
        self.scale_pub = self.create_publisher(Float32, "mission/speed_scale", 10)
        self.create_service(SetBool, "mission/set_patrol", self.on_set_patrol)
        self.create_subscription(WeatherPrediction, "weather/prediction", self.on_prediction, 10)
        self.create_subscription(Odometry, "odom", self.on_odom, 10)
        self.nav_client = ActionClient(self, NavigateTo, "navigate_to")

        self.publish_state()
        self.create_timer(0.2, self.tick)
        self.get_logger().info(
            f"mission_manager ready (weather_aware={self.weather_aware}, laps={self.laps or 'infinite'}, "
            f"patrol {'active' if self.patrol_enabled else 'paused'})")

    # ----- service -----
    def on_set_patrol(self, request, response):
        self.patrol_enabled = bool(request.data)
        response.success = True
        response.message = "patrol started/resumed" if self.patrol_enabled else "patrol paused"
        self.get_logger().info(response.message)
        return response

    def on_odom(self, msg):
        self.odom_ready = True

    # ----- weather -----
    def on_prediction(self, msg):
        if not self.weather_aware:
            return
        new_state = sm.decide_state(msg.predicted_wind_speed_mph, msg.rain_predicted,
                                    self.wind_p75, self.wind_p90)
        if new_state != self.state:
            self.get_logger().info(
                f"state {self.state} -> {new_state} "
                f"(predicted wind {msg.predicted_wind_speed_mph:.1f} mph, rain predicted: {msg.rain_predicted})")
            self.state = new_state
            self.publish_state()

    def publish_state(self):
        self.state_pub.publish(String(data=self.state))

    def publish_speed_scale(self):
        scale = 0.0 if not self.patrol_enabled else sm.SPEED_SCALE[self.state]
        self.scale_pub.publish(Float32(data=float(scale)))

    # ----- patrol logic -----
    def tick(self):
        self.publish_speed_scale()
        if self.finished:
            return

        if not self.odom_ready:
            self.get_logger().info("waiting for robot odometry...", throttle_duration_sec=5.0)
            return

        if self.mode == DOCKED:
            if self.patrol_enabled and self.state in (sm.NORMAL, sm.CAUTION) and not self.busy:
                self.mode = PATROL
                self.get_logger().info("leaving dock, patrol started")
            else:
                return

        if self.state == sm.RETURN and self.mode == PATROL:
            self.mode = RETURNING
            self.get_logger().warn("RETURN state: heading back to the dock")

        if self.mode == RETURNING:
            if self.busy:
                if self.current_target != "dock":
                    self.cancel_current()
                return
            self.send_goal("dock")
            return

        # PATROL
        if self.busy or not self.patrol_enabled or time.monotonic() < self.dwell_until:
            return
        self.send_goal(self.waypoint_names[self.wp_index])

    def send_goal(self, name):
        if not self.nav_client.server_is_ready():
            self.get_logger().info("waiting for /navigate_to action server...", throttle_duration_sec=5.0)
            return
        self.busy = True
        self.cancel_requested = False
        self.current_target = name
        goal = NavigateTo.Goal()
        goal.target = name
        self.get_logger().info(f"sending goal: {name}")
        self.nav_client.send_goal_async(goal).add_done_callback(self.on_goal_response)

    def on_goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            self.busy = False
            self.failures += 1
            self.dwell_until = time.monotonic() + 1.0
            self.get_logger().warn(f"goal '{self.current_target}' rejected")
            return
        self.goal_handle = handle
        if self.cancel_requested:
            handle.cancel_goal_async()
        handle.get_result_async().add_done_callback(self.on_result)

    def cancel_current(self):
        if self.cancel_requested:
            return
        self.cancel_requested = True
        if self.goal_handle is not None:
            self.goal_handle.cancel_goal_async()

    def on_result(self, future):
        wrapped = future.result()
        status, result = wrapped.status, wrapped.result
        name = self.current_target
        self.busy = False
        self.goal_handle = None
        self.cancel_requested = False

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.failures = 0
            if name == "dock":
                self.mode = DOCKED
                if self.final_return:
                    self.finished = True
                    self.get_logger().info("patrol complete, robot docked")
                else:
                    self.get_logger().info("docked, waiting for conditions to improve")
            else:
                self.advance_waypoint()
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info(f"goal '{name}' canceled")
        else:
            self.failures += 1
            self.get_logger().warn(f"goal '{name}' failed: {result.message}")
            self.dwell_until = time.monotonic() + 2.0
            if name != "dock" and self.failures >= 3:
                self.get_logger().error(f"skipping '{name}' after repeated failures")
                self.failures = 0
                self.advance_waypoint()

    def advance_waypoint(self):
        self.wp_index += 1
        self.dwell_until = time.monotonic() + self.dwell_s
        if self.wp_index >= len(self.waypoint_names):
            self.wp_index = 0
            self.laps_done += 1
            self.get_logger().info(f"lap {self.laps_done} complete")
            if self.laps > 0 and self.laps_done >= self.laps:
                self.final_return = True
                self.mode = RETURNING


def main(args=None):
    rclpy.init(args=args)
    node = MissionManager()
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
