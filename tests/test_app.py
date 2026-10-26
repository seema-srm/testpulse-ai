import json
from pathlib import Path
import tomllib

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def run_page(app, title):
    page_hash = next(
        page_hash
        for page_hash, page in app._registered_pages.items()
        if page["page_name"] == title
    )
    app._page_hash = page_hash
    return app.run(timeout=15)


def test_dashboard_pages_render_without_errors(monkeypatch):
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    app = AppTest.from_file(str(APP_PATH)).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "TestPulse AI"
    assert not any(widget.label == "Dataset" for widget in app.selectbox)
    assert any(heading.value == "Recent Changes" for heading in app.subheader)
    assert not any(
        heading.value == "Recent Simulation Changes" for heading in app.subheader
    )
    assert any(
        "Not Executed tests are excluded" in caption.value
        for caption in app.caption
    )
    assert any(
        "Release Readiness Score (0–100)" in caption.value
        for caption in app.caption
    )
    assert any(
        "Release Readiness Score" in column
        for dataframe in app.dataframe
        for column in dataframe.value.columns
    )
    scorecard = next(
        dataframe.value
        for dataframe in app.dataframe
        if "Release Readiness Score" in dataframe.value.columns
    )
    assert all(
        isinstance(value, str)
        and value.endswith("%")
        and len(value.rsplit(".", 1)[-1].removesuffix("%")) == 1
        for value in scorecard[
            ["Completion (%)", "Pass Rate (%)", "Release Readiness Score"]
        ].to_numpy().flatten()
    )
    assert all(
        "NOT_EXECUTED" not in caption.value for caption in app.caption
    )
    assert not app.radio
    page_titles = [
        page["page_name"] for page in app._registered_pages.values()
    ]
    assert page_titles == [
        "Executive Dashboard",
        "Team Details",
        "AI Risk Analysis",
        "Weekly Status Report",
        "Simulation Center",
    ]

    run_page(app, "Team Details")
    assert not app.exception
    assert app.title[0].value.startswith("Team Alpha")

    run_page(app, "Simulation Center")
    assert not app.exception
    assert app.title[0].value == "Simulation Center"

    run_page(app, "AI Risk Analysis")
    assert not app.exception
    assert app.title[0].value == "AI Risk Analysis"
    assert not any(button.label == "Run Portfolio Analysis" for button in app.button)
    assert any(
        "FIREWORKS_API_KEY" in info.value for info in app.info
    )

    run_page(app, "Weekly Status Report")
    assert not app.exception
    assert app.title[0].value == "Weekly Status Report"
    assert {button.label for button in app.download_button} == {
        "Download Markdown",
        "Download Excel",
    }


def test_analysis_report_uses_named_teams_risk_badges_and_metric_cards(monkeypatch):
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-fireworks-key")
    app = AppTest.from_file(str(APP_PATH)).run(timeout=15)
    run_page(app, "AI Risk Analysis")
    app.session_state["qa_portfolio_analysis"] = {
        "summary": "Team Alpha should review its current pass rate.",
        "findings": [
            {
                "team_id": "alpha",
                "risk_level": "Low",
                "title": "High Pass Rate",
                "explanation": "The pass rate is strong across the observed executions.",
                "evidence_refs": ["team:alpha:pass_rate"],
                "recommended_actions": ["Continue monitoring the pass rate."],
            }
        ],
    }
    app.session_state["qa_portfolio_analysis_evidence"] = {
        "team:alpha:pass_rate": {
            "team_id": "alpha",
            "label": "Pass Rate",
            "value": "79.07%",
        }
    }
    app.run(timeout=15)

    assert not app.exception
    assert any("Team Alpha" in element.value for element in app.markdown)
    assert any(
        ":green-badge[Low Risk]" in element.value for element in app.markdown
    )
    assert any(metric.label == "Pass Rate" for metric in app.metric)


def test_simulation_choices_update_when_team_changes():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=15)
    run_page(app, "Simulation Center")

    issue_team = next(widget for widget in app.selectbox if widget.key == "issue_team")
    issue_team.set_value("Team Beta").run()
    defect_selector = next(widget for widget in app.selectbox if widget.label == "Defect")
    assert "QAB-900" in defect_selector.options
    assert all(option.startswith("QAB-") for option in defect_selector.options)

    execution_team = next(
        widget for widget in app.selectbox if widget.key == "execution_team"
    )
    execution_team.set_value("Team Gamma").run()
    execution_selector = next(
        widget for widget in app.selectbox if widget.label == "Test Execution"
    )
    assert all(option.startswith("QAC-") for option in execution_selector.options)

    outcome_selector = next(
        widget for widget in app.selectbox if widget.label == "New Outcome"
    )
    assert outcome_selector.options == ["PASS", "FAIL", "BLOCKED", "NOT EXECUTED"]


def test_team_colors_are_consistent_and_distinguishable_in_portfolio_charts():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=15)
    expected_colors = {
        "Team Alpha": "#2563EB",
        "Team Beta": "#0F766E",
        "Team Gamma": "#7C3AED",
        "Team Delta": "#475569",
    }

    for chart in app.get("plotly_chart"):
        traces = json.loads(chart.proto.spec)["data"]
        actual_colors = {
            trace["name"]: trace.get("marker", {}).get("color")
            or trace.get("line", {}).get("color")
            for trace in traces
        }
        assert actual_colors == expected_colors


def test_theme_uses_teal_accents_and_darker_table_headers():
    config_path = APP_PATH.parent / ".streamlit" / "config.toml"
    with config_path.open("rb") as config_file:
        theme = tomllib.load(config_file)["theme"]

    assert theme["primaryColor"] == "#0F766E"
    assert theme["linkColor"] == "#0F766E"
    assert theme["backgroundColor"] == "#F0F9F8"
    assert theme["secondaryBackgroundColor"] == "#FFFFFF"
    assert theme["dataframeHeaderBackgroundColor"] == "#0F766E"
    assert theme["dataframeHeaderTextColor"] == "#FFFFFF"
    assert theme["chartCategoricalColors"] == [
        "#2563EB",
        "#0F766E",
        "#7C3AED",
        "#475569",
    ]
    assert theme["sidebar"]["backgroundColor"] == "#E6F4F2"
