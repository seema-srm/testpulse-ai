import json

import pandas as pd
import pytest

from scripts.dashboard_data import (
    build_sprint_metrics,
    build_team_metrics,
    load_dashboard_data,
    replay_simulation_events,
)


def test_replays_legacy_and_new_events_without_mutating_baseline():
    issues = pd.DataFrame(
        [{"issue_key": "QAA-1", "status": "Open", "resolved_date": ""}]
    )
    executions = pd.DataFrame(
        [{"execution_id": "EX-1", "status": "FAIL", "executed_at": "2026-01-01"}]
    )
    current_issues, current_executions = replay_simulation_events(
        issues,
        executions,
        [
            {
                "event_id": 1,
                "issue_key": "QAA-1",
                "previous_baseline_status": "Open",
                "new_status": "Done",
                "event_date": "2026-10-23",
            },
            {
                "event_id": 2,
                "target_type": "execution",
                "target_id": "EX-1",
                "previous_status": "FAIL",
                "new_status": "PASS",
                "event_date": "2026-10-24",
            },
        ],
    )

    assert current_issues.iloc[0]["status"] == "Done"
    assert current_issues.iloc[0]["resolved_date"] == "2026-10-23"
    assert current_executions.iloc[0]["status"] == "PASS"
    assert current_executions.iloc[0]["executed_at"] == "2026-10-24"
    assert issues.iloc[0]["status"] == "Open"
    assert executions.iloc[0]["status"] == "FAIL"


def test_dashboard_metrics_recalculate_from_event_log(project_files, tmp_path):
    history, teams_config = project_files
    events_file = tmp_path / "simulations" / "events.jsonl"
    events_file.parent.mkdir()
    events_file.write_text(
        json.dumps(
            {
                "event_id": 1,
                "target_type": "issue",
                "target_id": "QAA-1",
                "previous_status": "Open",
                "new_status": "Done",
                "note": "Resolved in simulation",
                "event_date": "2026-10-24",
            }
        )
        + "\n"
        + json.dumps(
            {
                "event_id": 2,
                "target_type": "execution",
                "target_id": "QAA-CYC-01-EX-001",
                "previous_status": "FAIL",
                "new_status": "PASS",
                "note": "Retest passed",
                "event_date": "2026-10-24",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    data = load_dashboard_data(history, events_file, teams_config)
    teams = build_team_metrics(data).set_index("id")
    sprints = build_sprint_metrics(data, "alpha")

    assert teams.loc["alpha", "open_defects"] == 0
    assert teams.loc["alpha", "completion_rate"] == 100.0
    assert teams.loc["alpha", "pass_rate"] == 100.0
    assert sprints.iloc[0]["baseline_pass_rate"] == 0.0
    assert sprints.iloc[0]["pass_rate"] == 100.0
    assert data["baseline"]["issues"].iloc[0]["status"] == "Open"
    assert data["baseline"]["executions"].iloc[0]["status"] == "FAIL"


def test_release_readiness_score_rewards_each_readiness_criterion(
    project_files,
):
    history, teams_config = project_files
    data = load_dashboard_data(
        history, history.parent / "no-events.jsonl", teams_config
    )
    data["current"]["issues"].loc[:, "status"] = "Done"
    data["current"]["issues"].loc[:, "blocked"] = "false"
    data["current"]["executions"].loc[:, "status"] = "PASS"

    ready_team = build_team_metrics(data).set_index("id").loc["alpha"]
    assert ready_team["release_readiness_score"] == 100.0

    data["current"]["issues"].loc[
        data["current"]["issues"]["issue_key"] == "QAA-1", "status"
    ] = "Open"
    data["current"]["issues"].loc[
        data["current"]["issues"]["issue_key"] == "QAA-1", "priority"
    ] = "High"
    data["current"]["issues"].loc[
        data["current"]["issues"]["issue_key"] == "QAA-1", "blocked"
    ] = "true"
    blocked_team = build_team_metrics(data).set_index("id").loc["alpha"]
    assert blocked_team["release_readiness_score"] == 70.0
    assert blocked_team["active_blockers"] == 1

    data["current"]["issues"].loc[:, "status"] = "Done"
    data["current"]["issues"].loc[:, "blocked"] = "false"
    data["current"]["issues"].loc[
        data["current"]["issues"]["issue_key"] == "QAA-1", "priority"
    ] = "Critical"
    data["current"]["issues"].loc[
        data["current"]["issues"]["issue_key"] == "QAA-1", "status"
    ] = "Open"
    critical_team = build_team_metrics(data).set_index("id").loc["alpha"]
    assert critical_team["active_blockers"] == 0
    assert critical_team["critical_open_defects"] == 1
    assert critical_team["release_readiness_score"] == 60.0

    data["current"]["issues"].loc[:, "status"] = "Done"
    data["current"]["executions"].loc[
        data["current"]["executions"]["execution_id"] == "QAA-CYC-01-EX-001",
        "status",
    ] = "FAIL"
    below_threshold_team = build_team_metrics(data).set_index("id").loc["alpha"]
    assert below_threshold_team["pass_rate"] < 90
    assert below_threshold_team["release_readiness_score"] == 70.0


def test_rejects_invalid_or_stale_simulation_events():
    issues = pd.DataFrame(
        [{"issue_key": "QAA-1", "status": "Open", "resolved_date": ""}]
    )
    executions = pd.DataFrame(
        [{"execution_id": "EX-1", "status": "FAIL", "executed_at": ""}]
    )
    with pytest.raises(ValueError, match="Invalid issue status"):
        replay_simulation_events(
            issues,
            executions,
            [{"target_type": "issue", "target_id": "QAA-1", "new_status": "Closed"}],
        )
    with pytest.raises(ValueError, match="expected status"):
        replay_simulation_events(
            issues,
            executions,
            [
                {
                    "target_type": "issue",
                    "target_id": "QAA-1",
                    "previous_status": "Done",
                    "new_status": "Open",
                }
            ],
        )
