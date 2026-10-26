"""Append synthetic simulation changes without modifying historical CSVs."""

from datetime import date
import json
from pathlib import Path
from typing import Any

from scripts.dashboard_data import (
    EVENTS,
    HISTORY,
    TEAMS_CONFIG,
    load_dashboard_data,
)

SIMULATION_STATUSES = {
    "issue": {"Open", "In Progress", "Done"},
    "execution": {"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"},
}
TARGET_COLUMNS = {"issue": "issue_key", "execution": "execution_id"}


def record_simulation(
    target_type: str,
    target_id: str,
    new_status: str,
    note: str,
    historical_dir: Path = HISTORY,
    events_file: Path = EVENTS,
    event_date: str | None = None,
    teams_config: Path | None = None,
) -> dict[str, Any]:
    """Validate a requested change and append a replayable event."""
    if target_type not in SIMULATION_STATUSES:
        raise ValueError(f"Unsupported simulation target type: {target_type!r}")
    if new_status not in SIMULATION_STATUSES[target_type]:
        raise ValueError(f"Unsupported {target_type} status: {new_status!r}")
    if not note.strip():
        raise ValueError("A simulation note is required")

    data = load_dashboard_data(
        historical_dir=historical_dir,
        events_file=events_file,
        teams_config=teams_config or TEAMS_CONFIG,
    )
    frame_name = "issues" if target_type == "issue" else "executions"
    frame = data["current"][frame_name]
    target_column = TARGET_COLUMNS[target_type]
    matches = frame[frame[target_column] == target_id]
    if len(matches) != 1:
        raise ValueError(
            f"Simulation target {target_id!r} matched {len(matches)} records"
        )
    previous_status = matches.iloc[0]["status"]
    if previous_status == new_status:
        raise ValueError(f"{target_id} already has status {new_status!r}")

    events = data["events"]
    numeric_ids = [
        event["event_id"]
        for event in events
        if str(event.get("event_id", "")).isdigit()
    ]
    event = {
        "event_id": max((int(value) for value in numeric_ids), default=0) + 1,
        "target_type": target_type,
        "target_id": target_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "note": note.strip(),
        "event_date": event_date or date.today().isoformat(),
    }

    events_file.parent.mkdir(parents=True, exist_ok=True)
    with events_file.open("a", encoding="utf-8") as event_stream:
        event_stream.write(json.dumps(event) + "\n")
    return event
