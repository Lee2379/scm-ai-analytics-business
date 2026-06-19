# Contributing

Contributions should preserve the project's decision contracts: reproducible inputs, non-negative operational recommendations, traceable Copilot answers, and explicit separation between simulated and observed outcomes.

## Local quality check

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q app.py src
python -m pytest -q
streamlit run app.py
```

## Pull-request expectations

- Describe the business decision affected by the change.
- Add or update tests for analytical logic and data contracts.
- Document metric-definition or assumption changes.
- Do not commit secrets, production records, customer data, or personal identifiers.
- Label simulated results and avoid causal claims without an appropriate experiment.

