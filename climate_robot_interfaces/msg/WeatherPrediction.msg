# Output of the Milestone 2 models for one observation hour.
builtin_interfaces/Time stamp
string observation_time              # dataset hour these predictions were made from
float64 current_wind_speed_mph       # wind speed at observation_time (for reference)
float64 predicted_wind_speed_mph     # regression: wind speed one hour ahead
bool rain_predicted                  # classification: rain within the next three hours
float64 rain_probability             # classifier probability of the "rain" class
