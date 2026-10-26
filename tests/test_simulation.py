import pytest

from scripts.dashboard_data import load_dashboard_data
from scripts.simulation import record_simulation


def test_record_simulation_appends_without_changing_baseline(project_files):
    history, teams_config = project_files
    events_file = history.parent / "events.jsonl"
    baseline_before = {
        path.name: path.read_bytes() for path in history.glob("*.csv")
    }

    event = record_simulation(
        "issue",
        "QAA-1",
        "Done",
        "Verified in synthetic test",
        historical_dir=history,
        events_file=events_file,
        event_date="2026-10-24",
    )
    second_event = record_simulation(
        "execution",
        "QAA-CYC-01-EX-001",
        "PASS",
        "Retest passed",
        historical_dir=history,
        events_file=events_file,
        event_date="2026-10-25",
    )

    data = load_dashboard_data(history, events_file, teams_config)
    assert event["event_id"] == 1
    assert second_event["event_id"] == 2
    assert data["current"]["issues"].iloc[0]["status"] == "Done"
    assert data["current"]["executions"].iloc[0]["status"] == "PASS"
    assert {
        path.name: path.read_bytes() for path in history.glob("*.csv")
    } == baseline_before
    assert len(events_file.read_text(encoding="utf-8").splitlines()) == 2


def test_rejects_invalid_simulation_without_appending(project_files):
    history, _ = project_files
    events_file = history.parent / "events.jsonl"

    with pytest.raises(ValueError, match="Unsupported execution status"):
        record_simulation(
            "execution",
            "QAA-CYC-01-EX-001",
            "SKIPPED",
            "Invalid outcome",
            historical_dir=history,
            events_file=events_file,
        )
    assert not events_file.exists()

    with pytest.raises(ValueError, match="already has status"):
        record_simulation(
            "issue",
            "QAA-1",
            "Open",
            "No-op status",
            historical_dir=history,
            events_file=events_file,
        )
    assert not events_file.exists()
