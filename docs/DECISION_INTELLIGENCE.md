# Decision Intelligence and Copilot

## From prediction to action

The product treats forecasting as an input to a decision system. A recommendation is considered complete only when it contains:

- the affected SKU and store;
- the relevant current state;
- the policy threshold or forecast used;
- a recommended action quantity;
- the operational reason;
- an explicit uncertainty or methodology limitation when relevant.

## Forecast diagnostics

Driver signals are computed from committed sales history:

- promotion response;
- weekend and holiday patterns;
- temperature sensitivity;
- recent momentum;
- forecast deviation from a trailing baseline;
- demand volatility.

They are diagnostic associations, not feature attribution from a fitted black-box model and not causal estimates. This distinction is stated in the product UI.

## Exception management

The forecast exception queue ranks low-confidence and high-volatility pairs first. This design supports analyst review where it has the greatest operational value rather than treating every forecast equally.

## Copilot intent routing

The local agent recognizes controlled intent families in English, Japanese, and Korean. Policy comparison is evaluated before reorder intent because policy questions often include words such as “replenishment” or “order.” This prevents a policy-evaluation request from incorrectly returning an operational reorder list.

| Intent | Reviewed source | Response contract |
|---|---|---|
| Reorder priority | recommendations + product/store dimensions | conclusion, top actions, decision logic, next step |
| Safety stock | inventory policy | highest requirements and policy inputs |
| Store transfer | transfer recommendations | source, destination, SKU, quantity |
| Policy comparison | KPI and segment summaries | metric comparison, drivers, limitations |

## LLM boundary

An optional Gemini path can transform the bounded SCM context into a concise narrative. The system prompt prohibits invented numbers and requests a fixed business response structure. If credentials are absent or the request fails, the deterministic local agent responds instead.

For enterprise use, add:

- prompt and response audit logs;
- schema validation on model output;
- role-aware data access;
- retrieval allowlists;
- evaluation sets for numerical faithfulness and action consistency;
- human approval before order or transfer execution.
