# Security and Privacy

## Supported version

Security and privacy fixes target the latest commit on `main`.

## Reporting

Do not open a public issue containing credentials, tokens, personal information, or exploitable details. Use GitHub's private vulnerability reporting feature when it is enabled for the repository.

## Data and credential policy

- The versioned datasets are synthetic and contain no customer-level records.
- Direct personal identifier columns are rejected by automated data-contract tests.
- Optional model keys must be supplied through environment variables or deployment secrets.
- `.env` and Streamlit secret files are excluded from version control.
- The public demo uses a deterministic local Copilot fallback when no external model key is configured.

See [Deployment and Privacy](docs/DEPLOYMENT_AND_PRIVACY.md) for the full threat model and deployment boundary.

