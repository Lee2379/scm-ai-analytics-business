# Modeling and Evaluation

## Forecast design

The forecast is intentionally transparent and deterministic for the synthetic portfolio scenario. It estimates SKU-store demand level and variability from recent sales, then applies calendar structure over a 28-day horizon. The objective is reproducible integration with inventory decisions—not a claim of state-of-the-art predictive accuracy.

### Required production backtests

Before production use, evaluate with rolling-origin splits and compare against:

- seasonal naive by weekday;
- moving-average and exponential-smoothing baselines;
- gradient-boosted models using promotion, weather, price, and calendar features;
- hierarchical reconciliation across SKU, store, city, and category.

Recommended metrics are WAPE, MAE, bias, service-weighted error, and interval coverage. Report them by demand velocity, intermittency, category, store, and forecast horizon.

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

## Interpretation discipline

- The sample is synthetic and the policy assignment is simulated.
- Statistical significance reflects internal simulation consistency, not production causality.
- Cost weights materially affect the headline savings result and require sensitivity analysis.
- Model error is not propagated through the current policy simulation.
- A production decision requires shadow-mode evaluation and a controlled operational pilot.
