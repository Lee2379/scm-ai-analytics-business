from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


GEMINI_MODEL = "gemini-3.5-flash"


def load_agent_tables(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    tables = {
        "policy": pd.read_csv(data_dir / "inventory_policy.csv"),
        "recommendations": pd.read_csv(data_dir / "recommendations.csv"),
        "transfers": pd.read_csv(data_dir / "transfer_recommendations.csv"),
        "products": pd.read_csv(data_dir / "products.csv"),
        "stores": pd.read_csv(data_dir / "stores.csv"),
    }
    policy_summary = data_dir / "policy_eval_kpi_summary.csv"
    policy_segments = data_dir / "policy_eval_segment_summary.csv"
    if policy_summary.exists():
        tables["policy_summary"] = pd.read_csv(policy_summary)
    if policy_segments.exists():
        tables["policy_segments"] = pd.read_csv(policy_segments)
    return tables


def gemini_ready() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def build_scm_context(tables: dict[str, pd.DataFrame]) -> str:
    policy = tables["policy"]
    recs = tables["recommendations"]
    transfers = tables["transfers"]
    products = tables["products"]
    stores = tables["stores"]

    product_names = products.set_index("sku_id")["product_name"].to_dict()
    store_cities = stores.set_index("store_id")["city"].to_dict()

    top_reorders = recs[recs["recommended_order_qty"] > 0].sort_values(
        ["priority", "risk_score"], ascending=[True, False]
    ).head(8)
    top_risks = policy[policy["stock_status"] == "Stockout Risk"].sort_values("days_of_supply").head(8)
    top_safety = policy.sort_values("safety_stock", ascending=False).head(6)
    top_transfers = transfers.head(6)

    lines = [
        "SCM LIVE DATA SNAPSHOT",
        f"- SKU-store pairs monitored: {len(policy)}",
        f"- Stockout risks: {int((policy['stock_status'] == 'Stockout Risk').sum())}",
        f"- Overstock cases: {int((policy['stock_status'] == 'Overstock').sum())}",
        f"- Total recommended order units: {int(recs['recommended_order_qty'].sum())}",
        f"- Store-transfer recommendations: {len(transfers)}",
        "",
        "INVENTORY POLICY FORMULAS",
        "- ROP = average daily demand x lead time + safety stock.",
        "- Safety stock = demand standard deviation x Z-value x sqrt(lead time).",
        "",
        "TOP REORDER ACTIONS",
    ]

    if top_reorders.empty:
        lines.append("- No immediate reorder action is required.")
    for _, row in top_reorders.iterrows():
        lines.append(
            "- "
            f"{row.store_id} ({store_cities.get(row.store_id, '')}) / "
            f"{product_names.get(row.sku_id, row.sku_id)}: "
            f"priority={row.priority}, stock={row.stock_on_hand:.0f}, ROP={row.rop:.0f}, "
            f"safety_stock={row.safety_stock:.0f}, forecast_28d={row.forecast_28d:.0f}, "
            f"recommended_order_qty={int(row.recommended_order_qty)}."
        )

    lines.extend(["", "HIGHEST STOCKOUT RISKS"])
    if top_risks.empty:
        lines.append("- No current stockout risk.")
    for _, row in top_risks.iterrows():
        lines.append(
            "- "
            f"{row.store_id} ({store_cities.get(row.store_id, '')}) / "
            f"{product_names.get(row.sku_id, row.sku_id)}: "
            f"days_of_supply={row.days_of_supply:.1f}, stock={row.stock_on_hand:.0f}, "
            f"ROP={row.rop:.0f}, lead_time_days={row.lead_time_days:.0f}."
        )

    lines.extend(["", "HIGHEST SAFETY STOCK REQUIREMENTS"])
    for _, row in top_safety.iterrows():
        lines.append(
            "- "
            f"{row.store_id} / {product_names.get(row.sku_id, row.sku_id)}: "
            f"safety_stock={row.safety_stock:.0f}, service_level={row.service_level:.0%}, "
            f"std_daily_demand={row.std_daily_demand:.1f}."
        )

    lines.extend(["", "STORE TRANSFER RECOMMENDATIONS"])
    if top_transfers.empty:
        lines.append("- No current store transfer recommendation.")
    for _, row in top_transfers.iterrows():
        lines.append(
            "- "
            f"{row.from_store} ({row.from_city}) -> {row.to_store} ({row.to_city}): "
            f"{int(row.transfer_qty)} units of {row.product_name}."
        )

    if "policy_summary" in tables:
        policy_summary = tables["policy_summary"]
        control = policy_summary[policy_summary["group"].str.contains("Baseline")].iloc[0]
        treatment = policy_summary[policy_summary["group"].str.contains("Candidate")].iloc[0]
        lines.extend(
            [
                "",
                "OFFLINE POLICY EVALUATION",
                f"- Baseline stockout rate: {control.stockout_rate:.1%}",
                f"- Candidate-policy stockout rate: {treatment.stockout_rate:.1%}",
                f"- Baseline service level: {control.service_level:.1%}",
                f"- Candidate-policy service level: {treatment.service_level:.1%}",
                f"- Total SCM cost proxy reduction: {treatment.cost_reduction_vs_control_pct:.1%}",
            ]
        )

    if "policy_segments" in tables:
        segments = tables["policy_segments"]
        pivot = segments.pivot_table(
            index=["city", "category"],
            columns="group",
            values="total_scm_cost_jpy",
            aggfunc="sum",
        ).reset_index()
        required = {
            "Baseline: planner policy",
            "Candidate: constrained AI-assisted policy",
        }
        if required.issubset(pivot.columns):
            pivot["cost_reduction_jpy"] = (
                pivot["Baseline: planner policy"]
                - pivot["Candidate: constrained AI-assisted policy"]
            )
            top_driver = pivot.sort_values("cost_reduction_jpy", ascending=False).head(3)
            lines.extend(["", "TOP OFFLINE POLICY IMPROVEMENT DRIVERS"])
            for _, row in top_driver.iterrows():
                lines.append(
                    f"- {row.city} / {row.category}: "
                    f"estimated cost reduction JPY {row.cost_reduction_jpy:,.0f}."
                )

    return "\n".join(lines)


def local_agent_reply(question: str, tables: dict[str, pd.DataFrame], lang: str = "ja") -> str:
    q = question.lower()
    context = build_scm_context(tables)
    reorder_terms = [
        "rop",
        "sku",
        "reorder",
        "order",
        "replenish",
        "priority",
        "prioritize",
        "\u518d\u767a\u6ce8",
        "\u767a\u6ce8",
        "\u88dc\u5145",
        "\u512a\u5148",
        "\uc7ac\uc8fc\ubb38",
        "\ubc1c\uc8fc",
        "\uc6b0\uc120",
    ]
    policy_terms = [
        "a/b",
        "ab test",
        "policy",
        "policies",
        "baseline",
        "candidate",
        "compare",
        "comparison",
        "impact",
        "effect",
        "improve",
        "service level",
        "scm cost",
        "\u30dd\u30ea\u30b7\u30fc",
        "\u65b9\u91dd",
        "\u30d9\u30fc\u30b9\u30e9\u30a4\u30f3",
        "\u6bd4\u8f03",
        "\u52b9\u679c",
        "\u6539\u5584",
        "\uc815\ucc45",
        "\ubca0\uc774\uc2a4\ub77c\uc778",
        "\ube44\uad50",
        "\ud6a8\uacfc",
        "\uac1c\uc120",
    ]
    # Policy questions often contain words such as "replenishment" or "order".
    # Classify them before reorder questions so a comparison request cannot fall
    # through to the operational reorder response.
    if any(k in q for k in policy_terms):
        return _format_policy_answer(tables, lang)
    if any(k in q for k in ["safety", "safety stock", "\u5b89\u5168\u5728\u5eab", "\uc548\uc804\uc7ac\uace0"]):
        return _reply(_section(context, "HIGHEST SAFETY STOCK REQUIREMENTS"))
    if any(k in q for k in ["transfer", "store", "\u5e97\u8217\u9593\u79fb\u52d5", "\u5728\u5eab\u79fb\u52d5", "\ub9e4\uc7a5 \uac04 \uc774\ub3d9", "\uc7ac\uace0 \uc774\ub3d9"]):
        return _reply(_section(context, "STORE TRANSFER RECOMMENDATIONS"))
    if any(k in q for k in reorder_terms):
        return _format_reorder_answer(tables, lang)
    if any(k in q for k in ["risk", "stockout"]):
        return _reply(_section(context, "HIGHEST STOCKOUT RISKS"))
    return _reply(_section(context, "SCM LIVE DATA SNAPSHOT"))


def gemini_reply_if_configured(question: str, context: str, lang: str = "ja") -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    language = {"ja": "Japanese", "en": "English", "ko": "Korean"}.get(lang, "Japanese")
    system_instruction = (
        "You are a cutting-edge SCM AI Agent for the AI SCM Data Analysis Project. "
        "You track live SCM dashboard data and answer as a business-ready supply chain analyst. "
        "Use only the supplied context. Do not invent numbers. "
        "When answering reorder-priority questions, do NOT dump the raw data. "
        "Structure the answer as: 1) one-sentence conclusion, 2) top 3 priority SKU-store actions, "
        "3) decision logic, 4) recommended next action. "
        "When answering offline policy evaluation or impact questions, explain that the results are synthetic simulated policy comparisons, "
        "then cover stockout rate, service level, total SCM cost proxy, and the top city/category improvement drivers. "
        "Use short bullets and explain stock, ROP, forecast demand, and order quantity in plain language. "
        "Keep answers concise, executive-friendly, readable, and specific."
    )
    prompt = (
        f"Preferred response language: {language}\n\n"
        f"{context}\n\n"
        f"User question:\n{question}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.25,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )
        return response.text
    except Exception as exc:
        return f"Gemini connection failed. Showing local SCM context fallback.\n\n{context}\n\nError: {exc}"


def _section(context: str, start_title: str) -> str:
    lines = context.splitlines()
    try:
        start = lines.index(start_title)
    except ValueError:
        return context
    collected = []
    for line in lines[start:]:
        if collected and line.isupper() and not line.startswith("-"):
            break
        collected.append(line)
    return "\n".join(collected)


def _reply(text: str) -> str:
    return text


def _format_policy_answer(tables: dict[str, pd.DataFrame], lang: str) -> str:
    summary = tables.get("policy_summary")
    if summary is None or summary.empty:
        return _reply("Policy evaluation data is not available.")

    baseline = summary[summary["group"].str.contains("Baseline")].iloc[0]
    candidate = summary[summary["group"].str.contains("Candidate")].iloc[0]
    stockout_delta_pp = (candidate.stockout_rate - baseline.stockout_rate) * 100
    service_delta_pp = (candidate.service_level - baseline.service_level) * 100
    cost_reduction = baseline.total_scm_cost_jpy - candidate.total_scm_cost_jpy
    cost_reduction_pct = cost_reduction / baseline.total_scm_cost_jpy

    drivers: list[tuple[str, str, float]] = []
    segments = tables.get("policy_segments")
    if segments is not None and not segments.empty:
        pivot = segments.pivot_table(
            index=["city", "category"],
            columns="group",
            values="total_scm_cost_jpy",
            aggfunc="sum",
        ).reset_index()
        baseline_col = "Baseline: planner policy"
        candidate_col = "Candidate: constrained AI-assisted policy"
        if {baseline_col, candidate_col}.issubset(pivot.columns):
            pivot["cost_reduction_jpy"] = pivot[baseline_col] - pivot[candidate_col]
            for _, row in pivot.sort_values("cost_reduction_jpy", ascending=False).head(3).iterrows():
                drivers.append((str(row.city), str(row.category), float(row.cost_reduction_jpy)))

    if lang == "ja":
        lines = [
            "結論：AI支援候補ポリシーは、ベースラインに対して欠品率と総SCMコストを低減し、サービスレベルを改善しました。",
            "",
            "主要KPI比較",
            f"- 欠品率：{baseline.stockout_rate:.1%} → {candidate.stockout_rate:.1%}（{stockout_delta_pp:+.1f}ポイント）",
            f"- サービスレベル：{baseline.service_level:.1%} → {candidate.service_level:.1%}（{service_delta_pp:+.1f}ポイント）",
            f"- 総SCMコスト：¥{baseline.total_scm_cost_jpy:,.0f} → ¥{candidate.total_scm_cost_jpy:,.0f}（{cost_reduction_pct:.1%}削減、¥{cost_reduction:,.0f}）",
        ]
        if drivers:
            lines.extend(["", "主な改善ドライバー"])
            lines.extend(f"- {city} / {category}：推定コスト削減 ¥{value:,.0f}" for city, category, value in drivers)
        lines.extend(
            [
                "",
                "解釈上の注意",
                f"- 対象は{int(baseline.experimental_units)}件のSKU・店舗ペアによる合成オフラインシミュレーションです。",
                "- ランダム化された本番実験ではないため、因果効果としては解釈できません。",
                "- 発注・保管・欠品・店舗間移動のコスト仮定が変わる場合は、感度分析が必要です。",
            ]
        )
        return _reply("\n".join(lines))

    if lang == "ko":
        lines = [
            "결론: AI 지원 후보 정책은 기준 정책보다 결품률과 총 SCM 비용을 낮추고 서비스 수준을 개선했습니다.",
            "",
            "핵심 KPI 비교",
            f"- 결품률: {baseline.stockout_rate:.1%} → {candidate.stockout_rate:.1%} ({stockout_delta_pp:+.1f}%p)",
            f"- 서비스 수준: {baseline.service_level:.1%} → {candidate.service_level:.1%} ({service_delta_pp:+.1f}%p)",
            f"- 총 SCM 비용: ¥{baseline.total_scm_cost_jpy:,.0f} → ¥{candidate.total_scm_cost_jpy:,.0f} ({cost_reduction_pct:.1%} 절감, ¥{cost_reduction:,.0f})",
        ]
        if drivers:
            lines.extend(["", "주요 개선 요인"])
            lines.extend(f"- {city} / {category}: 추정 비용 절감 ¥{value:,.0f}" for city, category, value in drivers)
        lines.extend(
            [
                "",
                "해석상 한계",
                f"- {int(baseline.experimental_units)}개 SKU-매장 페어를 사용한 합성 오프라인 시뮬레이션입니다.",
                "- 무작위 운영 실험이 아니므로 인과 효과로 해석할 수 없습니다.",
                "- 발주·보관·결품·매장 이동 비용 가정에 대한 민감도 분석이 필요합니다.",
            ]
        )
        return _reply("\n".join(lines))

    lines = [
        "Conclusion: the AI-assisted candidate policy lowers stockout exposure and total SCM cost while improving service level versus the baseline.",
        "",
        "KPI comparison",
        f"- Stockout rate: {baseline.stockout_rate:.1%} → {candidate.stockout_rate:.1%} ({stockout_delta_pp:+.1f} pp)",
        f"- Service level: {baseline.service_level:.1%} → {candidate.service_level:.1%} ({service_delta_pp:+.1f} pp)",
        f"- Total SCM cost: ¥{baseline.total_scm_cost_jpy:,.0f} → ¥{candidate.total_scm_cost_jpy:,.0f} ({cost_reduction_pct:.1%} reduction, ¥{cost_reduction:,.0f})",
    ]
    if drivers:
        lines.extend(["", "Top improvement drivers"])
        lines.extend(f"- {city} / {category}: estimated cost reduction ¥{value:,.0f}" for city, category, value in drivers)
    lines.extend(
        [
            "",
            "Limitations",
            f"- This is a synthetic offline simulation across {int(baseline.experimental_units)} SKU-store pairs.",
            "- It is not a randomized production experiment, so the results should not be interpreted as causal impact.",
            "- Cost assumptions for ordering, holding, stockouts, and transfers require sensitivity testing before deployment.",
        ]
    )
    return _reply("\n".join(lines))


def _format_reorder_answer(tables: dict[str, pd.DataFrame], lang: str) -> str:
    recs = tables["recommendations"]
    products = tables["products"]
    stores = tables["stores"]
    product_names = products.set_index("sku_id")["product_name"].to_dict()
    store_cities = stores.set_index("store_id")["city"].to_dict()
    top = recs[recs["recommended_order_qty"] > 0].sort_values(
        ["priority", "risk_score"], ascending=[True, False]
    ).head(3)

    if top.empty:
        return _reply("No urgent reorder is required. Current inventory is above ROP for the monitored SKU-store pairs.")

    if lang == "ja":
        lines = [
            "結論: 優先的に再発注すべきSKUは、在庫がROPを大きく下回り、28日需要予測に対して補充不足が大きいものです。",
            "",
            "優先再発注リスト",
        ]
        for i, (_, row) in enumerate(top.iterrows(), 1):
            product = product_names.get(row.sku_id, row.sku_id)
            city = store_cities.get(row.store_id, "")
            lines.append(
                f"{i}. {product} / {row.store_id} ({city})\n"
                f"   - 推奨発注数: {int(row.recommended_order_qty)} units\n"
                f"   - 現在在庫: {row.stock_on_hand:.0f}, ROP: {row.rop:.0f}, 28日需要予測: {row.forecast_28d:.0f}"
            )
        lines.extend(
            [
                "",
                "判断ロジック",
                "- 現在在庫がROPを下回るSKUを優先します。",
                "- ROPは「日平均需要 x リードタイム + 安全在庫」で計算します。",
                "- 推奨発注数は、28日需要予測と安全在庫を満たすために不足している数量です。",
                "",
                "次のアクション: 上位3SKUは欠品リスクが高いため、まず発注処理または近隣店舗からの在庫移動を検討してください。",
            ]
        )
        return _reply("\n".join(lines))

    lines = [
        "Conclusion: reorder priority should go to SKU-store pairs where current stock is far below ROP and the 28-day demand forecast is not covered.",
        "",
        "Top reorder priorities",
    ]
    for i, (_, row) in enumerate(top.iterrows(), 1):
        product = product_names.get(row.sku_id, row.sku_id)
        city = store_cities.get(row.store_id, "")
        lines.append(
            f"{i}. {product} / {row.store_id} ({city})\n"
            f"   - Recommended order: {int(row.recommended_order_qty)} units\n"
            f"   - Current stock: {row.stock_on_hand:.0f}, ROP: {row.rop:.0f}, 28-day forecast: {row.forecast_28d:.0f}"
        )
    lines.extend(
        [
            "",
            "Decision logic",
            "- Prioritize SKUs where current stock is below ROP.",
            "- ROP is calculated as average daily demand x lead time + safety stock.",
            "- Order quantity covers the 28-day forecast plus safety stock gap.",
            "",
            "Next action: execute replenishment for the top 3 items first, or check store-transfer options if overstock exists nearby.",
        ]
    )
    return _reply("\n".join(lines))
