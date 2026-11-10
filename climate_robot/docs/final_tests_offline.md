# Milestone 5: offline results on the held-out year

Test hours: 5490 real hours, 2026-01-01 to 2026-08-31. Wind thresholds from the 31308 training hours: p75 = 4.43 mph, p90 = 7.22 mph.

## Machine learning accuracy (test year)

| Model | Measure | Value |
| --- | --- | --- |
| Wind, 1 h ahead (random forest) | MAE | 0.766 mph |
| | RMSE | 1.077 mph |
| | R2 | 0.867 |
| | Baseline "same as now" MAE / RMSE | 0.839 / 1.180 mph |
| Rain within 3 h (random forest) | Accuracy | 0.889 |
| | Precision | 0.615 |
| | Recall | 0.569 |
| | F1 | 0.591 |
| | AUC | 0.885 |
| | Share of hours followed by rain | 0.141 |

## Did the robot pick the right state? (whole test year)

The ideal state is what the same rules give if the next hour's wind and the next 3 hours of rain were known exactly. Over 5484 hours the robot's state matched it 76.9% of the time.

| Ideal state | Hours | Robot chose the same |
| --- | --- | --- |
| NORMAL | 3042 | 86.0% |
| CAUTION | 1119 | 66.6% |
| PAUSE | 1280 | 66.2% |
| RETURN | 43 | 20.9% |

- Hours where PAUSE or RETURN was ideal (1323): the robot kept going at NORMAL in 18.1%.
- Calm hours (3042): the robot stopped needlessly in 7.5%.

## The five test windows

Each window is replayed at 10 s per hour. The first 3 hours only fill the prediction node's history, then 6 hours are judged (12 for test 5).

| Test | Spec expects | Replay start_time | Judged hours | Ideal states (real weather) | Model states |
| --- | --- | --- | --- | --- | --- |
| 1 Typical weather | NORMAL | 2026-06-20 01:00:00 | 2026-06-20 04:00:00 + 5 h | N N N N N N | N N N N N N |
| 2 Elevated wind | CAUTION | 2026-03-22 07:00:00 | 2026-03-22 10:00:00 + 5 h | C C C C C C | C C C C C C |
| 3 Rain | CAUTION / PAUSE | 2026-08-01 18:00:00 | 2026-08-01 21:00:00 + 5 h | P P P P P P | P P P P P P |
| 4 High environmental risk | PAUSE / RETURN | 2026-03-12 11:00:00 | 2026-03-12 14:00:00 + 5 h | R R R R R C | P P P P P P |
| 5 Changing weather | Multiple states | 2026-01-01 19:00:00 | 2026-01-01 22:00:00 + 11 h | N C P P P P P P P P P P | C C C P P P P P P P P P |

(N = NORMAL, C = CAUTION, P = PAUSE, R = RETURN.)

## How each window was chosen

- **Test 1 Typical weather:** Hours where the real wind is below p75 both now and in the next hour, with no rain, closest to the test-year median wind, temperature and humidity.
- **Test 2 Elevated wind:** Hours where the real wind is steadily in the upper band, p75 to p90, both now and in the next hour, with no rain, closest to the middle of that band.
- **Test 3 Rain:** Hours with measured rain in at least 5 of 6 hours, wind below p90, the largest total rain rate.
- **Test 4 High environmental risk:** The 6 hours with the highest combined risk of wind speed, gusts and rain rate, each scored by the share of training hours it beats.
- **Test 5 Changing weather:** 12 hours in which the real next-hour wind rises from below p75, through p75 to p90, to p90 or more, with no rain and the fewest back-and-forth changes.

## Observed weather in each window

| Test | Hour | Wind now (mph) | Gust (mph) | Rain rate (in/h) | Real wind next hour | Predicted wind next hour | Rain probability | Ideal | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 06-20 04:00 | 4.15 | 9.47 | 0.0 | 3.75 | 4.21 | 0.187 | NORMAL | NORMAL |
| 1 | 06-20 05:00 | 3.75 | 8.13 | 0.0 | 1.93 | 3.69 | 0.189 | NORMAL | NORMAL |
| 1 | 06-20 06:00 | 1.93 | 6.17 | 0.0 | 2.13 | 2.29 | 0.205 | NORMAL | NORMAL |
| 1 | 06-20 07:00 | 2.13 | 5.7 | 0.0 | 2.33 | 3.12 | 0.219 | NORMAL | NORMAL |
| 1 | 06-20 08:00 | 2.33 | 6.37 | 0.0 | 3.47 | 3.24 | 0.23 | NORMAL | NORMAL |
| 1 | 06-20 09:00 | 3.47 | 8.68 | 0.0 | 4.2 | 3.92 | 0.241 | NORMAL | NORMAL |
| 2 | 03-22 10:00 | 6.08 | 14.48 | 0.0 | 5.85 | 6.7 | 0.323 | CAUTION | CAUTION |
| 2 | 03-22 11:00 | 5.85 | 14.3 | 0.0 | 6.35 | 6.06 | 0.282 | CAUTION | CAUTION |
| 2 | 03-22 12:00 | 6.35 | 15.4 | 0.0 | 6.48 | 6.01 | 0.196 | CAUTION | CAUTION |
| 2 | 03-22 13:00 | 6.48 | 14.17 | 0.0 | 5.95 | 5.62 | 0.098 | CAUTION | CAUTION |
| 2 | 03-22 14:00 | 5.95 | 16.05 | 0.0 | 5.97 | 5.7 | 0.066 | CAUTION | CAUTION |
| 2 | 03-22 15:00 | 5.97 | 14.0 | 0.0 | 5.9 | 5.52 | 0.038 | CAUTION | CAUTION |
| 3 | 08-01 21:00 | 2.52 | 9.05 | 0.005 | 2.2 | 2.18 | 0.812 | PAUSE | PAUSE |
| 3 | 08-01 22:00 | 2.2 | 6.95 | 0.2285 | 2.53 | 2.25 | 0.855 | PAUSE | PAUSE |
| 3 | 08-01 23:00 | 2.53 | 7.58 | 0.7535 | 2.63 | 2.77 | 0.847 | PAUSE | PAUSE |
| 3 | 08-02 00:00 | 2.63 | 9.72 | 0.5905 | 1.8 | 2.92 | 0.824 | PAUSE | PAUSE |
| 3 | 08-02 01:00 | 1.8 | 6.5 | 0.0 | 0.68 | 2.36 | 0.612 | PAUSE | PAUSE |
| 3 | 08-02 02:00 | 0.68 | 2.4 | 0.000167 | 1.0 | 1.04 | 0.618 | PAUSE | PAUSE |
| 4 | 03-12 14:00 | 12.17 | 26.97 | 0.0495 | 11.68 | 11.53 | 0.364 | RETURN | PAUSE |
| 4 | 03-12 15:00 | 11.68 | 28.98 | 0.016333 | 11.07 | 11.7 | 0.321 | RETURN | PAUSE |
| 4 | 03-12 16:00 | 11.07 | 29.57 | 0.012667 | 11.65 | 10.66 | 0.276 | RETURN | PAUSE |
| 4 | 03-12 17:00 | 11.65 | 30.5 | 0.002833 | 12.53 | 10.98 | 0.302 | RETURN | PAUSE |
| 4 | 03-12 18:00 | 12.53 | 31.87 | 0.004167 | 10.75 | 11.1 | 0.312 | RETURN | PAUSE |
| 4 | 03-12 19:00 | 10.75 | 25.55 | 0.0015 | 5.5 | 9.6 | 0.27 | CAUTION | PAUSE |
| 5 | 01-01 22:00 | 5.73 | 11.93 | 0.0 | 4.33 | 5.42 | 0.222 | NORMAL | CAUTION |
| 5 | 01-01 23:00 | 4.33 | 11.63 | 0.0 | 5.64 | 4.53 | 0.181 | CAUTION | CAUTION |
| 5 | 01-02 00:00 | 5.64 | 14.41 | 0.0 | 7.86 | 6.16 | 0.131 | PAUSE | CAUTION |
| 5 | 01-02 01:00 | 7.86 | 18.89 | 0.0 | 7.38 | 7.81 | 0.133 | PAUSE | PAUSE |
| 5 | 01-02 02:00 | 7.38 | 18.8 | 0.0 | 8.25 | 7.53 | 0.12 | PAUSE | PAUSE |
| 5 | 01-02 03:00 | 8.25 | 20.37 | 0.0 | 9.18 | 8.48 | 0.093 | PAUSE | PAUSE |
| 5 | 01-02 04:00 | 9.18 | 21.58 | 0.0 | 9.13 | 8.94 | 0.103 | PAUSE | PAUSE |
| 5 | 01-02 05:00 | 9.13 | 23.38 | 0.0 | 8.3 | 8.97 | 0.124 | PAUSE | PAUSE |
| 5 | 01-02 06:00 | 8.3 | 18.82 | 0.0 | 9.12 | 8.26 | 0.13 | PAUSE | PAUSE |
| 5 | 01-02 07:00 | 9.12 | 20.03 | 0.0 | 8.52 | 8.95 | 0.103 | PAUSE | PAUSE |
| 5 | 01-02 08:00 | 8.52 | 22.23 | 0.0 | 9.0 | 8.82 | 0.09 | PAUSE | PAUSE |
| 5 | 01-02 09:00 | 9.0 | 24.15 | 0.0 | 8.2 | 9.03 | 0.076 | PAUSE | PAUSE |
