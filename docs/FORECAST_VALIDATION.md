# Forecast Validation

## Decision question

Which forecasting approach provides the most reliable 28-day SKU-store demand signal for downstream replenishment decisions under a leakage-safe evaluation design?

## Evaluation design

The backtest uses the committed synthetic daily sales table as the source of truth.

- Evaluation grain: SKU × store × day
- Coverage: 60 SKU-store pairs
- Horizon: 28 days
- Origins: 2025-04-06, 2025-05-04, and 2025-06-01
- Test windows: three non-overlapping 28-day periods
- Observations: 5,040 actual daily outcomes per model
- Leakage control: training records end at each origin; future actual demand is excluded from feature construction

Calendar, promotion, and weather fields are treated as known planning inputs. Historical demand features are calculated with a one-day shift. Forecast-period rolling statistics are frozen at the origin rather than updated with future actuals.

## Compared models

| Model | Design |
|---|---|
| Seasonal naive (weekday) | Mean demand for the same weekday over the latest 56 training days |
| Moving average (28d) | Constant SKU-store forecast from the latest 28 training days |
| Exponentially weighted mean | Constant SKU-store level with alpha 0.20 over the latest 56 training days |
| Global gradient boosting | One cross-SKU/store model using encoded identifiers, calendar, promotion, weather, and origin-safe demand statistics |

## Aggregate results

| Rank | Model | WAPE | MAE | Bias |
|---:|---|---:|---:|---:|
| 1 | Global gradient boosting | **17.97%** | **4.97** | -1.81% |
| 2 | Moving average (28d) | 21.45% | 5.93 | -3.75% |
| 3 | Exponentially weighted mean | 21.69% | 6.00 | +1.04% |
| 4 | Seasonal naive (weekday) | 21.99% | 6.08 | -5.81% |

The gradient-boosted model reduces aggregate WAPE by 3.48 percentage points, or 16.2% relative, versus the strongest simple baseline. It ranks first at every origin. Its remaining negative bias indicates a modest tendency to under-forecast in aggregate.

![Forecast model comparison](../assets/analysis/forecast_model_comparison.png)

## Stability by origin

| Origin | Gradient boosting WAPE | Moving average WAPE | Seasonal naive WAPE |
|---|---:|---:|---:|
| 2025-04-06 | 20.54% | 23.45% | 23.77% |
| 2025-05-04 | 18.00% | 21.73% | 23.42% |
| 2025-06-01 | 15.51% | 19.29% | 18.85% |

The ranking is stable, but the absolute error level changes across origins. Production monitoring should therefore track both aggregate accuracy and time-window drift.

## Demand-velocity segments

![Forecast error by demand velocity](../assets/analysis/forecast_error_by_velocity.png)

The gradient-boosted model records the lowest WAPE in all three velocity segments. High-velocity pairs remain the most difficult segment at 20.89% WAPE and retain a -9.03% aggregate bias. This segment should receive additional feature work and service-weighted review before operational use.

## Metric definitions

```text
WAPE = sum(abs(prediction - actual)) / sum(actual)
MAE  = mean(abs(prediction - actual))
Bias = sum(prediction - actual) / sum(actual)
```

WAPE provides a volume-weighted network measure. MAE preserves the operational unit scale. Bias identifies systematic over- or under-forecasting that can affect safety-stock decisions.

## Limitations

- The dataset is synthetic and covers 180 calendar days.
- The gradient-boosted model is evaluated on three origins; a production decision requires a longer seasonal history.
- Hyperparameters are fixed and not tuned against the test windows.
- Weather and promotion inputs are treated as known future covariates.
- Prediction intervals and hierarchical reconciliation are not included.
- The result establishes internal comparative validity, not expected production performance.

## Reproduction

```bash
python -m src.forecast_backtesting
python -m src.analysis_visuals
```

The reviewed tables are stored in `data/forecast_backtest_*.csv`.
