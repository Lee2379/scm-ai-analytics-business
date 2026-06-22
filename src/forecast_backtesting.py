from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


PAIR_KEYS = ["store_id", "sku_id"]
MODEL_NAMES = [
    "Seasonal naive (weekday)",
    "Moving average (28d)",
    "Exponentially weighted mean",
    "Global gradient boosting",
]
FEATURE_COLUMNS = [
    "store_code",
    "sku_code",
    "dow",
    "month",
    "day_of_year_sin",
    "day_of_year_cos",
    "promotion",
    "temperature",
    "precipitation",
    "is_holiday_like",
    "mean_7",
    "mean_28",
    "std_28",
    "weekday_mean",
]


def _metric_frame(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    def summarize(part: pd.DataFrame) -> pd.Series:
        actual = part["actual_units"].sum()
        error = part["prediction"] - part["actual_units"]
        return pd.Series(
            {
                "observations": len(part),
                "actual_units": actual,
                "predicted_units": part["prediction"].sum(),
                "wape": error.abs().sum() / actual if actual else np.nan,
                "mae": error.abs().mean(),
                "bias": error.sum() / actual if actual else np.nan,
            }
        )

    return (
        df.groupby(group_columns, observed=True, sort=False)
        .apply(summarize, include_groups=False)
        .reset_index()
        .round({"actual_units": 1, "predicted_units": 1, "wape": 4, "mae": 3, "bias": 4})
    )


def _add_training_features(frame: pd.DataFrame) -> pd.DataFrame:
    featured = frame.sort_values(PAIR_KEYS + ["date"]).copy()
    grouped = featured.groupby(PAIR_KEYS, sort=False)["units_sold"]
    featured["mean_7"] = grouped.transform(lambda series: series.shift(1).rolling(7, min_periods=7).mean())
    featured["mean_28"] = grouped.transform(lambda series: series.shift(1).rolling(28, min_periods=28).mean())
    featured["std_28"] = grouped.transform(lambda series: series.shift(1).rolling(28, min_periods=28).std())
    featured["weekday_mean"] = featured.groupby(PAIR_KEYS + ["dow"], sort=False)["units_sold"].transform(
        lambda series: series.shift(1).expanding(min_periods=2).mean()
    )
    return featured


def _add_calendar_features(frame: pd.DataFrame, store_codes: dict[str, int], sku_codes: dict[str, int]) -> pd.DataFrame:
    featured = frame.copy()
    featured["dow"] = featured["date"].dt.dayofweek
    featured["month"] = featured["date"].dt.month
    day_of_year = featured["date"].dt.dayofyear
    featured["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    featured["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    featured["store_code"] = featured["store_id"].map(store_codes)
    featured["sku_code"] = featured["sku_id"].map(sku_codes)
    return featured


def _future_feature_snapshot(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    pair_stats = (
        train.sort_values(PAIR_KEYS + ["date"])
        .groupby(PAIR_KEYS, as_index=False)
        .agg(
            mean_7=("units_sold", lambda series: series.tail(7).mean()),
            mean_28=("units_sold", lambda series: series.tail(28).mean()),
            std_28=("units_sold", lambda series: series.tail(28).std()),
        )
    )
    weekday_stats = (
        train[train["date"] > train["date"].max() - pd.Timedelta(days=56)]
        .groupby(PAIR_KEYS + ["dow"], as_index=False)["units_sold"]
        .mean()
        .rename(columns={"units_sold": "weekday_mean"})
    )
    return test.merge(pair_stats, on=PAIR_KEYS, how="left").merge(
        weekday_stats, on=PAIR_KEYS + ["dow"], how="left"
    )


def _baseline_predictions(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    recent = train[train["date"] > train["date"].max() - pd.Timedelta(days=56)]
    weekday = (
        recent.groupby(PAIR_KEYS + ["dow"], as_index=False)["units_sold"]
        .mean()
        .rename(columns={"units_sold": "prediction"})
    )
    seasonal = test[PAIR_KEYS + ["dow"]].merge(weekday, on=PAIR_KEYS + ["dow"], how="left")["prediction"]

    moving = (
        train.sort_values(PAIR_KEYS + ["date"])
        .groupby(PAIR_KEYS, as_index=False)
        .tail(28)
        .groupby(PAIR_KEYS, as_index=False)["units_sold"]
        .mean()
        .rename(columns={"units_sold": "prediction"})
    )
    moving_prediction = test[PAIR_KEYS].merge(moving, on=PAIR_KEYS, how="left")["prediction"]

    ewm = (
        train.sort_values(PAIR_KEYS + ["date"])
        .groupby(PAIR_KEYS, as_index=False)
        .tail(56)
        .groupby(PAIR_KEYS)["units_sold"]
        .apply(lambda series: series.ewm(alpha=0.20, adjust=False).mean().iloc[-1])
        .rename("prediction")
        .reset_index()
    )
    ewm_prediction = test[PAIR_KEYS].merge(ewm, on=PAIR_KEYS, how="left")["prediction"]

    return {
        "Seasonal naive (weekday)": seasonal.to_numpy(),
        "Moving average (28d)": moving_prediction.to_numpy(),
        "Exponentially weighted mean": ewm_prediction.to_numpy(),
    }


def _gradient_boosting_prediction(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    training_features = _add_training_features(train).dropna(subset=FEATURE_COLUMNS)
    future_features = _future_feature_snapshot(train, test)
    model = HistGradientBoostingRegressor(
        learning_rate=0.07,
        max_iter=180,
        max_leaf_nodes=31,
        min_samples_leaf=30,
        l2_regularization=0.10,
        random_state=42,
    )
    model.fit(training_features[FEATURE_COLUMNS], training_features["units_sold"])
    return model.predict(future_features[FEATURE_COLUMNS])


def build_forecast_backtest_outputs(
    data_dir: str | Path,
    output_dir: str | Path | None = None,
    horizon_days: int = 28,
    n_splits: int = 3,
) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    output_dir = Path(output_dir or data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sales = pd.read_csv(data_dir / "sales.csv", parse_dates=["date"])
    products = pd.read_csv(data_dir / "products.csv")
    stores = pd.read_csv(data_dir / "stores.csv")
    store_codes = {value: index for index, value in enumerate(sorted(sales["store_id"].unique()))}
    sku_codes = {value: index for index, value in enumerate(sorted(sales["sku_id"].unique()))}
    sales = _add_calendar_features(sales, store_codes, sku_codes)

    maximum_date = sales["date"].max()
    split_outputs: list[pd.DataFrame] = []
    for split_index in range(n_splits):
        periods_back = n_splits - split_index - 1
        test_end = maximum_date - pd.Timedelta(days=periods_back * horizon_days)
        test_start = test_end - pd.Timedelta(days=horizon_days - 1)
        origin = test_start - pd.Timedelta(days=1)
        train = sales[sales["date"] <= origin].copy()
        test = sales[(sales["date"] >= test_start) & (sales["date"] <= test_end)].copy()
        if train["date"].nunique() < 56 or test["date"].nunique() != horizon_days:
            raise ValueError(f"Insufficient history for origin {origin.date()}")

        predictions = _baseline_predictions(train, test)
        predictions["Global gradient boosting"] = _gradient_boosting_prediction(train, test)
        base_columns = ["date", "store_id", "sku_id", "units_sold"]
        for model_name, values in predictions.items():
            model_output = test[base_columns].rename(columns={"units_sold": "actual_units"}).copy()
            model_output["prediction"] = np.clip(values, 0, None)
            model_output["model"] = model_name
            model_output["origin"] = origin
            model_output["horizon_day"] = (model_output["date"] - origin).dt.days
            split_outputs.append(model_output)

    predictions = pd.concat(split_outputs, ignore_index=True)
    predictions = predictions.merge(products[["sku_id", "category"]], on="sku_id", how="left").merge(
        stores[["store_id", "city"]], on="store_id", how="left"
    )
    pair_velocity = (
        predictions.groupby(PAIR_KEYS, as_index=False)["actual_units"]
        .mean()
        .rename(columns={"actual_units": "mean_daily_units"})
    )
    pair_velocity["demand_velocity"] = pd.cut(
        pair_velocity["mean_daily_units"],
        bins=[-np.inf, 25, 45, np.inf],
        labels=["Low", "Medium", "High"],
    )
    predictions = predictions.merge(pair_velocity, on=PAIR_KEYS, how="left")
    predictions["absolute_error"] = (predictions["prediction"] - predictions["actual_units"]).abs()
    predictions["error"] = predictions["prediction"] - predictions["actual_units"]

    model_metrics = _metric_frame(predictions, ["model"]).sort_values(["wape", "mae"]).reset_index(drop=True)
    model_metrics["wape_rank"] = model_metrics["wape"].rank(method="dense").astype(int)
    origin_metrics = _metric_frame(predictions, ["model", "origin"])
    segment_metrics = _metric_frame(predictions, ["model", "demand_velocity"])
    city_category_metrics = _metric_frame(predictions, ["model", "city", "category"])

    predictions = predictions.round({"actual_units": 1, "prediction": 3, "absolute_error": 3, "error": 3})
    predictions.to_csv(output_dir / "forecast_backtest_predictions.csv", index=False)
    model_metrics.to_csv(output_dir / "forecast_backtest_model_metrics.csv", index=False)
    origin_metrics.to_csv(output_dir / "forecast_backtest_origin_metrics.csv", index=False)
    segment_metrics.to_csv(output_dir / "forecast_backtest_segment_metrics.csv", index=False)
    city_category_metrics.to_csv(output_dir / "forecast_backtest_city_category_metrics.csv", index=False)
    return {
        "predictions": predictions,
        "model_metrics": model_metrics,
        "origin_metrics": origin_metrics,
        "segment_metrics": segment_metrics,
        "city_category_metrics": city_category_metrics,
    }


if __name__ == "__main__":
    build_forecast_backtest_outputs(Path(__file__).resolve().parents[1] / "data")

