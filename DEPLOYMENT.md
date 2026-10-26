# Deploy TestPulse AI on Streamlit Community Cloud

This project is configured for a public Streamlit Community Cloud demo. The app uses synthetic data only. Fireworks AI can generate risk findings in the hosted app when its API key is configured in Streamlit Secrets. Only aggregate synthetic team and sprint metrics are sent to Fireworks.

## Prepare the GitHub repository

1. Create a **public** repository under your GitHub account, for example `testpulse-ai`.
2. Upload the complete project folder, including `app.py`, `scripts/`, `config/`, `data/historical/`, `data/simulations/events.jsonl`, `.streamlit/config.toml`, and `deployment/secrets.example.toml`.
3. Do not upload `.env`, `.streamlit/secrets.toml`, `.venv/`, `__pycache__/`, or `.pytest_cache/`.
4. The included `data/simulations/events.jsonl` contains synthetic demo events that give Team Beta its release-readiness scenario. Streamlit Cloud may discard additional simulation events after the app restarts.

## Deploy the app

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io) with the GitHub account that owns the repository.
2. Select **Create app**, choose the `testpulse-ai` repository, the `main` branch, and `app.py`.
3. In **Advanced settings**, select Python 3.12.
4. In **Advanced settings → Secrets**, replace the old `enable_local_ai` setting with this configuration, using your Fireworks API key:
   ```toml
   FIREWORKS_API_KEY = "your-fireworks-api-key"

   [testpulse]
   enable_fireworks_ai = true
   ```
   Enter the real key directly in Streamlit Secrets. Do not commit it to the repository or share it in chat. If the key is not configured, the hosted app displays the deterministic portfolio summary and a configuration notice.
5. Deploy, wait for the health status to become available, and copy the assigned `*.streamlit.app` URL for the instructor.
6. Test that URL in a private/incognito browser window. Verify the dashboard, Team Beta score, report export, and AI analysis page.

## Hosted behavior and limitations

- Team and sprint data is synthetic and read from the repository.
- The checked-in event log supplies the initial demo state. User-created simulation events and weekly SQLite memory are ephemeral on Community Cloud and may reset when the app sleeps, restarts, or is redeployed.
- The AI page calls Fireworks only when explicitly triggered. It sends aggregate synthetic metrics, not issue-level records, to the external Fireworks API.
- Keep model API keys in local environment variables or Streamlit Secrets. Never commit keys to this repository or share them in chat.

Official guides:

- [Deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Manage deployment secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
