from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


SERVICE_LEVEL_Z = {
    0.90: 1.28,
    0.95: 1.65,
    0.97: 1.88,
    0.98: 2.05,
}


@dataclass(frozen=True)
class DataPaths:
    data_dir: Path

    @property
    def sales(self) -> Path:
        return self.data_dir / "sales.csv"

    @property
    def products(self) -> Path:
        return self.data_dir / "products.csv"

    @property
    def stores(self) -> Path:
        return self.data_dir / "stores.csv"

    @property
    def inventory(self) -> Path:
        return self.data_dir / "inventory.csv"

    @property
    def supply(self) -> Path:
        return self.data_dir / "supply.csv"

    @property
    def forecast(self) -> Path:
        return self.data_dir / "forecast.csv"

    @property
    def policy(self) -> Path:
        return self.data_dir / "inventory_policy.csv"

    @property
    def recommendations(self) -> Path:
        return self.data_dir / "recommendations.csv"

    @property
    def transfers(self) -> Path:
        return self.data_dir / "transfer_recommendations.csv"


def z_value(service_level: float) -> float:
    return SERVICE_LEVEL_Z.get(round(float(service_level), 2), 1.65)


def load_dataset(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    paths = DataPaths(Path(data_dir))
    return {
        "sales": pd.read_csv(paths.sales, parse_dates=["date"]),
        "products": pd.read_csv(paths.products),
        "stores": pd.read_csv(paths.stores),
        "inventory": pd.read_csv(paths.inventory, parse_dates=["date"]),
        "supply": pd.read_csv(paths.supply),
    }


def make_forecast(sales: pd.DataFrame, horizon_days: int = 28) -> pd.DataFrame:
    last_date = sales["date"].max()
    recent = sales[sales["date"] > last_date - pd.Timedelta(days=56)].copy()
    recent["dow"] = recent["date"].dt.dayofweek

    combo_cols = ["store_id", "sku_id"]
    base = (
        recent.groupby(combo_cols + ["dow"], as_index=False)["units_sold"]
        .mean()
        .rename(columns={"units_sold": "dow_avg"})
    )
    trend = (
        recent.groupby(combo_cols, as_index=False)
        .agg(
            avg_daily_demand=("units_sold", "mean"),
            std_daily_demand=("units_sold", "std"),
            last_14d=("units_sold", lambda x: x.tail(14).mean()),
            first_14d=("units_sold", lambda x: x.head(14).mean()),
        )
    )
    trend["trend_factor"] = (trend["last_14d"] / trend["first_14d"].replace(0, np.nan)).fillna(1).clip(0.75, 1.25)

    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    combos = sales[combo_cols].drop_duplicates()
    future = combos.merge(pd.DataFrame({"date": future_dates}), how="cross")
    future["dow"] = future["date"].dt.dayofweek
    future = future.merge(base, on=combo_cols + ["dow"], how="left")
    future = future.merge(trend[combo_cols + ["avg_daily_demand", "std_daily_demand", "trend_factor"]], on=combo_cols, how="left")
    future["forecast_units"] = (
        future["dow_avg"].fillna(future["avg_daily_demand"]) * future["trend_factor"]
    ).clip(lower=0).round(1)
    return future[["date", "store_id", "sku_id", "forecast_units", "avg_daily_demand", "std_daily_demand"]]


def calculate_inventory_policy(
    sales: pd.DataFrame,
    inventory: pd.DataFrame,
    supply: pd.DataFrame,
    demand_window_days: int = 56,
) -> pd.DataFrame:
    last_date = sales["date"].max()
    recent = sales[sales["date"] > last_date - pd.Timedelta(days=demand_window_days)]
    demand_stats = (
        recent.groupby(["store_id", "sku_id"], as_index=False)
        .agg(
            avg_daily_demand=("units_sold", "mean"),
            std_daily_demand=("units_sold", "std"),
        )
    )
    demand_stats["std_daily_demand"] = demand_stats["std_daily_demand"].fillna(0)

    latest_inventory = (
        inventory.sort_values("date")
        .groupby(["store_id", "sku_id"], as_index=False)
        .tail(1)
        [["store_id", "sku_id", "stock_on_hand"]]
    )

    policy = demand_stats.merge(supply, on=["store_id", "sku_id"], how="left")
    policy = policy.merge(latest_inventory, on=["store_id", "sku_id"], how="left")
    policy["z_value"] = policy["service_level"].apply(z_value)
    policy["safety_stock"] = (
        policy["std_daily_demand"] * policy["z_value"] * np.sqrt(policy["lead_time_days"])
    )
    policy["rop"] = policy["avg_daily_demand"] * policy["lead_time_days"] + policy["safety_stock"]
    policy["days_of_supply"] = policy["stock_on_hand"] / policy["avg_daily_demand"].replace(0, np.nan)
    policy["reorder_flag"] = policy["stock_on_hand"] < policy["rop"]
    policy["stock_status"] = np.select(
        [
            policy["stock_on_hand"] < policy["rop"],
            policy["days_of_supply"] > 42,
        ],
        ["Stockout Risk", "Overstock"],
        default="Healthy",
    )
    return policy.round(
        {
            "avg_daily_demand": 2,
            "std_daily_demand": 2,
            "safety_stock": 1,
            "rop": 1,
            "days_of_supply": 1,
        }
    )


def make_recommendations(policy: pd.DataFrame, forecast: pd.DataFrame, horizon_days: int = 28) -> pd.DataFrame:
    forecast_sum = (
        forecast.groupby(["store_id", "sku_id"], as_index=False)["forecast_units"]
        .sum()
        .rename(columns={"forecast_units": "forecast_28d"})
    )
    rec = policy.merge(forecast_sum, on=["store_id", "sku_id"], how="left")
    rec["target_stock"] = rec["forecast_28d"] + rec["safety_stock"]
    rec["recommended_order_qty"] = (rec["target_stock"] - rec["stock_on_hand"]).clip(lower=0).round().astype(int)
    rec["risk_score"] = (
        (rec["rop"] - rec["stock_on_hand"]) / rec["rop"].replace(0, np.nan)
    ).fillna(0).clip(lower=0)
    rec["priority"] = np.select(
        [rec["risk_score"] >= 0.35, rec["risk_score"] >= 0.12, rec["recommended_order_qty"] > 0],
        ["High", "Medium", "Low"],
        default="Monitor",
    )
    rec["reason"] = rec.apply(
        lambda row: (
            f"Current stock {row.stock_on_hand:.0f} is below ROP {row.rop:.0f}; "
            f"order {row.recommended_order_qty:.0f} units to cover 28-day demand and safety stock."
        )
        if row.recommended_order_qty > 0
        else "No order needed; current stock is above ROP.",
        axis=1,
    )
    return rec.sort_values(["priority", "risk_score"], ascending=[True, False])


def make_transfer_recommendations(
    policy: pd.DataFrame,
    stores: pd.DataFrame,
    products: pd.DataFrame,
    max_pairs: int = 20,
) -> pd.DataFrame:
    shortage = policy[policy["stock_on_hand"] < policy["rop"]].copy()
    surplus = policy[policy["days_of_supply"] > 42].copy()
    rows: list[dict[str, object]] = []

    store_city = stores.set_index("store_id")["city"].to_dict()
    product_name = products.set_index("sku_id")["product_name"].to_dict()

    for sku_id, sku_shortage in shortage.groupby("sku_id"):
        sku_surplus = surplus[surplus["sku_id"] == sku_id]
        for _, need in sku_shortage.iterrows():
            needed_qty = max(0, int(round(need["rop"] - need["stock_on_hand"])))
            for _, extra in sku_surplus.iterrows():
                if need["store_id"] == extra["store_id"]:
                    continue
                surplus_qty = max(0, int(round(extra["stock_on_hand"] - extra["rop"])))
                qty = min(needed_qty, surplus_qty)
                if qty <= 0:
                    continue
                rows.append(
                    {
                        "sku_id": sku_id,
                        "product_name": product_name.get(sku_id, sku_id),
                        "from_store": extra["store_id"],
                        "from_city": store_city.get(extra["store_id"], ""),
                        "to_store": need["store_id"],
                        "to_city": store_city.get(need["store_id"], ""),
                        "transfer_qty": qty,
                        "reason": f"Move {qty} units from overstock store to stockout-risk store.",
                    }
                )
                break

    return pd.DataFrame(rows).head(max_pairs)


def build_all_outputs(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    paths = DataPaths(Path(data_dir))
    data = load_dataset(paths.data_dir)
    forecast = make_forecast(data["sales"])
    policy = calculate_inventory_policy(data["sales"], data["inventory"], data["supply"])
    recommendations = make_recommendations(policy, forecast)
    transfers = make_transfer_recommendations(policy, data["stores"], data["products"])

    forecast.to_csv(paths.forecast, index=False)
    policy.to_csv(paths.policy, index=False)
    recommendations.to_csv(paths.recommendations, index=False)
    transfers.to_csv(paths.transfers, index=False)
    return {
        "forecast": forecast,
        "policy": policy,
        "recommendations": recommendations,
        "transfers": transfers,
    }
