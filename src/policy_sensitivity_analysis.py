from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from src.policy_evaluation_simulation import (
    BASELINE_LABEL,
    CANDIDATE_LABEL,
    CONTROL_FORECAST_GAP_COVERAGE,
    HOLDING_COST_RATE_28D,
    ORDER_HANDLING_COST_PER_UNIT,
    TREATMENT_DEMAND_CAP,
    TREATMENT_REMAINING_GAP_COVERAGE,
    TREATMENT_TRANSFER_REALIZATION,
    TRANSFER_COST_PER_UNIT,
    _transfer_adjustments,
    load_inputs,
)
from src.scm_engine import make_transfer_recommendations, z_value


SERVICE_LEVELS = (0.90, 0.95, 0.97)
COST_MULTIPLIERS = (0.75, 1.00, 1.25)


def _evaluate(
    frame: pd.DataFrame,
    policy_name: str,
    order_column: str,
    transfer_enabled: bool,
    lost_sales_cost_multiplier: float,
    holding_cost_multiplier: float,
    order_cost_multiplier: float,
) -> dict[str, float | str]:
    result = frame.copy()
    if not transfer_enabled:
        result["inbound_transfer_qty"] = 0.0
        result["outbound_transfer_qty"] = 0.0
    result["order_qty"] = result[order_column].clip(lower=0)
    result["available_units"] = (
        result["stock_on_hand"]
        + result["order_qty"]
        + result["inbound_transfer_qty"].fillna(0)
        - result["outbound_transfer_qty"].fillna(0)
    ).clip(lower=0)
    result["fulfilled_units"] = result[["available_units", "forecast_28d"]].min(axis=1)
    result["lost_sales_units"] = (result["forecast_28d"] - result["fulfilled_units"]).clip(lower=0)
    result["ending_inventory_units"] = (result["available_units"] - result["forecast_28d"]).clip(lower=0)
    result["service_achieved"] = result["fulfilled_units"] / result["forecast_28d"].replace(0, np.nan)
    result["stockout_flag"] = result["lost_sales_units"] > 0
    result["lost_sales_proxy_jpy"] = (
        result["lost_sales_units"] * result["unit_price"] * lost_sales_cost_multiplier
    )
    result["holding_cost_jpy"] = (
        result["ending_inventory_units"]
        * result["unit_price"]
        * HOLDING_COST_RATE_28D
        * holding_cost_multiplier
    )
    result["order_handling_cost_jpy"] = (
        result["order_qty"] * ORDER_HANDLING_COST_PER_UNIT * order_cost_multiplier
    )
    result["transfer_cost_jpy"] = (
        result["inbound_transfer_qty"].fillna(0) + result["outbound_transfer_qty"].fillna(0)
    ) * TRANSFER_COST_PER_UNIT
    result["total_scm_cost_jpy"] = result[
        [
            "lost_sales_proxy_jpy",
            "holding_cost_jpy",
            "order_handling_cost_jpy",
            "transfer_cost_jpy",
        ]
    ].sum(axis=1)
    return {
        "policy": policy_name,
        "stockout_rate": result["stockout_flag"].mean(),
        "service_level_achieved": result["service_achieved"].mean(),
        "lost_sales_units": result["lost_sales_units"].sum(),
        "ending_inventory_units": result["ending_inventory_units"].sum(),
        "order_units": result["order_qty"].sum(),
        "transfer_units": result["inbound_transfer_qty"].fillna(0).sum(),
        "lost_sales_proxy_jpy": result["lost_sales_proxy_jpy"].sum(),
        "holding_cost_jpy": result["holding_cost_jpy"].sum(),
        "order_handling_cost_jpy": result["order_handling_cost_jpy"].sum(),
        "transfer_cost_jpy": result["transfer_cost_jpy"].sum(),
        "total_scm_cost_jpy": result["total_scm_cost_jpy"].sum(),
    }


def _scenario_base(inputs: dict[str, pd.DataFrame], service_level_target: float) -> pd.DataFrame:
    forecast_28d = (
        inputs["forecast"].groupby(["store_id", "sku_id"], as_index=False)["forecast_units"]
        .sum()
        .rename(columns={"forecast_units": "forecast_28d"})
    )
    policy = inputs["policy"].copy()
    policy["service_level"] = service_level_target
    policy["z_value"] = z_value(service_level_target)
    policy["safety_stock"] = (
        policy["std_daily_demand"] * policy["z_value"] * np.sqrt(policy["lead_time_days"])
    )
    policy["rop"] = policy["avg_daily_demand"] * policy["lead_time_days"] + policy["safety_stock"]
    policy["days_of_supply"] = policy["stock_on_hand"] / policy["avg_daily_demand"].replace(0, np.nan)
    policy["stock_status"] = np.select(
        [policy["stock_on_hand"] < policy["rop"], policy["days_of_supply"] > 42],
        ["Stockout Risk", "Overstock"],
        default="Healthy",
    )

    transfers = make_transfer_recommendations(policy, inputs["stores"], inputs["products"])
    transfer_adjustments = _transfer_adjustments(transfers)
    base = (
        policy.merge(forecast_28d, on=["store_id", "sku_id"], how="left")
        .merge(transfer_adjustments, on=["store_id", "sku_id"], how="left")
        .merge(inputs["products"][["sku_id", "unit_price"]], on="sku_id", how="left")
    )
    base[["inbound_transfer_qty", "outbound_transfer_qty"]] = base[
        ["inbound_transfer_qty", "outbound_transfer_qty"]
    ].fillna(0)
    base["rop_gap_order_qty"] = (base["rop"] - base["stock_on_hand"]).clip(lower=0)
    base["forecast_gap_after_rop"] = (
        base["forecast_28d"] - base["stock_on_hand"] - base["rop_gap_order_qty"]
    ).clip(lower=0)
    base["baseline_order_qty"] = (
        base["rop_gap_order_qty"] + CONTROL_FORECAST_GAP_COVERAGE * base["forecast_gap_after_rop"]
    ).round()
    base["forecast_gap_after_baseline"] = (
        base["forecast_28d"] - base["stock_on_hand"] - base["baseline_order_qty"]
    ).clip(lower=0)
    base["candidate_order_qty"] = (
        base["baseline_order_qty"]
        + TREATMENT_REMAINING_GAP_COVERAGE * base["forecast_gap_after_baseline"]
    ).round()
    base["candidate_order_qty"] = base["candidate_order_qty"].clip(
        upper=(base["forecast_28d"] * TREATMENT_DEMAND_CAP).round()
    )
    base["inbound_transfer_qty"] = (
        base["inbound_transfer_qty"] * TREATMENT_TRANSFER_REALIZATION
    ).round()
    base["outbound_transfer_qty"] = (
        base["outbound_transfer_qty"] * TREATMENT_TRANSFER_REALIZATION
    ).round()
    return base


def build_policy_sensitivity_outputs(
    data_dir: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    output_dir = Path(output_dir or data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs(data_dir)

    rows: list[dict[str, float | str]] = []
    summary_rows: list[dict[str, float | bool]] = []
    for service_level, shortage_multiplier, holding_multiplier, order_multiplier in product(
        SERVICE_LEVELS, COST_MULTIPLIERS, COST_MULTIPLIERS, COST_MULTIPLIERS
    ):
        base = _scenario_base(inputs, service_level)
        scenario_id = (
            f"sl_{service_level:.2f}__shortage_{shortage_multiplier:.2f}__"
            f"holding_{holding_multiplier:.2f}__order_{order_multiplier:.2f}"
        )
        common = {
            "scenario_id": scenario_id,
            "service_level_target": service_level,
            "lost_sales_cost_multiplier": shortage_multiplier,
            "holding_cost_multiplier": holding_multiplier,
            "order_cost_multiplier": order_multiplier,
        }
        baseline = _evaluate(
            base,
            BASELINE_LABEL,
            "baseline_order_qty",
            transfer_enabled=False,
            lost_sales_cost_multiplier=shortage_multiplier,
            holding_cost_multiplier=holding_multiplier,
            order_cost_multiplier=order_multiplier,
        )
        candidate = _evaluate(
            base,
            CANDIDATE_LABEL,
            "candidate_order_qty",
            transfer_enabled=True,
            lost_sales_cost_multiplier=shortage_multiplier,
            holding_cost_multiplier=holding_multiplier,
            order_cost_multiplier=order_multiplier,
        )
        rows.extend([{**common, **baseline}, {**common, **candidate}])
        baseline_cost = float(baseline["total_scm_cost_jpy"])
        candidate_cost = float(candidate["total_scm_cost_jpy"])
        summary_rows.append(
            {
                **common,
                "baseline_cost_jpy": baseline_cost,
                "candidate_cost_jpy": candidate_cost,
                "cost_reduction_jpy": baseline_cost - candidate_cost,
                "cost_reduction_pct": (baseline_cost - candidate_cost) / baseline_cost,
                "service_lift_pp": 100
                * (
                    float(candidate["service_level_achieved"])
                    - float(baseline["service_level_achieved"])
                ),
                "stockout_delta_pp": 100
                * (float(candidate["stockout_rate"]) - float(baseline["stockout_rate"])),
                "candidate_lower_cost": candidate_cost < baseline_cost,
            }
        )

    results = pd.DataFrame(rows)
    scenario_summary = pd.DataFrame(summary_rows)
    robustness = (
        scenario_summary.groupby("service_level_target", as_index=False)
        .agg(
            scenarios=("scenario_id", "count"),
            candidate_lower_cost_share=("candidate_lower_cost", "mean"),
            median_cost_reduction_pct=("cost_reduction_pct", "median"),
            minimum_cost_reduction_pct=("cost_reduction_pct", "min"),
            maximum_cost_reduction_pct=("cost_reduction_pct", "max"),
            median_service_lift_pp=("service_lift_pp", "median"),
            median_stockout_delta_pp=("stockout_delta_pp", "median"),
        )
        .round(4)
    )
    numeric_columns = results.select_dtypes(include="number").columns
    results[numeric_columns] = results[numeric_columns].round(4)
    scenario_summary = scenario_summary.round(4)
    results.to_csv(output_dir / "policy_sensitivity_results.csv", index=False)
    scenario_summary.to_csv(output_dir / "policy_sensitivity_scenarios.csv", index=False)
    robustness.to_csv(output_dir / "policy_sensitivity_robustness.csv", index=False)
    return {
        "results": results,
        "scenario_summary": scenario_summary,
        "robustness": robustness,
    }


if __name__ == "__main__":
    build_policy_sensitivity_outputs(Path(__file__).resolve().parents[1] / "data")
