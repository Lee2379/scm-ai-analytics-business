from pathlib import Path

import pandas as pd

from src.scm_engine import (
    calculate_inventory_policy,
    load_dataset,
    make_forecast,
    make_recommendations,
    z_value,
)


DATA_DIR = Path(__file__).parents[1] / "data"


def test_service_level_mapping_and_default() -> None:
    assert z_value(0.90) == 1.28
    assert z_value(0.95) == 1.65
    assert z_value(0.97) == 1.88
    assert z_value(0.93) == 1.65


def test_forecast_covers_every_pair_for_28_days() -> None:
    data = load_dataset(DATA_DIR)
    forecast = make_forecast(data["sales"], horizon_days=28)
    pair_count = data["sales"][["store_id", "sku_id"]].drop_duplicates().shape[0]

    assert len(forecast) == pair_count * 28
    assert forecast["forecast_units"].ge(0).all()
    assert forecast.groupby(["store_id", "sku_id"])["date"].nunique().eq(28).all()


def test_policy_and_recommendation_invariants() -> None:
    data = load_dataset(DATA_DIR)
    forecast = make_forecast(data["sales"])
    policy = calculate_inventory_policy(data["sales"], data["inventory"], data["supply"])
    recommendations = make_recommendations(policy, forecast)

    expected_pairs = data["sales"][["store_id", "sku_id"]].drop_duplicates().shape[0]
    assert len(policy) == expected_pairs
    assert policy["safety_stock"].ge(0).all()
    assert policy["rop"].ge(policy["safety_stock"]).all()
    assert set(policy["stock_status"]).issubset({"Healthy", "Stockout Risk", "Overstock"})
    assert recommendations["recommended_order_qty"].ge(0).all()
    assert pd.api.types.is_integer_dtype(recommendations["recommended_order_qty"])

