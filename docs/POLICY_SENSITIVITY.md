# Inventory Policy Sensitivity Analysis

## Decision question

Does the simulated cost advantage of the constrained AI-assisted policy persist when service targets and major SCM cost assumptions change?

## Scenario design

The analysis evaluates 81 combinations:

| Parameter | Values |
|---|---|
| Service-level target | 90%, 95%, 97% |
| Lost-sales cost multiplier | 0.75, 1.00, 1.25 |
| Holding-cost multiplier | 0.75, 1.00, 1.25 |
| Order-handling cost multiplier | 0.75, 1.00, 1.25 |

Each scenario recalculates safety stock and reorder points from its service target. Store-transfer candidates are rebuilt from the resulting shortage and surplus states. The baseline and candidate policies are then evaluated against the same 28-day demand scenario.

## Central assumptions

At multiplier 1.00 for all cost components:

| Service target | Baseline cost | Candidate cost | Cost reduction | Service lift | Stockout-rate change |
|---:|---:|---:|---:|---:|---:|
| 90% | ¥11,530,787 | ¥8,685,412 | 24.68% | +2.00 pp | -1.67 pp |
| 95% | ¥11,385,087 | ¥8,534,879 | 25.03% | +2.00 pp | -1.67 pp |
| 97% | ¥11,285,887 | ¥8,420,575 | 25.39% | +2.01 pp | -1.67 pp |

## Robustness result

The candidate policy has a lower simulated total cost in all 81 scenarios. Across the complete grid, cost reduction ranges from **23.16% to 26.43%**. Median reduction increases from 24.68% at the 90% service target to 25.39% at the 97% target.

![Policy sensitivity heatmap](../assets/analysis/policy_sensitivity_heatmap.png)

The central 95% service slice remains positive across all lost-sales and holding-cost combinations when order cost is held at its base assumption. Higher lost-sales cost increases the value of additional demand coverage; higher holding cost reduces that advantage.

## Interpretation

The result indicates internal robustness to moderate cost-weight changes within this simulation. It does not establish causal business impact. Candidate-policy behavior and the simulated demand path are structurally favorable to additional coverage, and the evaluated multiplier range does not represent every operating environment.

## Limitations

- Cost functions are linear and exclude capacity, markdown, shelf-life, and distance-based transfer effects.
- Supplier constraints, minimum order quantities, and case packs are not modeled.
- Transfer realization is fixed at 25% after candidates are regenerated.
- Demand uncertainty is represented by one synthetic forecast scenario rather than a probability distribution.
- Cost multipliers vary independently even though real operational costs may be correlated.
- A production recommendation requires finance-approved unit economics and a controlled pilot.

## Reproduction

```bash
python -m src.policy_sensitivity_analysis
python -m src.analysis_visuals
```

The reviewed tables are stored in `data/policy_sensitivity_*.csv`.

