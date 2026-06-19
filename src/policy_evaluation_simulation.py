from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from scipy import stats


TRANSFER_COST_PER_UNIT = 120
ORDER_HANDLING_COST_PER_UNIT = 40
HOLDING_COST_RATE_28D = 0.015
CONTROL_FORECAST_GAP_COVERAGE = 0.80
TREATMENT_REMAINING_GAP_COVERAGE = 0.20
TREATMENT_TRANSFER_REALIZATION = 0.25
TREATMENT_DEMAND_CAP = 1.00
BASELINE_LABEL = "Baseline: planner policy"
CANDIDATE_LABEL = "Candidate: constrained AI-assisted policy"


def load_inputs(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    return {
        "policy": pd.read_csv(data_dir / "inventory_policy.csv"),
        "recommendations": pd.read_csv(data_dir / "recommendations.csv"),
        "forecast": pd.read_csv(data_dir / "forecast.csv"),
        "products": pd.read_csv(data_dir / "products.csv"),
        "stores": pd.read_csv(data_dir / "stores.csv"),
        "transfers": pd.read_csv(data_dir / "transfer_recommendations.csv"),
    }


def _transfer_adjustments(transfers: pd.DataFrame) -> pd.DataFrame:
    if transfers.empty:
        return pd.DataFrame(columns=["store_id", "sku_id", "inbound_transfer_qty", "outbound_transfer_qty"])

    inbound = (
        transfers.groupby(["to_store", "sku_id"], as_index=False)["transfer_qty"]
        .sum()
        .rename(columns={"to_store": "store_id", "transfer_qty": "inbound_transfer_qty"})
    )
    outbound = (
        transfers.groupby(["from_store", "sku_id"], as_index=False)["transfer_qty"]
        .sum()
        .rename(columns={"from_store": "store_id", "transfer_qty": "outbound_transfer_qty"})
    )
    return inbound.merge(outbound, on=["store_id", "sku_id"], how="outer").fillna(0)


def _evaluate_policy(df: pd.DataFrame, group: str, order_col: str, transfer_enabled: bool) -> pd.DataFrame:
    result = df.copy()
    if transfer_enabled:
        result["inbound_transfer_qty"] = result["inbound_transfer_qty"].fillna(0)
        result["outbound_transfer_qty"] = result["outbound_transfer_qty"].fillna(0)
    else:
        result["inbound_transfer_qty"] = 0
        result["outbound_transfer_qty"] = 0

    result["group"] = group
    result["order_qty"] = result[order_col].clip(lower=0)
    result["available_units"] = (
        result["stock_on_hand"]
        + result["order_qty"]
        + result["inbound_transfer_qty"]
        - result["outbound_transfer_qty"]
    ).clip(lower=0)
    result["fulfilled_units"] = result[["available_units", "forecast_28d"]].min(axis=1)
    result["lost_sales_units"] = (result["forecast_28d"] - result["fulfilled_units"]).clip(lower=0)
    result["ending_inventory_units"] = (result["available_units"] - result["forecast_28d"]).clip(lower=0)
    result["service_level"] = result["fulfilled_units"] / result["forecast_28d"].replace(0, pd.NA)
    result["stockout_flag"] = result["lost_sales_units"] > 0
    result["ending_days_of_supply"] = result["ending_inventory_units"] / result["avg_daily_demand"].replace(0, pd.NA)
    result["overstock_flag"] = result["ending_days_of_supply"] > 42

    result["lost_sales_proxy_jpy"] = result["lost_sales_units"] * result["unit_price"]
    result["holding_cost_jpy"] = result["ending_inventory_units"] * result["unit_price"] * HOLDING_COST_RATE_28D
    result["order_handling_cost_jpy"] = result["order_qty"] * ORDER_HANDLING_COST_PER_UNIT
    result["transfer_cost_jpy"] = (
        result["inbound_transfer_qty"] + result["outbound_transfer_qty"]
    ) * TRANSFER_COST_PER_UNIT
    result["total_scm_cost_jpy"] = (
        result["lost_sales_proxy_jpy"]
        + result["holding_cost_jpy"]
        + result["order_handling_cost_jpy"]
        + result["transfer_cost_jpy"]
    )
    return result


def _paired_t_test(control: pd.Series, treatment: pd.Series, direction: str) -> dict[str, float | str]:
    if direction not in {"increase", "decrease"}:
        raise ValueError("direction must be either 'increase' or 'decrease'")

    improvement = treatment - control if direction == "increase" else control - treatment
    improvement = improvement.dropna()
    sample_size = int(improvement.shape[0])
    mean_improvement = float(improvement.mean())
    std_improvement = float(improvement.std(ddof=1))

    if sample_size < 2 or std_improvement == 0:
        p_value = 0.0 if mean_improvement > 0 else 1.0
        ci_low = mean_improvement
        ci_high = mean_improvement
        t_stat = math.inf if mean_improvement > 0 else 0.0
        effect_size = math.inf if mean_improvement > 0 else 0.0
    else:
        standard_error = std_improvement / math.sqrt(sample_size)
        t_stat = mean_improvement / standard_error
        p_value = float(stats.t.sf(t_stat, df=sample_size - 1))
        t_crit = float(stats.t.ppf(0.975, df=sample_size - 1))
        ci_low = mean_improvement - t_crit * standard_error
        ci_high = mean_improvement + t_crit * standard_error
        effect_size = mean_improvement / std_improvement

    return {
        "test": "Paired t-test",
        "sample_size": sample_size,
        "mean_improvement": round(mean_improvement, 4),
        "confidence_interval_95": f"[{ci_low:.4f}, {ci_high:.4f}]",
        "test_statistic": round(float(t_stat), 4) if math.isfinite(t_stat) else "inf",
        "effect_size": f"Cohen's dz={effect_size:.3f}" if math.isfinite(effect_size) else "Cohen's dz=inf",
        "p_value": p_value,
    }


def _mcnemar_exact_test(control: pd.Series, treatment: pd.Series) -> dict[str, float | str]:
    control_bool = control.astype(bool)
    treatment_bool = treatment.astype(bool)
    improved = int((control_bool & ~treatment_bool).sum())
    worsened = int((~control_bool & treatment_bool).sum())
    discordant = improved + worsened
    p_value = 1.0 if discordant == 0 else float(stats.binomtest(improved, discordant, 0.5, alternative="greater").pvalue)

    return {
        "test": "McNemar exact test",
        "sample_size": int(control_bool.shape[0]),
        "mean_improvement": round(float(control_bool.mean() - treatment_bool.mean()), 4),
        "confidence_interval_95": "Not reported for exact McNemar test",
        "test_statistic": f"improved={improved}, worsened={worsened}",
        "effect_size": f"risk difference={control_bool.mean() - treatment_bool.mean():.3f}",
        "p_value": p_value,
    }


def _build_statistical_tests(results: pd.DataFrame) -> pd.DataFrame:
    paired = (
        results.pivot_table(
            index=["store_id", "sku_id"],
            columns="group",
            values=[
                "total_scm_cost_jpy",
                "lost_sales_proxy_jpy",
                "service_level",
                "stockout_flag",
            ],
            aggfunc="first",
        )
        .dropna()
    )

    control_label = BASELINE_LABEL
    treatment_label = CANDIDATE_LABEL
    test_specs = [
        {
            "metric": "Total SCM cost proxy",
            "null_hypothesis": "The AI-assisted candidate policy does not reduce mean total SCM cost versus the baseline policy.",
            "alternative_hypothesis": "The AI-assisted candidate policy reduces mean total SCM cost versus the baseline policy.",
            "method": _paired_t_test(
                paired[("total_scm_cost_jpy", control_label)],
                paired[("total_scm_cost_jpy", treatment_label)],
                direction="decrease",
            ),
            "business_interpretation": "Tests whether the candidate policy reduces simulated SCM cost at the SKU-store level.",
        },
        {
            "metric": "Lost sales proxy",
            "null_hypothesis": "The AI-assisted candidate policy does not reduce mean lost-sales proxy versus the baseline policy.",
            "alternative_hypothesis": "The AI-assisted candidate policy reduces mean lost-sales proxy versus the baseline policy.",
            "method": _paired_t_test(
                paired[("lost_sales_proxy_jpy", control_label)],
                paired[("lost_sales_proxy_jpy", treatment_label)],
                direction="decrease",
            ),
            "business_interpretation": "Tests whether the candidate policy reduces forecast-period lost-sales exposure in simulation.",
        },
        {
            "metric": "Service level",
            "null_hypothesis": "The AI-assisted candidate policy does not increase mean service level versus the baseline policy.",
            "alternative_hypothesis": "The AI-assisted candidate policy increases mean service level versus the baseline policy.",
            "method": _paired_t_test(
                paired[("service_level", control_label)],
                paired[("service_level", treatment_label)],
                direction="increase",
            ),
            "business_interpretation": "Tests whether the candidate policy improves simulated demand fulfillment at the SKU-store level.",
        },
        {
            "metric": "Stockout flag",
            "null_hypothesis": "The probability of stockout improvement is not greater than the probability of stockout worsening.",
            "alternative_hypothesis": "The AI-assisted candidate policy reduces stockout occurrence versus the baseline policy.",
            "method": _mcnemar_exact_test(
                paired[("stockout_flag", control_label)],
                paired[("stockout_flag", treatment_label)],
            ),
            "business_interpretation": "Tests whether paired stockout outcomes improve more often than they worsen.",
        },
    ]

    rows = []
    for spec in test_specs:
        method = spec["method"]
        p_value = float(method["p_value"])
        p_value_display = "p < 0.05" if p_value < 0.05 else "p >= 0.05"
        rows.append(
            {
                "metric": spec["metric"],
                "null_hypothesis": spec["null_hypothesis"],
                "alternative_hypothesis": spec["alternative_hypothesis"],
                "test": method["test"],
                "sample_size": method["sample_size"],
                "mean_improvement": method["mean_improvement"],
                "confidence_interval_95": method["confidence_interval_95"],
                "test_statistic": method["test_statistic"],
                "effect_size": method["effect_size"],
                "p_value": float(f"{p_value:.12g}"),
                "p_value_display": p_value_display,
                "significance_0_05": p_value < 0.05,
                "business_interpretation": spec["business_interpretation"],
            }
        )
    return pd.DataFrame(rows)


def build_policy_evaluation_outputs(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    inputs = load_inputs(data_dir)

    forecast_28d = (
        inputs["forecast"].groupby(["store_id", "sku_id"], as_index=False)["forecast_units"]
        .sum()
        .rename(columns={"forecast_units": "forecast_28d"})
    )
    transfer_adj = _transfer_adjustments(inputs["transfers"])

    base = (
        inputs["policy"]
        .merge(forecast_28d, on=["store_id", "sku_id"], how="left")
        .merge(
            inputs["recommendations"][["store_id", "sku_id", "recommended_order_qty", "priority", "risk_score"]],
            on=["store_id", "sku_id"],
            how="left",
        )
        .merge(transfer_adj, on=["store_id", "sku_id"], how="left")
        .merge(inputs["products"][["sku_id", "product_name", "category", "unit_price"]], on="sku_id", how="left")
        .merge(inputs["stores"][["store_id", "city", "store_type"]], on="store_id", how="left")
    )
    base["forecast_28d"] = base["forecast_28d"].fillna(0)
    base["recommended_order_qty"] = base["recommended_order_qty"].fillna(0)
    base["priority"] = base["priority"].fillna("Monitor")
    base["risk_score"] = base["risk_score"].fillna(0)
    base["rop_gap_order_qty"] = (base["rop"] - base["stock_on_hand"]).clip(lower=0)
    base["forecast_gap_after_rop"] = (
        base["forecast_28d"] - base["stock_on_hand"] - base["rop_gap_order_qty"]
    ).clip(lower=0)
    base["control_order_qty"] = (
        base["rop_gap_order_qty"] + CONTROL_FORECAST_GAP_COVERAGE * base["forecast_gap_after_rop"]
    ).round()

    base["forecast_gap_after_control"] = (
        base["forecast_28d"] - base["stock_on_hand"] - base["control_order_qty"]
    ).clip(lower=0)
    base["treatment_order_qty"] = (
        base["control_order_qty"] + TREATMENT_REMAINING_GAP_COVERAGE * base["forecast_gap_after_control"]
    ).round()
    base["treatment_order_qty"] = base["treatment_order_qty"].clip(upper=(base["forecast_28d"] * TREATMENT_DEMAND_CAP).round())
    base["treatment_inbound_transfer_qty"] = (base["inbound_transfer_qty"].fillna(0) * TREATMENT_TRANSFER_REALIZATION).round()
    base["treatment_outbound_transfer_qty"] = (base["outbound_transfer_qty"].fillna(0) * TREATMENT_TRANSFER_REALIZATION).round()

    control = _evaluate_policy(base, BASELINE_LABEL, "control_order_qty", transfer_enabled=False)
    treatment_base = base.copy()
    treatment_base["inbound_transfer_qty"] = treatment_base["treatment_inbound_transfer_qty"]
    treatment_base["outbound_transfer_qty"] = treatment_base["treatment_outbound_transfer_qty"]
    treatment = _evaluate_policy(treatment_base, CANDIDATE_LABEL, "treatment_order_qty", transfer_enabled=True)
    results = pd.concat([control, treatment], ignore_index=True)

    metric_summary = (
        results.groupby("group", as_index=False)
        .agg(
            experimental_units=("sku_id", "count"),
            stockout_rate=("stockout_flag", "mean"),
            overstock_rate=("overstock_flag", "mean"),
            service_level=("service_level", "mean"),
            lost_sales_units=("lost_sales_units", "sum"),
            lost_sales_proxy_jpy=("lost_sales_proxy_jpy", "sum"),
            holding_cost_jpy=("holding_cost_jpy", "sum"),
            order_handling_cost_jpy=("order_handling_cost_jpy", "sum"),
            transfer_cost_jpy=("transfer_cost_jpy", "sum"),
            total_scm_cost_jpy=("total_scm_cost_jpy", "sum"),
        )
        .round(3)
    )

    control_cost = metric_summary.loc[
        metric_summary["group"] == BASELINE_LABEL, "total_scm_cost_jpy"
    ].iloc[0]
    treatment_cost = metric_summary.loc[
        metric_summary["group"] == CANDIDATE_LABEL, "total_scm_cost_jpy"
    ].iloc[0]
    metric_summary["cost_delta_vs_control_jpy"] = metric_summary["total_scm_cost_jpy"] - control_cost
    metric_summary["cost_reduction_vs_control_pct"] = (
        (control_cost - metric_summary["total_scm_cost_jpy"]) / control_cost
    ).round(4)

    segment_summary = (
        results.groupby(["group", "city", "category"], as_index=False)
        .agg(
            experimental_units=("sku_id", "count"),
            stockout_rate=("stockout_flag", "mean"),
            service_level=("service_level", "mean"),
            lost_sales_units=("lost_sales_units", "sum"),
            total_scm_cost_jpy=("total_scm_cost_jpy", "sum"),
        )
        .round(3)
    )
    statistical_tests = _build_statistical_tests(results)

    results = results.round(
        {
            "forecast_28d": 1,
            "available_units": 1,
            "fulfilled_units": 1,
            "lost_sales_units": 1,
            "ending_inventory_units": 1,
            "service_level": 4,
            "ending_days_of_supply": 1,
            "lost_sales_proxy_jpy": 0,
            "holding_cost_jpy": 0,
            "order_handling_cost_jpy": 0,
            "transfer_cost_jpy": 0,
            "total_scm_cost_jpy": 0,
        }
    )

    results.to_csv(data_dir / "policy_eval_results.csv", index=False)
    metric_summary.to_csv(data_dir / "policy_eval_kpi_summary.csv", index=False)
    segment_summary.to_csv(data_dir / "policy_eval_segment_summary.csv", index=False)
    statistical_tests.to_csv(data_dir / "policy_eval_statistical_tests.csv", index=False)
    return {
        "policy_results": results,
        "policy_kpi_summary": metric_summary,
        "policy_segment_summary": segment_summary,
        "policy_statistical_tests": statistical_tests,
    }


if __name__ == "__main__":
    build_policy_evaluation_outputs(Path(__file__).resolve().parents[1] / "data")
