# SCM Decision Copilot — Demonstration Questions and Answers

The public demo uses controlled intent routing over reviewed analytical tables. The following prompts were used for the deployment screenshots. Answers are generated from the repository's synthetic offline policy-evaluation outputs; they are not free-form claims or production results.

## English demonstration

### Question

> Compare the baseline and AI-assisted replenishment policies across stockout rate, service level, and total SCM cost. Explain the expected impact, key improvement drivers, and limitations.

### Answer

**Conclusion:** The AI-assisted candidate policy lowers simulated stockout exposure and total SCM cost while improving service level versus the planner baseline.

**KPI comparison**

- Stockout rate: **71.7% → 70.0%** (**-1.7 pp**)
- Service level: **92.9% → 94.9%** (**+2.0 pp**)
- Total SCM cost proxy: **¥11,351,887 → ¥8,493,779** (**25.2% reduction; ¥2,858,107**)

**Top improvement drivers**

- Tokyo / Outerwear: estimated cost reduction **¥465,264**
- Yokohama / Shirts: estimated cost reduction **¥414,250**
- Fukuoka / Outerwear: estimated cost reduction **¥342,790**

**Limitations**

- This is a synthetic offline simulation across 60 SKU-store pairs.
- It is not a randomized production experiment; the result is scenario evidence, not causal impact.
- Ordering, holding, stockout, and transfer-cost assumptions require sensitivity testing before production use.
- The paired stockout-state test is not significant at the 0.05 level in the current sample.

## Japanese demonstration

### 質問

> ベースラインとAI支援型の発注ポリシーを、欠品率・サービスレベル・総SCMコストで比較し、期待される効果、主な改善要因、分析上の限界を説明してください。

### 回答

**結論：** AI支援型の候補ポリシーは、プランナーのベースラインと比較して、シミュレーション上の欠品リスクと総SCMコストを低減しながら、サービスレベルを改善しました。

**主要KPIの比較**

- 欠品率：**71.7% → 70.0%**（**-1.7ポイント**）
- サービスレベル：**92.9% → 94.9%**（**+2.0ポイント**）
- 総SCMコスト指標：**¥11,351,887 → ¥8,493,779**（**25.2%削減、¥2,858,107**）

**主な改善要因**

- Tokyo / Outerwear：推定コスト削減 **¥465,264**
- Yokohama / Shirts：推定コスト削減 **¥414,250**
- Fukuoka / Outerwear：推定コスト削減 **¥342,790**

**分析上の限界**

- 対象は60件のSKU・店舗ペアを用いた合成オフラインシミュレーションです。
- ランダム化された本番実験ではないため、因果効果としては解釈できません。
- 発注・保管・欠品・店舗間移動のコスト仮定について、本番導入前に感度分析が必要です。
- 現在のサンプルでは、欠品状態の対応あり検定は5%水準で有意ではありません。

## Operational prioritization example

### Question

> Rank the SKUs with the highest stockout risk. For each SKU, show current inventory, reorder point, 28-day demand forecast, recommended order quantity, and the decision rationale.

### Answer structure

The Copilot returns:

1. a one-sentence prioritization conclusion;
2. the top three SKU-store actions with stock, ROP, forecast, and order quantity;
3. the policy formula used for the decision;
4. the next action—replenishment or a feasible store-transfer check.

The ranked values are read directly from `recommendations.csv`, ensuring that the narrative and the dashboard action table use the same decision contract.

## Grounding boundary

- The local public-demo path reads only prepared SCM tables.
- The model does not execute orders, mutate inventory, or access production systems.
- Optional Gemini integration is isolated behind deployment secrets and a supplied-context-only instruction.
- When no external key is configured, the same answer structure is produced deterministically by local code.

