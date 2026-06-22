# Modeling and Evaluation

## Forecast design

The operational forecast is intentionally transparent and deterministic for the synthetic evaluation scenario. It estimates SKU-store demand level and variability from recent sales, then applies calendar structure over a 28-day horizon. A separate backtesting pipeline evaluates stronger candidate models without changing the downstream inventory-policy contract.

### Rolling-origin backtest

The implemented validation uses three non-overlapping origins, a 28-day horizon, and 60 SKU-store pairs. It compares:

- seasonal naive by weekday;
- moving-average and exponential-smoothing baselines;
- a global gradient-boosted model using origin-safe demand statistics, promotion, weather, and calendar features.

The global gradient-boosted model ranks first with 17.97% WAPE, 4.97 MAE, and -1.81% bias. See [Forecast Validation](FORECAST_VALIDATION.md) for results by origin and demand velocity. Production validation still requires a longer seasonal history, prediction intervals, hierarchical reconciliation, and service-weighted error.

## Inventory policy

For each SKU-store pair:

```text
safety_stock = std_daily_demand × service_level_z × sqrt(lead_time_days)
rop = avg_daily_demand × lead_time_days + safety_stock
target_stock = forecast_28d + safety_stock
recommended_order_qty = max(target_stock - stock_on_hand, 0)
```

The implementation separates service-level protection during lead time from coverage of the forecast horizon. Priority is derived from shortage severity and the recommendation is accompanied by a human-readable rationale.

## Store-transfer logic

Transfers are generated only when the same SKU has both a shortage destination and a surplus source. Quantity is bounded by:

```text
min(source_surplus, destination_shortage)
```

Production extensions should add distance, transport cost, promised service, handling capacity, shelf-life, and source-store protection constraints.

## Offline policy simulation

### Experimental unit

The paired unit is one SKU-store pair (`n = 60`). Both policies are evaluated against the same 28-day demand forecast.

### Policies

- **Baseline:** planner-style constrained order quantity; no realized transfer.
- **Candidate:** constrained AI-assisted replenishment plus partial store-transfer realization.

### Cost proxy

Total SCM cost combines simulated lost-sales exposure, holding cost, order-handling cost, and transfer cost. It is a decision proxy, not an accounting forecast.

## Results

| Metric | Baseline | Candidate | Difference |
|---|---:|---:|---:|
| Stockout rate | 0.717 | 0.700 | -0.017 |
| Service level | 0.929 | 0.949 | +0.020 |
| Lost-sales units | 3,244.6 | 2,318.4 | -926.2 |
| Total SCM cost proxy | ¥11,351,886.88 | ¥8,493,779.46 | -¥2,858,107.42 |

## Statistical tests

| Outcome | Test | Effect | p-value | Interpretation |
|---|---|---|---:|---|
| Total SCM cost proxy | Paired t-test | Cohen's dz = 0.741 | 1.75e-07 | Strong simulated reduction |
| Lost-sales proxy | Paired t-test | Cohen's dz = 0.744 | 1.58e-07 | Strong simulated reduction |
| Service level | Paired t-test | Cohen's dz = 0.869 | 3.80e-09 | Strong simulated uplift |
| Stockout flag | Exact McNemar | Risk difference = 0.017 | 0.50 | Not statistically significant |

## Sensitivity analysis

The robustness analysis recalculates policy outcomes across 81 combinations of service target and lost-sales, holding, and order-handling cost multipliers. The candidate policy has a lower simulated cost in all evaluated scenarios, with reductions ranging from 23.16% to 26.43%. See [Inventory Policy Sensitivity Analysis](POLICY_SENSITIVITY.md) for scenario definitions and limitations.

## Interpretation discipline

- The sample is synthetic and the policy assignment is simulated.
- Statistical significance reflects internal simulation consistency, not production causality.
- The sensitivity range is bounded and does not cover every operating environment.
- Model error is not propagated through the current policy simulation.
- A production decision requires shadow-mode evaluation and a controlled operational pilot.
