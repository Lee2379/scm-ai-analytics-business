from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).parents[1] / "data"


def test_backtest_preserves_time_order_and_expected_coverage() -> None:
    predictions = pd.read_csv(
        DATA_DIR / "forecast_backtest_predictions.csv",
        parse_dates=["date", "origin"],
    )

    assert (predictions["date"] > predictions["origin"]).all()
    assert predictions["origin"].nunique() == 3
    assert predictions["model"].nunique() == 4
    assert predictions.groupby(["model", "origin"])["horizon_day"].nunique().eq(28).all()
    assert predictions.groupby(["model", "origin"])[["store_id", "sku_id"]].apply(
        lambda frame: frame.drop_duplicates().shape[0], include_groups=False
    ).eq(60).all()
    assert predictions["prediction"].ge(0).all()


def test_model_ranking_is_complete_and_metric_values_are_valid() -> None:
    metrics = pd.read_csv(DATA_DIR / "forecast_backtest_model_metrics.csv")

    assert len(metrics) == 4
    assert set(metrics["wape_rank"]) == {1, 2, 3, 4}
    assert metrics["wape"].between(0, 1).all()
    assert metrics["mae"].gt(0).all()
    assert metrics["bias"].between(-1, 1).all()


def test_policy_sensitivity_grid_and_pairwise_comparison_contract() -> None:
    scenarios = pd.read_csv(DATA_DIR / "policy_sensitivity_scenarios.csv")
    results = pd.read_csv(DATA_DIR / "policy_sensitivity_results.csv")

    assert scenarios["scenario_id"].nunique() == 81
    assert len(results) == 162
    assert set(results["policy"].str.split(":").str[0]) == {"Baseline", "Candidate"}
    assert scenarios["candidate_lower_cost"].all()
    assert scenarios["cost_reduction_pct"].between(0, 1).all()
    assert set(scenarios["service_level_target"].round(2)) == {0.90, 0.95, 0.97}
