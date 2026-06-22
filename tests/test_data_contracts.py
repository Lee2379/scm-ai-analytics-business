from pathlib import Path

import pandas as pd
import pytest


DATA_DIR = Path(__file__).parents[1] / "data"
REQUIRED_FILES = {
    "sales.csv",
    "products.csv",
    "stores.csv",
    "inventory.csv",
    "supply.csv",
    "forecast.csv",
    "inventory_policy.csv",
    "recommendations.csv",
    "transfer_recommendations.csv",
    "policy_eval_kpi_summary.csv",
    "forecast_backtest_model_metrics.csv",
    "forecast_backtest_origin_metrics.csv",
    "forecast_backtest_segment_metrics.csv",
    "policy_sensitivity_scenarios.csv",
    "policy_sensitivity_robustness.csv",
}
PROHIBITED_DIRECT_IDENTIFIER_COLUMNS = {
    "email",
    "phone",
    "phone_number",
    "address",
    "customer_name",
    "employee_name",
    "credit_card",
    "account_number",
}


def test_required_analytical_assets_are_versioned() -> None:
    available = {path.name for path in DATA_DIR.glob("*.csv")}
    assert REQUIRED_FILES.issubset(available)


@pytest.mark.parametrize("csv_path", sorted(DATA_DIR.glob("*.csv")))
def test_synthetic_tables_exclude_direct_personal_identifiers(csv_path: Path) -> None:
    columns = {column.lower() for column in pd.read_csv(csv_path, nrows=0).columns}
    assert columns.isdisjoint(PROHIBITED_DIRECT_IDENTIFIER_COLUMNS)


def test_offline_policy_summary_has_comparable_cohorts() -> None:
    summary = pd.read_csv(DATA_DIR / "policy_eval_kpi_summary.csv")

    assert len(summary) == 2
    assert summary["group"].str.contains("Baseline").sum() == 1
    assert summary["group"].str.contains("Candidate").sum() == 1
    assert summary["experimental_units"].nunique() == 1
    assert summary["experimental_units"].iloc[0] == 60
