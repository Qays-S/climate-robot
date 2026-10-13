"""Weather node: replays real WeatherSTEM observations from the cleaned dataset.

Publishes /weather/observation (climate_robot_interfaces/msg/WeatherObservation),
one dataset hour every `replay_period_s` seconds. No synthetic data is created;
hours the station did not report are skipped, never filled.

Jump to a different real period while running:
    ros2 param set /weather start_time "2026-03-14 06:00:00"
"""
import bisect
import os

import rclpy
from climate_robot_interfaces.msg import WeatherObservation
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node

from .features import BASE_COLS
from .ros_common import latched_qos
from .weather_data import TIME_FORMAT, load_observations, parse_time


class WeatherNode(Node):
    def __init__(self):
        super().__init__("weather")
        self.declare_parameter("csv_path", os.path.expanduser("~/ros2_ws/weatherstem_cleaned_hourly.csv"))
        self.declare_parameter("start_time", "2026-01-01 00:00:00")
        self.declare_parameter("end_time", "")
        self.declare_parameter("replay_period_s", 5.0)      # wall-clock seconds per dataset hour
        self.declare_parameter("loop", False)

        csv_path = self.get_parameter("csv_path").value
        end_text = self.get_parameter("end_time").value
        end = parse_time(end_text) if end_text else None
        self.rows, skipped = load_observations(csv_path, None, end)
        if not self.rows:
            raise RuntimeError(f"no usable observations in {csv_path}")
        self.times = [r["time"] for r in self.rows]
        self.loop = bool(self.get_parameter("loop").value)
        self.index = self.seek(parse_time(self.get_parameter("start_time").value))

        self.pub = self.create_publisher(WeatherObservation, "weather/observation", latched_qos())
        self.add_on_set_parameters_callback(self.on_params)
        period = float(self.get_parameter("replay_period_s").value)
        self.create_timer(period, self.publish_next)
        self.get_logger().info(
            f"loaded {len(self.rows)} real observations ({skipped} outage hours skipped); "
            f"replaying from {self.rows[self.index]['time']} every {period:.1f}s")

    def seek(self, when):
        return min(bisect.bisect_left(self.times, when), len(self.rows) - 1)

    def on_params(self, params):
        for p in params:
            if p.name == "start_time":
                try:
                    self.index = self.seek(parse_time(p.value))
                except ValueError:
                    return SetParametersResult(successful=False, reason=f"expected '{TIME_FORMAT}'")
                self.get_logger().info(f"seeking to {self.rows[self.index]['time']}")
        return SetParametersResult(successful=True)

    def publish_next(self):
        if self.index >= len(self.rows):
            if not self.loop:
                return
            self.index = 0
        row = self.rows[self.index]
        self.index += 1
        msg = WeatherObservation()
        msg.stamp = self.get_clock().now().to_msg()
        msg.observation_time = row["time"].strftime(TIME_FORMAT)
        for col in BASE_COLS:
            setattr(msg, col, float(row[col]))
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = WeatherNode()
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
