from __future__ import annotations

import os
import textwrap
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(os.getenv("TEMP", ".")) / "scm-matplotlib"))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns


TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}
BLUE = {"xlight": "#EAF1FE", "light": "#CEDFFE", "base": "#A3BEFA", "mid": "#5477C4", "dark": "#2E4780"}


def _theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "savefig.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "grid.color": TOKENS["grid"],
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": ["Inter", "Segoe UI", "DejaVu Sans", "Arial"],
            "axes.spines.top": False,
            "axes.spines.right": False,
        },
    )


def _header(fig: plt.Figure, ax: plt.Axes, title: str, subtitle: str) -> None:
    title = textwrap.fill(title, width=76, break_long_words=False)
    subtitle = textwrap.fill(subtitle, width=110, break_long_words=False)
    fig.subplots_adjust(top=0.78, left=0.19, right=0.96, bottom=0.16)
    left = ax.get_position().x0
    fig.text(left, 0.965, title, ha="left", va="top", fontsize=15, fontweight="semibold", color=TOKENS["ink"])
    fig.text(left, 0.895, subtitle, ha="left", va="top", fontsize=9.5, color=TOKENS["muted"], linespacing=1.2)
    sns.despine(ax=ax)


def _save(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)


def plot_forecast_model_comparison(metrics: pd.DataFrame, output_path: Path) -> None:
    _theme()
    plot_df = metrics.sort_values("wape", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    bars = ax.barh(
        plot_df["model"],
        plot_df["wape"],
        color=BLUE["base"],
        edgecolor=BLUE["dark"],
        linewidth=1.0,
    )
    for bar, value in zip(bars, plot_df["wape"]):
        ax.text(value + 0.002, bar.get_y() + bar.get_height() / 2, f"{value:.1%}", va="center", fontsize=9, color=TOKENS["ink"])
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("WAPE (lower is better)")
    ax.set_ylabel("")
    ax.grid(axis="x", color=TOKENS["grid"])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, plot_df["wape"].max() * 1.20)
    _header(
        fig,
        ax,
        "Forecast model comparison",
        "Three non-overlapping rolling origins · 28-day horizon · 60 SKU-store pairs · 5,040 actual observations per model",
    )
    _save(fig, output_path)


def plot_forecast_segment_heatmap(segment_metrics: pd.DataFrame, output_path: Path) -> None:
    _theme()
    order = ["High", "Medium", "Low"]
    matrix = segment_metrics.pivot(index="model", columns="demand_velocity", values="wape").reindex(columns=order)
    fig, ax = plt.subplots(figsize=(9.6, 5.7))
    cmap = sns.blend_palette([TOKENS["panel"], BLUE["xlight"], BLUE["light"], BLUE["base"], BLUE["mid"]], as_cmap=True)
    sns.heatmap(
        matrix,
        ax=ax,
        cmap=cmap,
        linewidths=1.0,
        linecolor=TOKENS["panel"],
        annot=True,
        fmt=".1%",
        cbar_kws={"label": "WAPE"},
    )
    ax.set_xlabel("Demand velocity")
    ax.set_ylabel("")
    _header(
        fig,
        ax,
        "Forecast error by demand velocity",
        "Post-hoc demand segments use mean observed daily units across the evaluation windows; lower WAPE indicates better calibration",
    )
    _save(fig, output_path)


def plot_policy_sensitivity_heatmap(scenarios: pd.DataFrame, output_path: Path) -> None:
    _theme()
    base_slice = scenarios[
        (scenarios["service_level_target"] == 0.95)
        & (scenarios["order_cost_multiplier"] == 1.00)
    ]
    matrix = base_slice.pivot(
        index="holding_cost_multiplier",
        columns="lost_sales_cost_multiplier",
        values="cost_reduction_pct",
    ).sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    cmap = sns.blend_palette([TOKENS["panel"], BLUE["xlight"], BLUE["light"], BLUE["base"], BLUE["mid"]], as_cmap=True)
    sns.heatmap(
        matrix,
        ax=ax,
        cmap=cmap,
        linewidths=1.0,
        linecolor=TOKENS["panel"],
        annot=True,
        fmt=".1%",
        cbar_kws={"label": "Candidate cost reduction"},
    )
    ax.set_xlabel("Lost-sales cost multiplier")
    ax.set_ylabel("Holding-cost multiplier")
    _header(
        fig,
        ax,
        "Policy cost reduction remains positive across the central sensitivity grid",
        "Service-level target 95% · order-cost multiplier 1.00 · synthetic 28-day policy simulation · values compare candidate with baseline",
    )
    _save(fig, output_path)


def build_analysis_visuals(data_dir: str | Path, output_dir: str | Path) -> list[Path]:
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    paths = [
        output_dir / "forecast_model_comparison.png",
        output_dir / "forecast_error_by_velocity.png",
        output_dir / "policy_sensitivity_heatmap.png",
    ]
    plot_forecast_model_comparison(pd.read_csv(data_dir / "forecast_backtest_model_metrics.csv"), paths[0])
    plot_forecast_segment_heatmap(pd.read_csv(data_dir / "forecast_backtest_segment_metrics.csv"), paths[1])
    plot_policy_sensitivity_heatmap(pd.read_csv(data_dir / "policy_sensitivity_scenarios.csv"), paths[2])
    return paths


if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[1]
    build_analysis_visuals(repository_root / "data", repository_root / "assets" / "analysis")
