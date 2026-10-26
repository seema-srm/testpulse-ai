# Deploy TestPulse AI on Streamlit Community Cloud

This project is configured for a public Streamlit Community Cloud demo. The app uses synthetic data only. Its AI analysis remains local-only and is disabled in the hosted version; run the app locally with Ollama to use AI-generated findings.

## Prepare the GitHub repository

1. Create a **public** repository under your GitHub account, for example `testpulse-ai`.
2. Upload the complete project folder, including `app.py`, `scripts/`, `config/`, `data/historical/`, `data/simulations/events.jsonl`, `.streamlit/config.toml`, and `deployment/secrets.example.toml`.
3. Do not upload `.env`, `.streamlit/secrets.toml`, `.venv/`, `__pycache__/`, or `.pytest_cache/`.
4. The included `data/simulations/events.jsonl` contains synthetic demo events that give Team Beta its release-readiness scenario. Streamlit Cloud may discard additional simulation events after the app restarts.

## Deploy the app

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io) with the GitHub account that owns the repository.
2. Select **Create app**, choose the `testpulse-ai` repository, the `main` branch, and `app.py`.
3. In **Advanced settings**, select Python 3.12.
4. In the **Secrets** field, paste the contents of `deployment/secrets.example.toml`. This disables the local Ollama call in the hosted app and displays the deterministic portfolio summary with an explanation. If no secrets are configured, the app defaults to local AI being enabled, which will not work on Community Cloud.
5. Deploy, wait for the health status to become available, and copy the assigned `*.streamlit.app` URL for the instructor.
6. Test that URL in a private/incognito browser window. Verify the dashboard, Team Beta score, report export, and hosted AI limitation message.

## Hosted behavior and limitations

- Team and sprint data is synthetic and read from the repository.
- The checked-in event log supplies the initial demo state. User-created simulation events and weekly SQLite memory are ephemeral on Community Cloud and may reset when the app sleeps, restarts, or is redeployed.
- The AI page displays the factual summary but does not call Ollama in the hosted configuration. Local analysis remains available when running the app on a computer with Ollama installed.
- Do not paste passwords, GitHub tokens, or model API keys into this repository or the Streamlit Secrets example. No hosted model API key is needed for this deployment.

Official guides:

- [Deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Manage deployment secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
