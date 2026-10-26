import pandas as pd
import pytest


@pytest.fixture
def isolated_generator_history(tmp_path, monkeypatch):
    from scripts import generate_data

    history = tmp_path / "historical"
    monkeypatch.setattr(generate_data, "HISTORY", history)
    return history


@pytest.fixture
def project_files(tmp_path):
    history = tmp_path / "historical"
    history.mkdir()
    tables = {
        "sprints.csv": [
            {
                "team_id": "alpha",
                "project_key": "QAA",
                "sprint_id": "QAA-SPR-01",
                "sprint_number": "1",
                "start_date": "2026-07-06",
                "end_date": "2026-07-19",
                "goal": "Synthetic sprint",
            }
        ],
        "jira_issues.csv": [
            {
                "issue_key": "QAA-1",
                "project_key": "QAA",
                "team_id": "alpha",
                "sprint_id": "QAA-SPR-01",
                "issue_type": "Bug",
                "priority": "Critical",
                "status": "Open",
                "created_date": "2026-07-06",
                "resolved_date": "",
                "blocked": "true",
                "summary": "Synthetic defect",
            }
        ],
        "zephyr_test_cases.csv": [
            {
                "test_id": "QAA-TC-001",
                "project_key": "QAA",
                "team_id": "alpha",
                "title": "Synthetic test",
            }
        ],
        "zephyr_cycles.csv": [
            {
                "cycle_id": "QAA-CYC-01",
                "project_key": "QAA",
                "sprint_id": "QAA-SPR-01",
                "name": "Regression",
            }
        ],
        "zephyr_executions.csv": [
            {
                "execution_id": "QAA-CYC-01-EX-001",
                "project_key": "QAA",
                "team_id": "alpha",
                "sprint_id": "QAA-SPR-01",
                "cycle_id": "QAA-CYC-01",
                "test_id": "QAA-TC-001",
                "status": "FAIL",
                "executed_at": "2026-07-19",
            }
        ],
        "snapshots.csv": [
            {
                "project_key": "QAA",
                "team_id": "alpha",
                "sprint_id": "QAA-SPR-01",
                "snapshot_date": "2026-07-19",
                "total_tests": "1",
                "passed": "0",
                "failed": "1",
                "blocked": "0",
                "not_executed": "0",
                "pass_rate": "0.0",
            }
        ],
        "dependencies.csv": [
            {
                "source_issue": "QAA-1",
                "affected_project": "QAA",
                "observed_sprint": "QAA-SPR-01",
                "dependency_type": "carryover",
            }
        ],
    }
    for filename, rows in tables.items():
        pd.DataFrame(rows).to_csv(history / filename, index=False)
    teams_config = tmp_path / "teams.yaml"
    teams_config.write_text(
        "teams:\n"
        "  - {id: alpha, name: Team Alpha, project_key: QAA, domain: Payments}\n"
        "  - {id: beta, name: Team Beta, project_key: QAB, domain: Checkout}\n",
        encoding="utf-8",
    )
    return history, teams_config
