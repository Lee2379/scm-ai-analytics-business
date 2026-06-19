# Portfolio Case Study

## The business problem

Retail inventory teams rarely suffer from a lack of dashboards. The harder problem is connecting demand signals, service-level policy, inventory position, and transfer constraints into a decision that can be reviewed and executed. This project treats the dashboard as the last mile of a decision system rather than the analytical product itself.

The operating question is:

> For each SKU-store pair, what should the planner order or transfer, why is that action justified, and how does the candidate policy compare with the current policy?

## Scope and ownership

This repository demonstrates end-to-end ownership across five layers:

1. **Data product design** — explicit synthetic source tables and reproducible analytical assets.
2. **Forecasting** — store-SKU demand projections with weekday seasonality and bounded recent trend.
3. **Inventory optimization** — service-level safety stock, reorder points, prioritization, and feasible store transfers.
4. **Decision intelligence** — paired offline policy simulation, segment diagnostics, and statistical tests.
5. **AI application delivery** — a multilingual, data-grounded SCM Copilot embedded in a deployed Streamlit workspace.

## Key design decisions

### Use transparent policy logic before model complexity

The forecast and replenishment calculations are deterministic and inspectable. This makes the system auditable, establishes a trustworthy baseline, and prevents a sophisticated model from hiding weak inventory assumptions. A production extension could replace the forecasting component without changing the downstream decision contracts.

### Separate prediction from policy evaluation

Forecast accuracy is not the same as operational value. The project therefore evaluates the replenishment policy on stockout exposure, service level, and a total-cost proxy. The paired simulation keeps SKU-store composition fixed, making the comparison more informative than two unrelated aggregate snapshots.

### Constrain the Copilot to governed analytical outputs

The Copilot routes common SCM intents to prepared tables and deterministic calculations. It does not receive unrestricted database or execution access. This design reduces hallucination risk, keeps answers traceable to the displayed metrics, and allows the public demo to run without an external model credential.

### Treat limitations as part of the product

The policy comparison is a synthetic offline simulation, not a randomized production experiment. The dashboard states this limitation directly. Estimated improvements should be interpreted as scenario evidence that motivates a controlled pilot, not as causal proof.

## Evidence and results

The current synthetic scenario monitors 60 SKU-store pairs and identifies 26 stockout-risk pairs and 3 overstock cases. The decision layer recommends 21,727 order units while maintaining 100% explanation coverage.

The constrained candidate policy produces the following simulated comparison:

| KPI | Baseline | Candidate | Difference |
|---|---:|---:|---:|
| Stockout rate | 71.7% | 70.0% | -1.7 pp |
| Service level | 92.9% | 94.9% | +2.0 pp |
| Total SCM cost proxy | JPY 11,351,887 | JPY 8,493,779 | -25.2% |

The stockout-rate change is not statistically significant in the current paired sample, while the simulated service and cost outcomes show stronger paired evidence. That distinction is intentionally preserved in the interpretation.

## What I would do next in production

1. Establish point-in-time feature generation and backtesting to eliminate leakage risk.
2. Benchmark seasonal-naive, exponential-smoothing, and gradient-boosting models by demand regime.
3. Add probabilistic forecasts and calibrate safety stock against empirical service outcomes.
4. Run sensitivity analysis across holding, shortage, transfer, and order-handling costs.
5. Introduce approval workflows, decision logs, overrides, and realized-outcome monitoring.
6. Pilot on a bounded category and geography before any broader rollout.

## Interview discussion prompts

- Why was a transparent deterministic forecast appropriate for this portfolio stage?
- How would intermittent-demand SKUs change the modeling choice?
- Which assumptions drive the 25.2% simulated cost reduction?
- How would you design a production pilot that measures causal operational lift?
- What controls are required before allowing an LLM to propose or execute inventory actions?

