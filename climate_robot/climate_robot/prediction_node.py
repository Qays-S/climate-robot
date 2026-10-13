"""Prediction node: runs the Milestone 2 models on the weather stream.

Subscribes : /weather/observation
Publishes  : /weather/prediction (climate_robot_interfaces/msg/WeatherPrediction)

Needs the current hour plus the three previous hours (the models use lag
features). If an hour is missing (station outage) the history restarts and
predictions resume after three more consecutive hours.
"""
import os
from collections import deque
from datetime import timedelta

import joblib
import rclpy
from climate_robot_interfaces.msg import WeatherObservation, WeatherPrediction
from rclpy.node import Node

from .features import BASE_COLS, HISTORY_NEEDED, build_feature_dict, to_row
from .ros_common import latched_qos
from .weather_data import parse_time


class PredictionNode(Node):
    def __init__(self):
        super().__init__("prediction")
        self.declare_parameter("model_dir", os.path.expanduser("~/ros2_ws"))
        model_dir = self.get_parameter("model_dir").value

        self.wind_model = joblib.load(os.path.join(model_dir, "best_wind_model.joblib"))
        self.rain_model = joblib.load(os.path.join(model_dir, "best_rain_model.joblib"))
        self.feature_names = list(self.wind_model.feature_names_in_)
        if self.feature_names != list(self.rain_model.feature_names_in_):
            raise RuntimeError("wind and rain models were trained on different feature columns")
        self.rain_idx = list(self.rain_model.classes_).index(1.0)

        self.history = deque(maxlen=HISTORY_NEEDED)
        self.pub = self.create_publisher(WeatherPrediction, "weather/prediction", latched_qos())
        self.create_subscription(WeatherObservation, "weather/observation", self.on_observation, 10)
        self.get_logger().info(f"models loaded from {model_dir} ({len(self.feature_names)} features)")

    def on_observation(self, msg):
        when = parse_time(msg.observation_time)
        obs = {c: float(getattr(msg, c)) for c in BASE_COLS}
        obs["time"] = when
        if self.history and (when - self.history[-1]["time"]) != timedelta(hours=1):
            self.get_logger().warn(f"gap before {msg.observation_time}: restarting history")
            self.history.clear()
        self.history.append(obs)
        if len(self.history) < HISTORY_NEEDED:
            self.get_logger().info(f"warming up ({len(self.history)}/{HISTORY_NEEDED} hours)")
            return

        row = to_row(build_feature_dict(list(self.history), when), self.feature_names)
        wind = float(self.wind_model.predict(row)[0])
        rain_prob = float(self.rain_model.predict_proba(row)[0][self.rain_idx])
        rain = bool(self.rain_model.predict(row)[0] == 1.0)

        out = WeatherPrediction()
        out.stamp = self.get_clock().now().to_msg()
        out.observation_time = msg.observation_time
        out.current_wind_speed_mph = obs["wind_speed_mph"]
        out.predicted_wind_speed_mph = wind
        out.rain_predicted = rain
        out.rain_probability = rain_prob
        self.pub.publish(out)
        self.get_logger().info(
            f"{msg.observation_time}: wind now {obs['wind_speed_mph']:.1f} -> next hour {wind:.1f} mph, "
            f"rain within 3h: {rain} (p={rain_prob:.2f})")


def main(args=None):
    rclpy.init(args=args)
    node = PredictionNode()
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
