# Delay model — latest evaluation

Data source: **REAL BTS**

BTS sample: completed, non-diverted US domestic reporting-carrier flights.

## Time split

- Train: 2025-01-01 to 2025-02-28; 40,000 flights; 19.7% delayed.
- Test: 2025-03-01 to 2025-03-31; 20,000 flights; 19.7% delayed.

## Held-out scores

Decision threshold: 0.5 (fixed before evaluation).

| Model | Accuracy | Precision | Recall | ROC-AUC |
|---|---:|---:|---:|---:|
| lightgbm | 0.8022 | 0.4359 | 0.0129 | 0.6187 |
| always_on_time | 0.8030 | 0.0000 | 0.0000 | 0.5000 |

Accuracy difference versus always-on-time: -0.075 percentage points. Recall at the fixed threshold: 1.29%. A score above baseline ROC-AUC does not by itself make the default classifier useful.

## Exploration

| Month | Flights | Delay rate |
|---|---:|---:|
| 2025-01 | 20,000 | 18.3% |
| 2025-02 | 20,000 | 21.0% |
| 2025-03 | 20,000 | 19.7% |

Airlines: 14; routes: 5221.

## Interpretation and limits

Always-on-time accuracy can be high simply because delays are uncommon. Compare recall and ROC-AUC as well; zero baseline recall means it never finds a delayed flight.

These are uncalibrated model scores. One held-out month does not establish performance in other seasons or years. The model excludes cancellations/diversions and has no live weather, airport congestion, or aircraft rotation inputs. It should not be generalized to international flights. Synthetic results validate the pipeline only.

Features: airline, origin, destination, scheduled_hour, day_of_week, month.

Source and field definitions: https://transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ

This is not legal advice. Delay predictions do not determine compensation rights.
