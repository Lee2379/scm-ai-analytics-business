# Deployment, Privacy, and Operations

## Current deployment

- Platform: Streamlit Community Cloud
- App: `https://scm-ai-analytics-business.streamlit.app`
- Entry point: `app.py`
- Runtime: Python 3.12
- Data: synthetic CSV files committed with the application

## Privacy posture

- No customer, employee, payment, contact, or authentication data is included.
- No production identifiers are included.
- Real secret files are excluded by `.gitignore`.
- Example configuration contains placeholders only.
- The public deployment requires no external model credential and therefore uses deterministic local Copilot responses.
- A runtime `robots` directive requests `noindex`, `nofollow`, `noarchive`, `nosnippet`, and `noimageindex` for the controlled demonstration.

Search-engine directives are requests, not access controls. A production private deployment should use authentication and network-level restrictions.

## Secrets

Never commit `.env`, `.streamlit/secrets.toml`, service-account files, or deployment keys. Use the hosting platform's secret manager for optional integrations.

## Release checklist

1. compile `app.py` and `src/*.py`;
2. run unit and data-contract tests;
3. rebuild analytical outputs and review diffs;
4. verify English and Japanese interface states;
5. test reorder, transfer, and policy-comparison Copilot intents;
6. confirm no secret or personal-data patterns are tracked;
7. validate the live health endpoint and first-screen rendering.

## Production observability

Recommended operational telemetry:

- source freshness and row-count anomalies;
- missing SKU-store coverage;
- forecast WAPE, bias, and interval coverage;
- service level and stockout rate;
- planner override rate and reason;
- order and transfer acceptance rate;
- realized versus simulated savings;
- Copilot intent, latency, fallback rate, and numerical-faithfulness checks.
