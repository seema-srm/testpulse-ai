# TestPulse AI Demo Script

**Suggested length:** 3-4 minutes
**Audience:** Instructor, classmates, or project reviewers
**Demo data:** Synthetic Jira- and Zephyr-style records only

## Before the Demo

- Start the dashboard with `streamlit run app.py`.
- Confirm the four teams appear and the portfolio scorecard is visible.
- To run AI analysis, configure `FIREWORKS_API_KEY` in Streamlit Secrets or the local environment.
- Open the scalable diagrams if useful:
  - [AI analysis demo flow](./ai-analysis-demo-flow.svg)
  - [Application architecture](./application-architecture.svg)
  - [Full architecture notes](./architecture-diagram.md)

## Spoken Introduction

> “TestPulse AI is a QA portfolio dashboard built with synthetic Jira- and Zephyr-style data. It compares four QA teams across six sprints, tracks test outcomes and defects, and can model status changes without rewriting its historical baseline. It also includes weekly status memory and Fireworks AI-assisted risk analysis.”

## Click-Through Demo

### 1. Executive Dashboard

**Action:** Open Executive Dashboard and point out the team comparison, six-sprint pass-rate trends, and Portfolio Scorecard.

> “This page gives a portfolio view across Team Alpha, Beta, Gamma, and Delta. The charts compare their current test pass rates and show the sprint history. The readiness score is a transparent 0-to-100 score: 40 points for having no open critical defects, 30 for having no active blockers, and up to 30 based on test pass rate against a 90 percent target. The score is a prioritization signal, not a claim that a team is prohibited from release.”

### 2. Team Details

**Action:** Open Team Details, select a team, and show its sprint metrics, defects, executions, and trend chart.

> “The team view lets us drill into one team's execution and defect history. We can see what contributes to the portfolio-level measures instead of treating the score as a black box.”

### 3. Weekly Status Report

**Action:** Open Weekly Status Report. If appropriate, generate or refresh the report, then point out team status, blockers, carryover history, and Markdown or Excel download buttons.

> “The weekly report stores synthetic snapshots in a local SQLite database. Later reports can compare against a prior week, and the carryover view can answer which issues have remained stuck across sprints. The report can be downloaded as Markdown or Excel.”

### 4. AI Risk Analysis

**Action:** Open AI Risk Analysis and select **Run Portfolio Analysis**. If the API key is not configured, point out the factual summary and configuration notice.

> “The AI page sends aggregate synthetic team and sprint metrics to Fireworks AI, not individual issue records. The factual portfolio summary is calculated by the application, not written by the model. Fireworks returns risk findings and suggested actions; the app checks that each finding refers to a known team and cites evidence belonging to that team. The API key is kept in Streamlit Secrets, and the model has no tools or write access.”

### 5. Simulation Center

**Action:** Open Simulation Center last. Show the status-change form and recent event history. If demonstrating a change, choose a synthetic record and narrate that the event is appended and then replayed.

> “The Simulation Center is a what-if feature. It appends the change to a local JSONL event log, then the dashboard replays it over copies of the historical records. The baseline CSVs are preserved, and current metrics update from the replay. On the hosted demo, added events can reset when the app restarts.”

## Architecture Walkthrough (Optional)

Use the [AI analysis demo flow](./ai-analysis-demo-flow.svg) to explain the AI sequence:

1. The app loads baseline synthetic data and replays local simulation events.
2. A user explicitly starts the analysis from the dashboard.
3. Python calculates current metrics and assembles aggregate facts with evidence IDs.
4. Fireworks AI returns structured findings; it does not run tools or edit records.
5. Host code validates team-specific evidence and computes the factual summary.
6. Streamlit displays the summary, findings, evidence, and human-review suggestions.

Use the [application architecture diagram](./application-architecture.svg) to point out the separation between Streamlit presentation, Python business logic, local storage, and the Fireworks AI service.

## Closing

> “The main design choices are synthetic-only data, separation of UI from business logic, replayable simulations that preserve historical baselines, persistent weekly memory, and a read-only AI workflow. The AI helps explain possible risks, while the metrics and final review stay with the application and the user.”

## Questions You May Be Asked

**Does it connect to a company's Jira or Zephyr?**
> “No. The project uses synthetic educational data and does not connect to company systems.”

**Can the AI change issue or test statuses?**
> “No. The model has no tools or write access. Simulation changes are explicit user actions handled by the application.”

**What data is sent to Fireworks AI?**
> “Only aggregate synthetic team and sprint metrics are sent for analysis. Individual issue and test records are excluded.”

**What does a readiness score of 100 mean?**
> “It means the team meets all three score criteria. It is a portfolio signal for discussion, not an automated release approval.”

**What is the limitation of the AI output?**
> “The numeric portfolio summary is computed deterministically, and findings must cite valid team evidence. The wording and recommendations are still generated by a language model and need human review.”
