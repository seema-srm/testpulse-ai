# TestPulse AI
Synthetic Jira- and Zephyr Squad-style QA data and an interactive dashboard for four teams across sprints.

Run `python scripts/generate_data.py generate --seed 42` to create a reproducible baseline.
Run `python scripts/generate_data.py simulate --issue QAB-900 --status Done --note "Fix verified"` to append an event without modifying baseline CSVs.
Run `python -m pip install -r requirements.txt` to install dependencies.
Run `streamlit run app.py` to launch the dashboard.
Run `python -m pytest -q` for validation.

To publish a shareable instructor demo, follow [DEPLOYMENT.md](./DEPLOYMENT.md) for Streamlit Community Cloud setup.

The dashboard uses the full historical dataset. The Executive Dashboard compares all four teams. Team Details includes sprint metrics, defects, execution outcomes, and Sprint Pass Rate Trends. The Simulation Center appends defect or execution changes to `data/simulations/events.jsonl`. Recent changes show the previous and new statuses, and the app replays events to recalculate current metrics while keeping historical CSVs and snapshots unchanged.

The Executive Dashboard Portfolio Scorecard includes a 0–100 Release Readiness Score: 40 points for no open critical defects, 30 points for no active blockers (blocked issues that are not Done), and up to 30 points for test pass rate, scaled to the 90% target.

The AI Risk Analysis page uses a local Ollama model to identify portfolio risks from aggregate synthetic metrics. Its portfolio summary is calculated deterministically from current metrics; the model produces evidence-grounded team findings and recommendations. Install [Ollama](https://ollama.com/download), start the local service, and pull the default model with `ollama pull llama3.1:8b`. Override the model with `TESTPULSE_OLLAMA_MODEL`; the endpoint can be set with `TESTPULSE_OLLAMA_URL` but must be a local loopback URL. Run the analysis explicitly from the page. The workflow has no tools or write access, excludes individual issue details, validates its structured findings and evidence references, and presents recommendations for human review only. Unit tests use a fake model and do not require Ollama.

The Weekly Status Report page saves synthetic team status snapshots in the local `data/status_memory.sqlite3` database. Generate one report per week to retain week-over-week memory; refreshing the same week updates that week's record. Later reports compare pass rate, completion, defects, and test outcomes against the previous saved report. Reports include deterministic team risk flags, active blockers, and multi-sprint carryover history, including items that have since been resolved, to answer "What has been stuck for more than one sprint?" Download the report as Markdown or as a formatted Excel workbook with separate team status, blocker, carryover, and (when available) week-over-week sheets. The local memory database is ignored by Git and does not modify historical CSVs.

All names and records are synthetic. The project does not connect to Jira or Zephyr. These are normalized educational CSVs, not official Zephyr Squad API response payloads.
