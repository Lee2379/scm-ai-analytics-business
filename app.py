from __future__ import annotations

import html
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from src.agent import build_scm_context, gemini_ready, gemini_reply_if_configured, load_agent_tables, local_agent_reply


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

RETAIL_RED = "#e60012"
INK_BLACK = "#111111"
STATUS_COLORS = {
    "Healthy": INK_BLACK,
    "Stockout Risk": RETAIL_RED,
    "Overstock": "#8a8a8a",
}
STORE_COLORS = [RETAIL_RED, INK_BLACK, "#777777", "#b0000d", "#d8d8d8"]
LANG_OPTIONS = {
    "en": "English",
    "ja": "\u65e5\u672c\u8a9e",
    "ko": "\ud55c\uad6d\uc5b4",
}

JP = {
    "project": "AI SCM\u30c7\u30fc\u30bf\u5206\u6790\u30b7\u30b9\u30c6\u30e0",
    "hero_title": "AI SCM Data Analysis Project",
    "summary": "\u9700\u8981\u4e88\u6e2c\u3001SKU\u30fb\u5e97\u8217\u5225\u767a\u6ce8\u70b9\u3001\u5b89\u5168\u5728\u5eab\u3001\u88dc\u5145\u63a8\u85a6\u3001\u5e97\u8217\u9593\u5728\u5eab\u79fb\u52d5\u3092\u7d71\u5408\u3057\u305fSCM\u610f\u601d\u6c7a\u5b9a\u652f\u63f4\u30b7\u30b9\u30c6\u30e0\u3002",
    "chatbot": "\u30c1\u30e3\u30c3\u30c8\u30dc\u30c3\u30c8",
    "chat_desc": "\u73fe\u5728\u306eSCM\u30c7\u30e2\u30c7\u30fc\u30bf\u3092\u3082\u3068\u306b\u3001\u6b20\u54c1\u30ea\u30b9\u30af\u3001\u767a\u6ce8\u70b9\u3001\u5b89\u5168\u5728\u5eab\u3001\u88dc\u5145\u6570\u91cf\u3001\u5e97\u8217\u9593\u79fb\u52d5\u3092\u8ffd\u8de1\u3057\u307e\u3059\u3002",
    "controls": "\u64cd\u4f5c",
    "city": "\u90fd\u5e02",
    "status": "\u5728\u5eab\u30b9\u30c6\u30fc\u30bf\u30b9",
    "agent_lang": "\u30a8\u30fc\u30b8\u30a7\u30f3\u30c8\u8a00\u8a9e",
    "live_question": "\u30ea\u30a2\u30eb\u30bf\u30a4\u30e0SCM\u8cea\u554f",
    "track": "SCM\u3092\u8ffd\u8de1",
    "pairs": "SKU\u30fb\u5e97\u8217\u30da\u30a2",
    "stockout": "\u6b20\u54c1\u30ea\u30b9\u30af",
    "overstock": "\u904e\u5270\u5728\u5eab",
    "order_units": "\u63a8\u5968\u767a\u6ce8\u6570",
    "overview": "\u6982\u8981",
    "forecast": "\u9700\u8981\u4e88\u6e2c",
    "rop": "\u767a\u6ce8\u70b9\u30fb\u5b89\u5168\u5728\u5eab",
    "transfer": "\u5e97\u8217\u9593\u79fb\u52d5",
    "agent": "AI\u30a8\u30fc\u30b8\u30a7\u30f3\u30c8",
    "risk_dist": "\u5728\u5eab\u30ea\u30b9\u30af\u5206\u5e03",
    "city_risk": "\u90fd\u5e02\u5225\u30ea\u30b9\u30af",
    "top_replenishment": "\u512a\u5148\u88dc\u5145\u63a8\u85a6",
    "product": "\u5546\u54c1",
    "recent_sales": "\u76f4\u8fd1\u8ca9\u58f2\u30d1\u30bf\u30fc\u30f3",
    "sales_history": "\u5e97\u8217\u5225\u8ca9\u58f2\u5c65\u6b74",
    "policy": "SKU\u30fb\u5e97\u8217\u5225\u767a\u6ce8\u70b9\u30dd\u30ea\u30b7\u30fc",
    "transfer_rec": "\u5e97\u8217\u9593\u5728\u5eab\u79fb\u52d5\u63a8\u85a6",
    "no_transfer": "\u73fe\u5728\u306e\u30b7\u30ca\u30ea\u30aa\u3067\u306f\u5e97\u8217\u9593\u79fb\u52d5\u63a8\u85a6\u306f\u3042\u308a\u307e\u305b\u3093\u3002",
    "manager": "SCM\u30de\u30cd\u30fc\u30b8\u30e3\u30fc\u30a8\u30fc\u30b8\u30a7\u30f3\u30c8",
    "question": "\u8cea\u554f",
    "ask_agent": "SCM Agent\u306b\u8cea\u554f",
}


st.set_page_config(
    page_title="AI SCM Data Analysis Project",
    page_icon="SCM",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    if "GEMINI_API_KEY" in st.secrets and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass


@st.cache_data
def load_tables() -> dict[str, pd.DataFrame]:
    return {
        "sales": pd.read_csv(DATA_DIR / "sales.csv", parse_dates=["date"]),
        "calendar": pd.read_csv(DATA_DIR / "calendar.csv", parse_dates=["date"]),
        "weather": pd.read_csv(DATA_DIR / "weather.csv", parse_dates=["date"]),
        "inventory": pd.read_csv(DATA_DIR / "inventory.csv", parse_dates=["date"]),
        "products": pd.read_csv(DATA_DIR / "products.csv"),
        "stores": pd.read_csv(DATA_DIR / "stores.csv"),
        "policy": pd.read_csv(DATA_DIR / "inventory_policy.csv"),
        "recommendations": pd.read_csv(DATA_DIR / "recommendations.csv"),
        "forecast": pd.read_csv(DATA_DIR / "forecast.csv", parse_dates=["date"]),
        "transfers": pd.read_csv(DATA_DIR / "transfer_recommendations.csv"),
        "policy_results": pd.read_csv(DATA_DIR / "policy_eval_results.csv"),
        "policy_summary": pd.read_csv(DATA_DIR / "policy_eval_kpi_summary.csv"),
        "policy_segments": pd.read_csv(DATA_DIR / "policy_eval_segment_summary.csv"),
        "policy_tests": pd.read_csv(DATA_DIR / "policy_eval_statistical_tests.csv"),
    }


@st.cache_data
def build_forecast_explanations(
    sales: pd.DataFrame,
    forecast: pd.DataFrame,
    products: pd.DataFrame,
    stores: pd.DataFrame,
) -> pd.DataFrame:
    """Create transparent demand-driver diagnostics from committed demo data.

    These diagnostics explain observed demand patterns around the 28-day forecast.
    They are deliberately labelled as driver signals rather than SHAP values because
    the committed forecast table does not contain per-row model attribution output.
    """

    history = sales.copy()
    history["date"] = pd.to_datetime(history["date"])
    history["is_weekend"] = history["date"].dt.dayofweek >= 5
    latest_date = history["date"].max()
    recent_start = latest_date - pd.Timedelta(days=27)
    previous_start = recent_start - pd.Timedelta(days=28)

    rows: list[dict[str, object]] = []
    for (store_id, sku_id), group in history.groupby(["store_id", "sku_id"], sort=False):
        recent = group[group["date"] >= recent_start]
        previous = group[(group["date"] >= previous_start) & (group["date"] < recent_start)]
        recent_daily = float(recent["units_sold"].mean())
        previous_daily = float(previous["units_sold"].mean()) if not previous.empty else recent_daily
        baseline_28d = recent_daily * 28

        def relative_lift(flag: pd.Series) -> float:
            exposed = group.loc[flag, "units_sold"]
            reference = group.loc[~flag, "units_sold"]
            if exposed.empty or reference.empty or reference.mean() == 0:
                return 0.0
            return float((exposed.mean() / reference.mean() - 1) * 100)

        promotion_lift = relative_lift(group["promotion"].astype(bool))
        weekend_lift = relative_lift(group["is_weekend"])
        holiday_lift = relative_lift(group["is_holiday_like"].astype(bool))
        momentum = 0.0 if previous_daily == 0 else (recent_daily / previous_daily - 1) * 100
        volatility = 0.0 if group["units_sold"].mean() == 0 else group["units_sold"].std() / group["units_sold"].mean() * 100
        temperature_signal = float(group["units_sold"].corr(group["temperature"]) * 100)
        if pd.isna(temperature_signal):
            temperature_signal = 0.0

        driver_values = {
            "Recent momentum": momentum,
            "Promotion response": promotion_lift,
            "Weekend pattern": weekend_lift,
            "Holiday pattern": holiday_lift,
            "Temperature sensitivity": temperature_signal,
        }
        top_driver = max(driver_values, key=lambda name: abs(driver_values[name]))
        rows.append(
            {
                "store_id": store_id,
                "sku_id": sku_id,
                "baseline_28d": baseline_28d,
                "momentum_pct": momentum,
                "promotion_lift_pct": promotion_lift,
                "weekend_lift_pct": weekend_lift,
                "holiday_lift_pct": holiday_lift,
                "temperature_signal_pct": temperature_signal,
                "volatility_pct": volatility,
                "top_driver": top_driver,
                "top_driver_signal_pct": driver_values[top_driver],
                "confidence": "High" if volatility < 35 else "Medium" if volatility < 55 else "Low",
            }
        )

    explanation = pd.DataFrame(rows)
    forecast_28d = forecast.groupby(["store_id", "sku_id"], as_index=False)["forecast_units"].sum()
    forecast_28d = forecast_28d.rename(columns={"forecast_units": "forecast_28d"})
    explanation = explanation.merge(forecast_28d, on=["store_id", "sku_id"], how="left")
    explanation["forecast_vs_baseline_pct"] = (
        explanation["forecast_28d"] / explanation["baseline_28d"].replace(0, pd.NA) - 1
    ) * 100
    explanation = explanation.merge(products[["sku_id", "product_name", "category"]], on="sku_id", how="left")
    explanation = explanation.merge(stores[["store_id", "city"]], on="store_id", how="left")
    return explanation

def data_ready() -> bool:
    required_files = [
        "sales.csv",
        "calendar.csv",
        "weather.csv",
        "inventory.csv",
        "inventory_policy.csv",
        "recommendations.csv",
        "policy_eval_results.csv",
        "policy_eval_kpi_summary.csv",
        "policy_eval_segment_summary.csv",
        "policy_eval_statistical_tests.csv",
    ]
    return all((DATA_DIR / name).exists() for name in required_files)


def ask_scm_agent(question: str, lang: str) -> str:
    agent_tables = load_agent_tables(DATA_DIR)
    if os.environ.get("SCM_LOCAL_ONLY") == "1":
        return local_agent_reply(question, agent_tables, lang=lang)
    scm_context = build_scm_context(agent_tables)
    gemini_answer = gemini_reply_if_configured(question, scm_context, lang=lang)
    return gemini_answer or local_agent_reply(question, agent_tables, lang=lang)


def response_box(text: str) -> None:
    safe = html.escape(text).replace("\n", "<br>")
    st.markdown(f'<div class="chat-response">{safe}</div>', unsafe_allow_html=True)


def tr(lang: str, en: str, ja: str, ko: str) -> str:
    return {"en": en, "ja": ja, "ko": ko}.get(lang, en)


st.markdown(
    """
    <style>
    .stApp {
      background:
        linear-gradient(90deg, rgba(230, 0, 18, .05) 0 1px, transparent 1px 100%),
        linear-gradient(180deg, #ffffff 0%, #f7f7f7 100%);
      background-size: 56px 56px, auto;
      color: #111111;
    }
    [data-testid="stHeader"] {
      background: rgba(255, 255, 255, 0.88);
      border-bottom: 1px solid #ececec;
      backdrop-filter: blur(16px);
    }
    [data-testid="stSidebar"] {
      background: #ffffff;
      border-right: 1px solid #ececec;
    }
    .language-strip {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 10px;
      margin: 0 0 14px;
      color: #555555;
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .hero,
    .chat-panel {
      min-height: 304px;
      border: 1px solid #111111;
      border-radius: 0;
      background: #ffffff;
      box-shadow: 0 24px 60px rgba(0, 0, 0, .12);
    }
    .hero {
      min-height: auto;
      padding: 24px 28px;
      overflow: hidden;
    }
    .hero-kicker {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 14px;
      color: #e60012;
      font-size: 13px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .hero-kicker::before {
      width: 28px;
      height: 3px;
      background: #e60012;
      content: "";
    }
    .ja-small {
      display: block;
      margin-top: 4px;
      color: #777777;
      font-size: 12px;
      font-weight: 700;
      line-height: 1.35;
      text-transform: none;
    }
    .hero h1 {
      margin: 0 0 10px;
      color: #111111;
      font-size: clamp(30px, 4vw, 44px);
      letter-spacing: -1.4px;
      line-height: 1.02;
      font-weight: 900;
    }
    .project-name {
      margin: 0 0 12px;
      color: #111111;
      font-size: 20px;
      font-weight: 900;
    }
    .hero p {
      margin: 0;
      color: #4b4b4b;
      font-size: 16px;
      line-height: 1.55;
      max-width: 820px;
    }
    .model-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 22px;
    }
    .model-meta span {
      padding: 7px 9px;
      border: 1px solid #d8d8d8;
      color: #333333;
      background: #fafafa;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .35px;
      text-transform: uppercase;
    }
    .chat-panel {
      min-height: auto;
      padding: 0;
      margin-bottom: 10px;
      border: 2px solid #e60012;
      border-radius: 0;
      overflow: hidden;
      background: #ffffff;
      box-shadow: 0 22px 52px rgba(0, 0, 0, .18);
    }
    .chat-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      background: #e60012;
      color: #ffffff;
    }
    .chat-title {
      margin: 0;
      color: #ffffff;
      font-size: 15px;
      font-weight: 900;
      line-height: 1.15;
    }
    .chat-close {
      width: 24px;
      height: 24px;
      display: grid;
      place-items: center;
      background: rgba(255, 255, 255, .16);
      color: #ffffff;
      font-weight: 900;
      line-height: 1;
    }
    .chat-response {
      min-height: 160px;
      max-height: 330px;
      overflow-y: auto;
      margin-top: 0;
      padding: 16px;
      border: 0;
      background: #ffffff;
      color: #111111;
      font-size: 14px;
      line-height: 1.62;
      white-space: pre-wrap;
      box-shadow: none;
    }
    .chat-response:empty::before {
      color: #8a8a8a;
      content: "";
    }
    div[data-testid="stForm"] {
      border: 0;
      border-radius: 0;
      background: transparent;
      padding: 0;
      box-shadow: none;
    }
    div[data-testid="stForm"] textarea {
      min-height: 128px !important;
      border-radius: 0 !important;
      border: 1px solid #111111 !important;
      font-size: 15px !important;
      line-height: 1.55 !important;
      box-shadow: none !important;
    }
    [data-testid="stMetric"] {
      padding: 18px 18px 16px;
      border: 1px solid #e4e4e4;
      background: #ffffff;
      box-shadow: 0 12px 34px rgba(0, 0, 0, .06);
    }
    [data-testid="stMetricLabel"] {
      color: #555555;
      font-weight: 800;
    }
    [data-testid="stMetricValue"] {
      color: #e60012;
      font-weight: 900;
    }
    div[data-baseweb="tab-list"] {
      gap: 28px;
      border-bottom: 1px solid #d8d8d8;
    }
    button[data-baseweb="tab"] {
      min-height: 58px;
      border: 0;
      border-bottom: 3px solid transparent;
      border-radius: 0;
      background: transparent;
      color: #111111;
      font-weight: 900;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
      border-bottom-color: #e60012;
      background: transparent;
      color: #e60012;
    }
    button[data-baseweb="tab"] p {
      margin: 0;
      line-height: 1.12;
    }
    .stButton > button {
      border: 1px solid #e60012;
      border-radius: 0;
      background: #e60012;
      color: #ffffff;
      font-weight: 900;
    }
    .stButton > button:hover {
      border-color: #111111;
      background: #111111;
      color: #ffffff;
    }
    .stDataFrame {
      border: 1px solid #ececec;
      background: #ffffff;
    }
    @media (max-width: 760px) {
      .hero h1 {
        font-size: 36px;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    :root {
      --scm-red: #e60012;
      --scm-ink: #171717;
      --scm-muted: #6b6f76;
      --scm-line: #e3e5e8;
      --scm-soft: #f7f8f9;
    }
    .stApp {
      background: #ffffff;
      color: var(--scm-ink);
    }
    [data-testid="stHeader"] {
      background: rgba(255,255,255,.96);
      border-bottom: 1px solid var(--scm-line);
      backdrop-filter: blur(12px);
    }
    [data-testid="stMainBlockContainer"] {
      max-width: 100%;
      padding: 2.1rem 23rem 4rem 2rem;
    }
    [data-testid="stSidebar"] {
      width: 224px !important;
      min-width: 224px !important;
      background: #fbfbfb;
      border-right: 1px solid var(--scm-line);
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
      padding: 1.4rem .8rem 1rem;
    }
    .workspace-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      padding: 0 0 18px;
      border-bottom: 1px solid var(--scm-line);
    }
    .workspace-header h1 {
      margin: 0 0 4px;
      color: var(--scm-ink);
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -.7px;
      line-height: 1.15;
    }
    .workspace-header p {
      margin: 0;
      color: var(--scm-muted);
      font-size: 13px;
    }
    .model-status {
      padding-top: 4px;
      color: var(--scm-muted);
      font-size: 12px;
      line-height: 1.65;
      text-align: right;
    }
    .model-status strong { color: var(--scm-ink); }
    .status-dot {
      display: inline-block;
      width: 7px;
      height: 7px;
      margin-right: 6px;
      border-radius: 50%;
      background: #22a447;
    }
    .filter-label {
      margin: 16px 0 6px;
      color: var(--scm-muted);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .45px;
      text-transform: uppercase;
    }
    .sidebar-brand {
      padding: 6px 8px 18px;
      border-bottom: 1px solid var(--scm-line);
      color: var(--scm-ink);
      font-size: 16px;
      font-weight: 850;
      letter-spacing: -.3px;
      text-align: left;
      white-space: nowrap;
    }
    .sidebar-section {
      margin: 18px 8px 8px;
      color: #8a8d92;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .55px;
      text-transform: uppercase;
    }
    [data-testid="stSidebar"] .stButton > button {
      justify-content: flex-start;
      width: 100%;
      min-height: 38px;
      padding: 8px 10px;
      border: 0;
      border-left: 3px solid transparent;
      border-radius: 0 3px 3px 0;
      background: transparent;
      color: #3f444b;
      box-shadow: none;
      font-size: 13px;
      font-weight: 600;
      text-align: left;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
      border-left-color: #c9ccd1;
      background: #f5f6f7;
      color: var(--scm-ink);
    }
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
      border-left-color: var(--scm-red);
      background: #fff2f3;
      color: var(--scm-red);
      font-weight: 800;
    }
    [data-testid="stMetric"] {
      min-height: 94px;
      padding: 13px 16px 11px;
      border: 0;
      border-right: 1px solid var(--scm-line);
      background: #ffffff;
      box-shadow: none;
    }
    [data-testid="stMetricLabel"] {
      color: #555b63;
      font-size: 12px;
      font-weight: 650;
    }
    [data-testid="stMetricValue"] {
      color: var(--scm-red);
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -.5px;
    }
    [data-testid="stPlotlyChart"] {
      border: 1px solid var(--scm-line);
      border-radius: 4px;
      background: #fff;
      overflow: hidden;
    }
    [data-testid="stDataFrame"] {
      border: 1px solid var(--scm-line);
      border-radius: 4px;
      background: #fff;
    }
    .st-key-copilot_rail {
      position: fixed;
      z-index: 990;
      top: 82px;
      right: 22px;
      width: 316px;
      max-height: calc(100vh - 104px);
      padding: 0 13px 14px;
      overflow-y: auto;
      border: 1px solid var(--scm-line);
      border-radius: 4px;
      background: #fff;
      box-shadow: 0 8px 24px rgba(15, 18, 22, .07);
    }
    .st-key-copilot_rail .chat-panel {
      margin: 0 -13px 10px;
      border: 0;
      border-bottom: 1px solid #c7000f;
      border-radius: 3px 3px 0 0;
      box-shadow: none;
    }
    .st-key-copilot_rail .chat-header {
      padding: 13px 14px;
      border-bottom: 1px solid #f0d4d6;
      background: #ffffff;
      color: var(--scm-red);
    }
    .st-key-copilot_rail .chat-title { color: var(--scm-red); }
    .st-key-copilot_rail textarea {
      min-height: 112px !important;
      border-color: #cfd2d6 !important;
      border-radius: 3px !important;
      font-size: 13px !important;
    }
    .st-key-copilot_rail .stButton > button {
      width: 100%;
      min-height: 36px;
      border: 1px solid #d9dce0;
      border-radius: 3px;
      background: #ffffff;
      color: #3f444b;
      font-size: 12px;
      font-weight: 600;
      text-align: left;
    }
    .st-key-copilot_rail .stButton > button:hover {
      border-color: var(--scm-red);
      background: #fff5f6;
      color: var(--scm-red);
    }
    .st-key-copilot_rail [data-testid="stFormSubmitButton"] button {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--scm-red);
      border-radius: 3px;
      background: var(--scm-red);
      color: #ffffff;
      font-weight: 750;
    }
    .chat-response {
      min-height: 0;
      max-height: none;
      overflow-y: visible;
      padding: 14px 4px 18px;
      border-bottom: 1px solid var(--scm-line);
      font-size: 12.5px;
      line-height: 1.6;
    }
    .language-strip { display: none; }
    div[data-baseweb="select"] > div,
    [data-testid="stSegmentedControl"] { border-radius: 3px !important; }
    [data-testid="stSegmentedControl"] button {
      min-width: 0 !important;
      padding-left: 9px !important;
      padding-right: 9px !important;
      font-size: 12px !important;
    }
    h1, h2, h3 { color: var(--scm-ink); letter-spacing: -.25px; }
    @media (max-width: 980px) {
      [data-testid="stMainBlockContainer"] { padding-right: 1.2rem; }
      .st-key-copilot_rail {
        position: relative;
        top: auto;
        right: auto;
        width: auto;
        max-height: none;
        margin-bottom: 1rem;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not data_ready():
    st.warning("Demo data files are missing. Please verify that the required CSV files exist in the data directory.")
    st.stop()

if "site_lang" not in st.session_state:
    st.session_state["site_lang"] = "ja"

language_labels = {"English": "en", "日本語": "ja", "한국어": "ko"}
lang = st.session_state["site_lang"]
question_label = tr(lang, "Live SCM question", JP["live_question"], "실시간 SCM 질문")
question_placeholder = tr(
    lang,
    "Ask about reorder actions, stockout risk, safety stock, or store transfers.",
    "再発注、欠品リスク、安全在庫、店舗間移動について質問してください。",
    "재발주, 결품 리스크, 안전재고, 매장 간 이동에 대해 질문하세요.",
)
track_label = tr(lang, "Track SCM", JP["track"], "SCM 추적")

tables = load_tables()
sales = tables["sales"]
products = tables["products"]
stores = tables["stores"]
policy = tables["policy"].merge(products[["sku_id", "product_name", "category"]], on="sku_id", how="left")
policy = policy.merge(stores[["store_id", "city", "store_type"]], on="store_id", how="left")
recs = tables["recommendations"].merge(products[["sku_id", "product_name", "category"]], on="sku_id", how="left")
recs = recs.merge(stores[["store_id", "city"]], on="store_id", how="left")
forecast = tables["forecast"].merge(products[["sku_id", "product_name"]], on="sku_id", how="left")
explanations = build_forecast_explanations(tables["sales"], tables["forecast"], products, stores)
transfers = tables["transfers"]
policy_results = tables["policy_results"]
policy_summary = tables["policy_summary"]
policy_segments = tables["policy_segments"]
policy_tests = tables["policy_tests"]

latest_data_date = pd.to_datetime(sales["date"]).max()
st.markdown(
    f"""
    <div class="workspace-header">
      <div>
        <h1>{tr(lang, 'SCM Analytics Workspace', 'SCM分析ワークスペース', 'SCM 분석 워크스페이스')}</h1>
        <p>{tr(lang, 'Integrated demand forecasting, inventory risk, and decision support', '需要予測・在庫リスクの統合分析と意思決定支援', '수요예측·재고 리스크 통합 분석 및 의사결정 지원')}</p>
      </div>
      <div class="model-status">
        <strong>{tr(lang, 'Model status', 'モデルステータス', '모델 상태')}</strong><br>
        {tr(lang, 'Operational', '正常稼働', '정상 운영')} · {tr(lang, 'latest data', '最終データ', '최신 데이터')} {latest_data_date:%Y-%m-%d}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

cities = ["All"] + sorted(policy["city"].dropna().unique().tolist())
statuses = ["All"] + sorted(policy["stock_status"].dropna().unique().tolist())
filter_lang, filter_city, filter_status, filter_horizon = st.columns([1.65, 1.15, 1.15, 1.35])
with filter_lang:
    st.markdown('<div class="filter-label">Website language</div>', unsafe_allow_html=True)
    current_language_label = next(label for label, code in language_labels.items() if code == st.session_state["site_lang"])
    selected_language_label = st.segmented_control(
        "Website Language",
        list(language_labels),
        default=current_language_label,
        label_visibility="collapsed",
    )
    if selected_language_label and language_labels[selected_language_label] != st.session_state["site_lang"]:
        st.session_state["site_lang"] = language_labels[selected_language_label]
        st.session_state.pop("top_chat_reply", None)
        st.session_state.pop("top_chat_reply_lang", None)
        st.rerun()
with filter_city:
    st.markdown(f'<div class="filter-label">{tr(lang, "City", "都市", "도시")}</div>', unsafe_allow_html=True)
    city = st.selectbox(tr(lang, "City", "都市", "도시"), cities, label_visibility="collapsed")
with filter_status:
    st.markdown(f'<div class="filter-label">{tr(lang, "Inventory status", "在庫ステータス", "재고 상태")}</div>', unsafe_allow_html=True)
    status = st.selectbox(tr(lang, "Inventory status", "在庫ステータス", "재고 상태"), statuses, label_visibility="collapsed")
with filter_horizon:
    st.markdown(f'<div class="filter-label">{tr(lang, "Analysis horizon", "分析ホライズン", "분석 기간")}</div>', unsafe_allow_html=True)
    st.selectbox(
        tr(lang, "Analysis horizon", "分析ホライズン", "분석 기간"),
        [tr(lang, f"Past 28 days · through {latest_data_date:%Y-%m-%d}", f"過去28日間 · {latest_data_date:%Y-%m-%d}時点", f"최근 28일 · {latest_data_date:%Y-%m-%d} 기준")],
        label_visibility="collapsed",
        disabled=True,
    )

page_labels = {
    "overview": tr(lang, "Overview", "概要", "개요"),
    "forecast": tr(lang, "Demand Forecast", "需要予測", "수요예측"),
    "drivers": tr(lang, "Forecast Drivers", "予測要因", "예측 요인"),
    "inventory": tr(lang, "ROP & Safety Stock", "発注点・安全在庫", "발주점·안전재고"),
    "transfer": tr(lang, "Store Transfer", "店舗間移動", "매장 간 이동"),
    "policy": tr(lang, "Policy Evaluation", "政策比較", "정책 비교"),
    "agent": tr(lang, "AI Agent", "AIエージェント", "AI 에이전트"),
}
with st.sidebar:
    st.markdown(
        f'<div class="sidebar-brand">{tr(lang, "AI SCM Dashboard", "AI SCM ダッシュボード", "AI SCM 대시보드")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="sidebar-section">{tr(lang, "Analysis", "分析", "분석")}</div>', unsafe_allow_html=True)
    if st.session_state.get("workspace_page") not in page_labels:
        st.session_state["workspace_page"] = "overview"
    selected_page = st.session_state["workspace_page"]
    for page_id, page_label in page_labels.items():
        if st.button(
            page_label,
            key=f"nav_{page_id}",
            type="primary" if page_id == selected_page else "secondary",
            width="stretch",
        ):
            st.session_state["workspace_page"] = page_id
            st.rerun()
    st.markdown(f'<div class="sidebar-section">{tr(lang, "Data context", "データコンテキスト", "데이터 컨텍스트")}</div>', unsafe_allow_html=True)
    st.caption(
        f"{tr(lang, 'Updated', '更新', '업데이트')}: {latest_data_date:%Y-%m-%d}\n\n"
        f"{tr(lang, 'Coverage', '対象', '범위')}: {len(policy):,} SKU-store pairs\n\n"
        "Asia/Seoul"
    )

with st.container(key="copilot_rail"):
    st.markdown(
        f"""
        <div class="chat-panel">
          <div class="chat-header">
            <div class="chat-title">{tr(lang, 'SCM Decision Copilot', 'SCM意思決定コパイロット', 'SCM 의사결정 코파일럿')}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("top_scm_chat"):
        top_question = st.text_area(
            question_label,
            placeholder=question_placeholder,
            height=168,
        )
        top_submitted = st.form_submit_button(track_label)
    if top_submitted and top_question.strip():
        st.session_state["top_chat_reply"] = ask_scm_agent(top_question, lang)
        st.session_state["top_chat_reply_lang"] = lang
    if (
        st.session_state.get("top_chat_reply")
        and st.session_state.get("top_chat_reply_lang") == lang
    ):
        response_box(st.session_state["top_chat_reply"])
    st.caption(tr(lang, "Suggested questions", "おすすめの質問", "추천 질문"))
    copilot_prompts = [
        tr(lang, "Which SKU has the highest stockout risk?", "欠品リスクが最も高いSKUは？", "결품 위험이 가장 높은 SKU는?"),
        tr(lang, "Show recommended orders by city.", "推奨発注数を都市別に見せて。", "추천 발주량을 도시별로 보여줘."),
        tr(lang, "Where can store transfers help?", "店舗間移動で改善できる条件は？", "매장 간 이동으로 개선할 조건은?"),
    ]
    copilot_prompts = [
        tr(lang, "Which SKU has the highest stockout risk?", "欠品リスクが最も高いSKUは？", "결품 위험이 가장 높은 SKU는?"),
        tr(
            lang,
            "Compare the baseline and AI-assisted replenishment policies.",
            "ベースラインとAI支援発注ポリシーを比較して。",
            "기준 정책과 AI 지원 발주 정책을 비교해줘.",
        ),
        tr(lang, "Where can store transfers help?", "店舗間移動で改善できる条件は？", "매장 간 이동으로 개선할 조건은?"),
    ]
    for prompt_index, prompt in enumerate(copilot_prompts):
        if st.button(prompt, key=f"copilot_prompt_{prompt_index}", width="stretch"):
            st.session_state["top_chat_reply"] = ask_scm_agent(prompt, lang)
            st.session_state["top_chat_reply_lang"] = lang
            st.rerun()

components.html(
    """
    <script>
      const disableSpellcheck = () => {
        window.parent.document.querySelectorAll('textarea').forEach((element) => {
          element.setAttribute('spellcheck', 'false');
          element.setAttribute('autocomplete', 'off');
          element.setAttribute('autocorrect', 'off');
          element.setAttribute('autocapitalize', 'off');
        });
      };
      const preventIndexing = () => {
        const parentDocument = window.parent.document;
        let robots = parentDocument.head.querySelector('meta[name="robots"]');
        if (!robots) {
          robots = parentDocument.createElement('meta');
          robots.setAttribute('name', 'robots');
          parentDocument.head.appendChild(robots);
        }
        robots.setAttribute(
          'content',
          'noindex, nofollow, noarchive, nosnippet, noimageindex'
        );
      };
      disableSpellcheck();
      preventIndexing();
      new MutationObserver(disableSpellcheck).observe(
        window.parent.document.body,
        { childList: true, subtree: true }
      );
    </script>
    """,
    height=0,
)

view = policy.copy()
filtered_recs = recs.copy()
if city != "All":
    view = view[view["city"] == city]
    filtered_recs = filtered_recs[filtered_recs["city"] == city]
if status != "All":
    view = view[view["stock_status"] == status]
    filtered_recs = filtered_recs[filtered_recs["stock_status"] == status]

explanation_coverage = explanations["forecast_28d"].notna().mean() * 100
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(tr(lang, "SKU-store pairs", JP["pairs"], "SKU-매장 페어"), f"{len(view):,}")
col2.metric(tr(lang, "Stockout risks", JP["stockout"], "결품 리스크"), f"{(view['stock_status'] == 'Stockout Risk').sum():,}")
col3.metric(tr(lang, "Overstock cases", JP["overstock"], "과잉재고"), f"{(view['stock_status'] == 'Overstock').sum():,}")
col4.metric(tr(lang, "Recommended order units", JP["order_units"], "추천 발주 수량"), f"{int(filtered_recs['recommended_order_qty'].sum()):,}")
col5.metric(tr(lang, "Explanation coverage", "説明カバレッジ", "설명 커버리지"), f"{explanation_coverage:.0f}%")

st.caption(
    "ROP = average daily demand x lead time + safety stock.\n"
    "Safety stock = demand standard deviation x Z-value x sqrt(lead time)."
)

if selected_page == "overview":
    left, right = st.columns(2)
    with left:
        status_count = view.groupby("stock_status", as_index=False).size()
        status_count["stock_status"] = pd.Categorical(
            status_count["stock_status"],
            categories=["Healthy", "Stockout Risk", "Overstock"],
            ordered=True,
        )
        status_count = status_count.sort_values("stock_status")
        fig = px.bar(
            status_count,
            x="stock_status",
            y="size",
            color="stock_status",
            color_discrete_map=STATUS_COLORS,
            title=tr(lang, "Inventory Risk Distribution", JP["risk_dist"], "재고 리스크 분포"),
            labels={"stock_status": "", "size": tr(lang, "Pairs", "件数", "건수")},
        )
        fig.update_layout(showlegend=False, height=350, paper_bgcolor="white", plot_bgcolor="white", margin=dict(l=42, r=20, t=58, b=44))
        st.plotly_chart(fig, width="stretch")
    with right:
        city_count = view.groupby(["city", "stock_status"], as_index=False).size()
        fig = px.bar(
            city_count,
            x="city",
            y="size",
            color="stock_status",
            color_discrete_map=STATUS_COLORS,
            title=tr(lang, "Risk by City", JP["city_risk"], "도시별 리스크"),
            labels={"city": "", "size": tr(lang, "Pairs", "件数", "건수"), "stock_status": tr(lang, "Status", "在庫状態", "재고 상태")},
        )
        fig.update_layout(height=350, paper_bgcolor="white", plot_bgcolor="white", margin=dict(l=42, r=20, t=58, b=44))
        st.plotly_chart(fig, width="stretch")

    st.subheader(tr(lang, "Top Replenishment Recommendations", JP["top_replenishment"], "우선 보충 추천"))
    st.dataframe(
        filtered_recs[filtered_recs["recommended_order_qty"] > 0][
            [
                "store_id",
                "sku_id",
                "product_name",
                "priority",
                "stock_on_hand",
                "rop",
                "safety_stock",
                "forecast_28d",
                "recommended_order_qty",
                "reason",
            ]
        ].head(12),
        width="stretch",
        hide_index=True,
        column_config={
            "store_id": tr(lang, "Store", "店舗", "매장"),
            "sku_id": "SKU",
            "product_name": tr(lang, "Product", "商品", "상품"),
            "priority": tr(lang, "Priority", "優先度", "우선순위"),
            "stock_on_hand": tr(lang, "On hand", "現在庫", "현재고"),
            "rop": "ROP",
            "safety_stock": tr(lang, "Safety stock", "安全在庫", "안전재고"),
            "forecast_28d": tr(lang, "28-day forecast", "28日予測", "28일 예측"),
            "recommended_order_qty": tr(lang, "Recommended order", "推奨発注数", "추천 발주량"),
            "reason": tr(lang, "Decision rationale", "判断根拠", "판단 근거"),
        },
    )

elif selected_page == "forecast":
    product_options = sorted(forecast["product_name"].dropna().unique().tolist())
    selected_product = st.selectbox(tr(lang, "Product", JP["product"], "상품"), product_options)
    product_forecast = forecast[forecast["product_name"] == selected_product]
    fig = px.line(
        product_forecast,
        x="date",
        y="forecast_units",
        color="store_id",
        color_discrete_sequence=STORE_COLORS,
        title=f"{tr(lang, '28-Day Forecast', '28日需要予測', '28일 수요예측')}: {selected_product}",
    )
    fig.update_layout(height=420, paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")

    st.subheader(tr(lang, "Recent Sales Pattern", JP["recent_sales"], "최근 판매 패턴"))
    sku_id = products[products["product_name"] == selected_product]["sku_id"].iloc[0]
    recent_sales = sales[sales["sku_id"] == sku_id].merge(stores[["store_id", "city"]], on="store_id", how="left")
    fig = px.line(
        recent_sales.tail(5 * 60),
        x="date",
        y="units_sold",
        color="store_id",
        color_discrete_sequence=STORE_COLORS,
        title=tr(lang, "Historical Sales by Store", JP["sales_history"], "매장별 판매 이력"),
    )
    fig.update_layout(height=360, paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")

elif selected_page == "drivers":
    st.subheader(tr(lang, "Explainable Forecast Diagnostics", "説明可能な予測診断", "설명가능한 예측 진단"))
    st.caption(
        tr(
            lang,
            "Driver signals are calculated from committed sales history and reconcile operational context around the 28-day forecast. They are diagnostics, not SHAP attributions.",
            "要因シグナルは保存済み販売履歴から算出し、28日予測の業務コンテキストを説明します。SHAP値ではなく診断指標です。",
            "요인 신호는 저장된 판매 이력에서 계산해 28일 예측의 운영 맥락을 설명합니다. SHAP 값이 아닌 진단 지표입니다.",
        )
    )

    explanation_view = explanations.merge(
        view[["store_id", "sku_id", "stock_status"]],
        on=["store_id", "sku_id"],
        how="inner",
    )
    if explanation_view.empty:
        st.info(tr(lang, "No forecast diagnostics match the current filters.", "現在のフィルターに該当する予測診断はありません。", "현재 필터에 맞는 예측 진단이 없습니다."))
    else:
        coverage = explanation_view["forecast_28d"].notna().mean() * 100
        low_confidence = (explanation_view["confidence"] == "Low").sum()
        avg_gap = explanation_view["forecast_vs_baseline_pct"].mean()
        avg_promo = explanation_view["promotion_lift_pct"].mean()
        exp1, exp2, exp3, exp4 = st.columns(4)
        exp1.metric(tr(lang, "Explanation coverage", "説明カバレッジ", "설명 커버리지"), f"{coverage:.0f}%")
        exp2.metric(tr(lang, "Low-confidence pairs", "低信頼ペア", "낮은 신뢰도 페어"), f"{low_confidence:,}")
        exp3.metric(tr(lang, "Forecast vs recent baseline", "直近基準比", "최근 기준 대비 예측"), f"{avg_gap:+.1f}%")
        exp4.metric(tr(lang, "Observed promotion lift", "観測プロモーション効果", "관측 프로모션 상승"), f"{avg_promo:+.1f}%")

        selector_left, selector_right = st.columns(2)
        with selector_left:
            selected_driver_product = st.selectbox(
                tr(lang, "Product for local explanation", "ローカル説明対象商品", "개별 설명 상품"),
                sorted(explanation_view["product_name"].dropna().unique()),
                key="explanation_product",
            )
        eligible_stores = explanation_view.loc[
            explanation_view["product_name"] == selected_driver_product, "store_id"
        ].dropna().unique()
        with selector_right:
            selected_driver_store = st.selectbox(
                tr(lang, "Store", "店舗", "매장"),
                sorted(eligible_stores),
                key="explanation_store",
            )

        selected_explanation = explanation_view[
            (explanation_view["product_name"] == selected_driver_product)
            & (explanation_view["store_id"] == selected_driver_store)
        ].iloc[0]
        local1, local2, local3, local4 = st.columns(4)
        local1.metric(tr(lang, "28-day forecast", "28日予測", "28일 예측"), f"{selected_explanation['forecast_28d']:,.0f}")
        local2.metric(tr(lang, "Trailing baseline", "直近基準", "최근 기준"), f"{selected_explanation['baseline_28d']:,.0f}")
        local3.metric(tr(lang, "Forecast delta", "予測差分", "예측 차이"), f"{selected_explanation['forecast_vs_baseline_pct']:+.1f}%")
        local4.metric(tr(lang, "Signal confidence", "シグナル信頼度", "신호 신뢰도"), selected_explanation["confidence"])

        driver_chart = pd.DataFrame(
            {
                "driver": [
                    "Recent momentum",
                    "Promotion response",
                    "Weekend pattern",
                    "Holiday pattern",
                    "Temperature sensitivity",
                ],
                "signal_pct": [
                    selected_explanation["momentum_pct"],
                    selected_explanation["promotion_lift_pct"],
                    selected_explanation["weekend_lift_pct"],
                    selected_explanation["holiday_lift_pct"],
                    selected_explanation["temperature_signal_pct"],
                ],
            }
        ).sort_values("signal_pct")
        driver_chart["direction"] = driver_chart["signal_pct"].ge(0).map({True: "Positive", False: "Negative"})
        local_fig = px.bar(
            driver_chart,
            x="signal_pct",
            y="driver",
            color="direction",
            orientation="h",
            color_discrete_map={"Positive": RETAIL_RED, "Negative": INK_BLACK},
            title=tr(lang, "Observed demand-driver signals", "観測された需要要因シグナル", "관측 수요 요인 신호"),
            labels={"signal_pct": "Signal (%)", "driver": ""},
        )
        local_fig.add_vline(x=0, line_color="#8a8a8a", line_width=1)
        local_fig.update_layout(height=390, paper_bgcolor="white", plot_bgcolor="white", showlegend=False)

        strength = pd.DataFrame(
            {
                "driver": [
                    "Recent momentum",
                    "Promotion response",
                    "Weekend pattern",
                    "Holiday pattern",
                    "Temperature sensitivity",
                ],
                "mean_absolute_signal": [
                    explanation_view["momentum_pct"].abs().mean(),
                    explanation_view["promotion_lift_pct"].abs().mean(),
                    explanation_view["weekend_lift_pct"].abs().mean(),
                    explanation_view["holiday_lift_pct"].abs().mean(),
                    explanation_view["temperature_signal_pct"].abs().mean(),
                ],
            }
        ).sort_values("mean_absolute_signal")
        global_fig = px.bar(
            strength,
            x="mean_absolute_signal",
            y="driver",
            orientation="h",
            title=tr(lang, "Driver strength across filtered pairs", "フィルター対象ペアの要因強度", "필터 대상 페어의 요인 강도"),
            labels={"mean_absolute_signal": "Mean absolute signal (%)", "driver": ""},
        )
        global_fig.update_traces(marker_color=RETAIL_RED)
        global_fig.update_layout(height=390, paper_bgcolor="white", plot_bgcolor="white", showlegend=False)

        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.plotly_chart(local_fig, width="stretch")
        with chart_right:
            st.plotly_chart(global_fig, width="stretch")

        st.subheader(tr(lang, "Forecast exception queue", "予測例外キュー", "예측 예외 큐"))
        exception_queue = explanation_view[
            [
                "city",
                "store_id",
                "product_name",
                "category",
                "forecast_28d",
                "forecast_vs_baseline_pct",
                "volatility_pct",
                "confidence",
                "top_driver",
                "top_driver_signal_pct",
                "stock_status",
            ]
        ].copy()
        exception_queue["confidence_rank"] = exception_queue["confidence"].map({"Low": 0, "Medium": 1, "High": 2})
        exception_queue = exception_queue.sort_values(
            ["confidence_rank", "volatility_pct"], ascending=[True, False]
        ).drop(columns="confidence_rank")
        st.dataframe(
            exception_queue,
            width="stretch",
            hide_index=True,
        )

elif selected_page == "inventory":
    st.subheader(tr(lang, "SKU-store-level ROP Policy", JP["policy"], "SKU-매장별 ROP 정책"))
    st.dataframe(
        view[
            [
                "city",
                "store_id",
                "product_name",
                "category",
                "avg_daily_demand",
                "std_daily_demand",
                "lead_time_days",
                "service_level",
                "safety_stock",
                "rop",
                "stock_on_hand",
                "days_of_supply",
                "stock_status",
            ]
        ].sort_values(["stock_status", "days_of_supply"]),
        width="stretch",
        hide_index=True,
    )

elif selected_page == "transfer":
    st.subheader(tr(lang, "Store-to-store Transfer Recommendations", JP["transfer_rec"], "매장 간 재고 이동 추천"))
    if transfers.empty:
        st.info(tr(lang, "No transfer recommendation available in the current scenario.", JP["no_transfer"], "현재 시나리오에서는 매장 간 이동 추천이 없습니다."))
    else:
        st.dataframe(transfers, width="stretch", hide_index=True)

elif selected_page == "policy":
    st.subheader("Offline Policy Evaluation: SCM KPI Comparison")
    st.caption(
        "Baseline = planner-style replenishment policy. Candidate = constrained AI-assisted replenishment plus limited store-transfer policy. "
        "This is a synthetic offline policy comparison, not a randomized production experiment."
    )
    st.info(
        "Interpretation note: p-values only evaluate paired differences under this synthetic simulation. "
        "They do not prove real-world causal impact; production rollout would require backtesting, pilot stores, constraints, and sensitivity checks."
    )
    st.caption(
        "日本語: ベースライン在庫運用と、制約付きAI補充推奨・店舗間移動施策を比較する、"
        "合成デモデータに基づくオフライン政策評価シミュレーションです。"
    )

    control = policy_summary[policy_summary["group"].str.contains("Baseline")].iloc[0]
    treatment = policy_summary[policy_summary["group"].str.contains("Candidate")].iloc[0]
    cost_reduction_pct = float(treatment["cost_reduction_vs_control_pct"]) * 100
    cost_reduction_jpy = float(control["total_scm_cost_jpy"] - treatment["total_scm_cost_jpy"])
    stockout_reduction_pp = float(control["stockout_rate"] - treatment["stockout_rate"]) * 100
    service_level_uplift_pp = float(treatment["service_level"] - control["service_level"]) * 100
    lost_sales_reduction_jpy = float(control["lost_sales_proxy_jpy"] - treatment["lost_sales_proxy_jpy"])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total SCM cost proxy reduction", f"{cost_reduction_pct:.1f}%", f"-JPY {cost_reduction_jpy:,.0f}")
    kpi2.metric("Stockout-rate reduction", f"{stockout_reduction_pp:.1f} pp")
    kpi3.metric("Service-level uplift", f"{service_level_uplift_pp:.1f} pp")
    kpi4.metric("Lost-sales reduction", f"JPY {lost_sales_reduction_jpy:,.0f}")

    cost_fig = px.bar(
        policy_summary,
        x="group",
        y="total_scm_cost_jpy",
        color="group",
        color_discrete_sequence=[INK_BLACK, RETAIL_RED],
        title="Baseline vs Candidate: Total SCM Cost Proxy",
    )
    cost_fig.update_layout(showlegend=False, height=390, paper_bgcolor="white", plot_bgcolor="white")

    rate_long = policy_summary.melt(
        id_vars=["group"],
        value_vars=["stockout_rate", "service_level"],
        var_name="metric",
        value_name="rate",
    )
    rate_fig = px.bar(
        rate_long,
        x="metric",
        y="rate",
        color="group",
        barmode="group",
        color_discrete_sequence=[INK_BLACK, RETAIL_RED],
        title="Operational KPI Rate Comparison",
    )
    rate_fig.update_layout(height=390, paper_bgcolor="white", plot_bgcolor="white", yaxis_tickformat=".0%")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(cost_fig, width="stretch")
    with right:
        st.plotly_chart(rate_fig, width="stretch")

    st.subheader("Hypothesis Test and p-value")
    st.caption(
        "Methodology: paired t-test for continuous KPI deltas and McNemar exact test for paired stockout outcomes. "
        "H0 means the AI-assisted candidate policy does not improve the KPI versus the baseline policy."
    )
    st.caption(
        "日本語: SKU・店舗ペアを同一単位として比較し、連続値KPIは対応のあるt検定、"
        "欠品有無はMcNemar正確検定でp値を算出しています。"
    )
    st.dataframe(
        policy_tests[
            [
                "metric",
                "null_hypothesis",
                "test",
                "sample_size",
                "mean_improvement",
                "confidence_interval_95",
                "effect_size",
                "test_statistic",
                "p_value_display",
                "significance_0_05",
                "business_interpretation",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

    segment_cost = policy_segments.pivot_table(
        index=["city", "category"],
        columns="group",
        values="total_scm_cost_jpy",
        aggfunc="sum",
    ).reset_index()
    segment_cost["cost_reduction_jpy"] = (
        segment_cost["Baseline: planner policy"]
        - segment_cost["Candidate: constrained AI-assisted policy"]
    )
    segment_cost["cost_reduction_pct"] = (
        segment_cost["cost_reduction_jpy"] / segment_cost["Baseline: planner policy"].replace(0, pd.NA)
    )
    segment_cost = segment_cost.sort_values("cost_reduction_jpy", ascending=False)

    st.subheader("Where logistics should improve first")
    st.caption("改善優先領域: Cost-reduction drivers by city and product category.")
    driver_fig = px.bar(
        segment_cost.head(10),
        x="cost_reduction_jpy",
        y="city",
        color="category",
        orientation="h",
        title="Top Improvement Drivers by City and Category",
    )
    driver_fig.update_layout(height=440, paper_bgcolor="white", plot_bgcolor="white")
    st.plotly_chart(driver_fig, width="stretch")

    st.dataframe(
        segment_cost[["city", "category", "cost_reduction_jpy", "cost_reduction_pct"]].head(12),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Offline Policy Evaluation Detail Table")
    st.dataframe(
        policy_results[
            [
                "group",
                "city",
                "store_id",
                "product_name",
                "category",
                "forecast_28d",
                "order_qty",
                "inbound_transfer_qty",
                "outbound_transfer_qty",
                "service_level",
                "lost_sales_units",
                "ending_inventory_units",
                "total_scm_cost_jpy",
            ]
        ].sort_values(["group", "total_scm_cost_jpy"], ascending=[True, False]).head(30),
        width="stretch",
        hide_index=True,
    )

elif selected_page == "agent":
    st.subheader(tr(lang, "SCM Manager Agent", JP["manager"], "SCM 매니저 에이전트"))
    st.write("Ask about reorder actions, safety stock, stockout risk, or store-transfer recommendations.")
    question = st.text_input(
        tr(lang, "Question", JP["question"], "질문"),
        placeholder=question_placeholder,
    )
    if st.button(tr(lang, "Ask SCM Agent", JP["ask_agent"], "SCM Agent에게 질문"), type="primary") and question.strip():
        st.markdown(ask_scm_agent(question, lang).replace("\n", "  \n"))
