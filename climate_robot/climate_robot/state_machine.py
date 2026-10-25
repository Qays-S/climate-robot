"""Weather-risk decision rules for the robot (Milestone 4 policy, kept ROS-free).

NORMAL  : wind below the 75th percentile and no rain predicted -> full speed
CAUTION : wind between the 75th and 90th percentile, no rain   -> reduced speed
PAUSE   : wind at/above the 90th percentile, or rain predicted -> stop and wait
RETURN  : wind at/above the 90th percentile AND rain predicted -> go back to the dock
"""
from __future__ import annotations

NORMAL = "NORMAL"
CAUTION = "CAUTION"
PAUSE = "PAUSE"
RETURN = "RETURN"

# Fraction of full speed the navigation node is allowed to use in each state.
SPEED_SCALE = {NORMAL: 1.0, CAUTION: 0.5, PAUSE: 0.0, RETURN: 1.0}


def decide_state(predicted_wind_mph: float, rain_predicted: bool,
                 wind_p75: float, wind_p90: float) -> str:
    high_wind = predicted_wind_mph >= wind_p90
    if high_wind and rain_predicted:
        return RETURN
    if high_wind or rain_predicted:
        return PAUSE
    if predicted_wind_mph >= wind_p75:
        return CAUTION
    return NORMAL


def effective_speed_scale(state: str, returning: bool, patrol_enabled: bool = True) -> float:
    """Speed fraction sent to navigation.

    Once the robot has started returning to the dock it finishes the trip at full speed,
    even if the weather improves to PAUSE on the way (stopping in the open would defeat the point).
    """
    if not patrol_enabled and not returning:
        return 0.0
    if returning:
        return 1.0
    return SPEED_SCALE[state]
