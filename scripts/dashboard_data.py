"""Load synthetic project data, replay simulations, and calculate dashboard metrics."""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "historical"
EVENTS = ROOT / "data" / "simulations" / "events.jsonl"
TEAMS_CONFIG = ROOT / "config" / "teams.yaml"

ISSUE_STATUSES = {"Open", "In Progress", "Done"}
EXECUTION_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"}
RELEASE_READINESS_PASS_RATE = 90.0
RELEASE_READINESS_CRITICAL_DEFECT_POINTS = 40
RELEASE_READINESS_BLOCKER_POINTS = 30
RELEASE_READINESS_PASS_RATE_POINTS = 30
CSV_FILES = {
    "sprints": "sprints.csv",
    "issues": "jira_issues.csv",
    "test_cases": "zephyr_test_cases.csv",
    "cycles": "zephyr_cycles.csv",
    "executions": "zephyr_executions.csv",
    "snapshots": "snapshots.csv",
    "dependencies": "dependencies.csv",
}


def read_simulation_events(events_file: Path = EVENTS) -> list[dict[str, Any]]:
    """Read append-only JSONL events, accepting the original issue-event shape."""
    if not events_file.exists():
        return []

    events = []
    with events_file.open(encoding="utf-8") as event_stream:
        for line_number, line in enumerate(event_stream, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid simulation event on line {line_number} of {events_file}"
                ) from exc
            if not isinstance(event, dict):
                raise ValueError(
                    f"Simulation event on line {line_number} must be a JSON object"
                )
            events.append(event)
    return events


def replay_simulation_events(
    issues: pd.DataFrame,
    executions: pd.DataFrame,
    events: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply events to copies of baseline rows, leaving the inputs unchanged."""
    current_issues = issues.copy(deep=True)
    current_executions = executions.copy(deep=True)

    for event in events:
        target_type = event.get("target_type")
        if target_type is None and "issue_key" in event:
            target_type = "issue"
            target_id = event["issue_key"]
        else:
            target_id = event.get("target_id")

        if target_type == "issue":
            frame = current_issues
            id_column = "issue_key"
            allowed_statuses = ISSUE_STATUSES
        elif target_type == "execution":
            frame = current_executions
            id_column = "execution_id"
            allowed_statuses = EXECUTION_STATUSES
        else:
            raise ValueError(f"Unknown simulation target type: {target_type!r}")

        if not isinstance(target_id, str) or not target_id:
            raise ValueError("Simulation event is missing a target ID")
        new_status = event.get("new_status")
        if new_status not in allowed_statuses:
            raise ValueError(
                f"Invalid {target_type} status {new_status!r} for target {target_id}"
            )

        matches = frame.index[frame[id_column] == target_id]
        if len(matches) != 1:
            raise ValueError(
                f"Simulation target {target_id!r} matched {len(matches)} baseline rows"
            )
        row_index = matches[0]
        current_status = frame.at[row_index, "status"]
        previous_status = event.get("previous_status")
        if previous_status is not None and previous_status != current_status:
            raise ValueError(
                f"Simulation event for {target_id} expected status "
                f"{previous_status!r}, found {current_status!r}"
            )

        frame.at[row_index, "status"] = new_status
        event_date = event.get("event_date", "")
        if target_type == "issue":
            frame.at[row_index, "resolved_date"] = (
                event_date if new_status == "Done" else ""
            )
        else:
            frame.at[row_index, "executed_at"] = (
                "" if new_status == "NOT_EXECUTED" else event_date
            )

    return current_issues, current_executions


def load_dashboard_data(
    historical_dir: Path = HISTORY,
    events_file: Path = EVENTS,
    teams_config: Path = TEAMS_CONFIG,
) -> dict[str, Any]:
    """Load baseline CSVs and return baseline plus event-replayed dataframes."""
    baseline = {
        name: pd.read_csv(historical_dir / filename, dtype=str, keep_default_na=False)
        for name, filename in CSV_FILES.items()
    }
    with teams_config.open(encoding="utf-8") as config_stream:
        team_config = yaml.safe_load(config_stream)
    teams = team_config.get("teams") if isinstance(team_config, dict) else None
    if not isinstance(teams, list) or not teams:
        raise ValueError(f"Team configuration must contain a non-empty teams list: {teams_config}")

    events = read_simulation_events(events_file)
    current_issues, current_executions = replay_simulation_events(
        baseline["issues"], baseline["executions"], events
    )
    current = dict(baseline)
    current["issues"] = current_issues
    current["executions"] = current_executions
    return {"baseline": baseline, "current": current, "events": events, "teams": teams}


def _percentage(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0


def build_team_metrics(data: dict[str, Any]) -> pd.DataFrame:
    """Summarize current issue and execution metrics for every configured team."""
    issues = data["current"]["issues"]
    executions = data["current"]["executions"]
    rows = []
    for team in data["teams"]:
        team_id = team["id"]
        team_issues = issues[issues["team_id"] == team_id]
        bugs = team_issues[team_issues["issue_type"] == "Bug"]
        open_bugs = bugs[bugs["status"] != "Done"]
        active_blockers = team_issues[
            (team_issues["status"] != "Done")
            & (team_issues["blocked"].str.casefold() == "true")
        ]
        done_issues = team_issues[team_issues["status"] == "Done"]
        team_executions = executions[executions["team_id"] == team_id]
        passed = int((team_executions["status"] == "PASS").sum())
        executed = int(team_executions["status"].isin(["PASS", "FAIL", "BLOCKED"]).sum())
        critical_open_defects = int(
            (open_bugs["priority"] == "Critical").sum()
        )
        pass_rate = _percentage(passed, executed)
        release_readiness_score = round(
            (RELEASE_READINESS_CRITICAL_DEFECT_POINTS if critical_open_defects == 0 else 0)
            + (RELEASE_READINESS_BLOCKER_POINTS if active_blockers.empty else 0)
            + min(pass_rate / RELEASE_READINESS_PASS_RATE, 1.0)
            * RELEASE_READINESS_PASS_RATE_POINTS,
            1,
        )
        rows.append(
            {
                **team,
                "issue_count": len(team_issues),
                "completed_issues": len(done_issues),
                "completion_rate": _percentage(len(done_issues), len(team_issues)),
                "defect_count": len(bugs),
                "open_defects": len(open_bugs),
                "critical_open_defects": critical_open_defects,
                "active_blockers": len(active_blockers),
                "execution_count": len(team_executions),
                "passed": passed,
                "failed": int((team_executions["status"] == "FAIL").sum()),
                "blocked": int((team_executions["status"] == "BLOCKED").sum()),
                "not_executed": int((team_executions["status"] == "NOT_EXECUTED").sum()),
                "pass_rate": pass_rate,
                "release_readiness_score": release_readiness_score,
            }
        )
    return pd.DataFrame(rows)


def build_sprint_metrics(
    data: dict[str, Any], team_id: str | None = None
) -> pd.DataFrame:
    """Calculate sprint outcomes from replayed records alongside snapshot rates."""
    current = data["current"]
    baseline_snapshots = data["baseline"]["snapshots"]
    sprints = current["sprints"]
    if team_id is not None:
        sprints = sprints[sprints["team_id"] == team_id]

    team_names = {team["id"]: team["name"] for team in data["teams"]}
    rows = []
    for sprint in sprints.to_dict("records"):
        sprint_id = sprint["sprint_id"]
        sprint_issues = current["issues"][current["issues"]["sprint_id"] == sprint_id]
        bugs = sprint_issues[sprint_issues["issue_type"] == "Bug"]
        sprint_executions = current["executions"][
            current["executions"]["sprint_id"] == sprint_id
        ]
        passed = int((sprint_executions["status"] == "PASS").sum())
        executed = int(
            sprint_executions["status"].isin(["PASS", "FAIL", "BLOCKED"]).sum()
        )
        snapshot = baseline_snapshots[baseline_snapshots["sprint_id"] == sprint_id]
        baseline_rate = float(snapshot.iloc[0]["pass_rate"]) if not snapshot.empty else 0.0
        rows.append(
            {
                **sprint,
                "team_name": team_names[sprint["team_id"]],
                "issue_count": len(sprint_issues),
                "completed_issues": int((sprint_issues["status"] == "Done").sum()),
                "completion_rate": _percentage(
                    int((sprint_issues["status"] == "Done").sum()),
                    len(sprint_issues),
                ),
                "defect_count": len(bugs),
                "open_defects": int((bugs["status"] != "Done").sum()),
                "passed": passed,
                "failed": int((sprint_executions["status"] == "FAIL").sum()),
                "blocked": int((sprint_executions["status"] == "BLOCKED").sum()),
                "not_executed": int(
                    (sprint_executions["status"] == "NOT_EXECUTED").sum()
                ),
                "pass_rate": _percentage(passed, executed),
                "baseline_pass_rate": baseline_rate,
            }
        )
    return pd.DataFrame(rows).sort_values(["team_id", "sprint_number"]).reset_index(drop=True)
