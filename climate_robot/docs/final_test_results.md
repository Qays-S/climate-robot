# Milestone 5: final test results (robot system)

Each test replays a real held-out 2026 window at 10 s per data hour. The first 3 hours only fill the prediction node's history.

| Test | Expected state | Actual state | Correct behavior? | Navigation successful? |
| --- | --- | --- | --- | --- |
| Typical weather | NORMAL | NORMAL (6 h) | Yes | Yes |
| Elevated wind | CAUTION | CAUTION (6 h) | Yes | Yes |
| Rain | CAUTION / PAUSE | PAUSE (6 h) | Yes | Yes |
| High environmental risk | PAUSE / RETURN | PAUSE (6 h) | Yes | Yes |
| Changing weather | Multiple states | NORMAL (1 h) -> CAUTION (3 h) -> PAUSE (9 h) | Yes | Yes |

## Did the integrated system do what the models said? (state per hour)

The robot's state for each hour is compared with the state the same models and rules give offline (`final_tests.py`), and with the ideal state for the real weather.

| Test | Robot = offline model | Robot = ideal for real weather | Waypoints reached | RETURNs | Docked after every RETURN | Goal failures |
| --- | --- | --- | --- | --- | --- | --- |
| Typical weather | 6 of 6 h | 6 of 6 h | 6 | 0 | n/a | 0 |
| Elevated wind | 6 of 6 h | 6 of 6 h | 4 | 0 | n/a | 0 |
| Rain | 6 of 6 h | 6 of 6 h | 2 | 0 | n/a | 0 |
| High environmental risk | 6 of 6 h | 0 of 6 h | 2 | 0 | n/a | 0 |
| Changing weather | 12 of 12 h | 10 of 12 h | 4 | 0 | n/a | 0 |

## Hour by hour

**Test 1: Typical weather**

| Hour | Ideal (real weather) | Offline model | Robot |
| --- | --- | --- | --- |
| 06-20 04:00 | NORMAL | NORMAL | NORMAL |
| 06-20 05:00 | NORMAL | NORMAL | NORMAL |
| 06-20 06:00 | NORMAL | NORMAL | NORMAL |
| 06-20 07:00 | NORMAL | NORMAL | NORMAL |
| 06-20 08:00 | NORMAL | NORMAL | NORMAL |
| 06-20 09:00 | NORMAL | NORMAL | NORMAL |

**Test 2: Elevated wind**

| Hour | Ideal (real weather) | Offline model | Robot |
| --- | --- | --- | --- |
| 03-22 10:00 | CAUTION | CAUTION | CAUTION |
| 03-22 11:00 | CAUTION | CAUTION | CAUTION |
| 03-22 12:00 | CAUTION | CAUTION | CAUTION |
| 03-22 13:00 | CAUTION | CAUTION | CAUTION |
| 03-22 14:00 | CAUTION | CAUTION | CAUTION |
| 03-22 15:00 | CAUTION | CAUTION | CAUTION |

**Test 3: Rain**

| Hour | Ideal (real weather) | Offline model | Robot |
| --- | --- | --- | --- |
| 08-01 21:00 | PAUSE | PAUSE | PAUSE |
| 08-01 22:00 | PAUSE | PAUSE | PAUSE |
| 08-01 23:00 | PAUSE | PAUSE | PAUSE |
| 08-02 00:00 | PAUSE | PAUSE | PAUSE |
| 08-02 01:00 | PAUSE | PAUSE | PAUSE |
| 08-02 02:00 | PAUSE | PAUSE | PAUSE |

**Test 4: High environmental risk**

| Hour | Ideal (real weather) | Offline model | Robot |
| --- | --- | --- | --- |
| 03-12 14:00 | RETURN | PAUSE | PAUSE |
| 03-12 15:00 | RETURN | PAUSE | PAUSE |
| 03-12 16:00 | RETURN | PAUSE | PAUSE |
| 03-12 17:00 | RETURN | PAUSE | PAUSE |
| 03-12 18:00 | RETURN | PAUSE | PAUSE |
| 03-12 19:00 | CAUTION | PAUSE | PAUSE |

**Test 5: Changing weather**

| Hour | Ideal (real weather) | Offline model | Robot |
| --- | --- | --- | --- |
| 01-01 22:00 | NORMAL | CAUTION | CAUTION |
| 01-01 23:00 | CAUTION | CAUTION | CAUTION |
| 01-02 00:00 | PAUSE | CAUTION | CAUTION |
| 01-02 01:00 | PAUSE | PAUSE | PAUSE |
| 01-02 02:00 | PAUSE | PAUSE | PAUSE |
| 01-02 03:00 | PAUSE | PAUSE | PAUSE |
| 01-02 04:00 | PAUSE | PAUSE | PAUSE |
| 01-02 05:00 | PAUSE | PAUSE | PAUSE |
| 01-02 06:00 | PAUSE | PAUSE | PAUSE |
| 01-02 07:00 | PAUSE | PAUSE | PAUSE |
| 01-02 08:00 | PAUSE | PAUSE | PAUSE |
| 01-02 09:00 | PAUSE | PAUSE | PAUSE |

