import json
from copy import deepcopy

import httpx
import ollama
import pandas as pd
import pytest
from pydantic import ValidationError

from scripts.qa_agent import (
    PortfolioAnalysis,
    PortfolioFindings,
    QAAgentConfigurationError,
    QAAgentUnavailableError,
    QAAgentValidationError,
    _check_local_ollama_url,
    prepare_portfolio_facts,
    run_portfolio_analysis,
    local_ollama_enabled,
)


class FakeStructuredModel:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.schema = None
        self.request = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        self.request = json.loads(messages[1].content)
        if self.error:
            raise self.error
        return self.response


def valid_analysis(team_id="alpha", evidence_ref="team:alpha:open_defects"):
    return {
        "findings": [
            {
                "team_id": team_id,
                "risk_level": "Medium",
                "title": "Review open defect status",
                "explanation": "The open-defect count warrants follow-up.",
                "evidence_refs": [evidence_ref],
                "recommended_actions": ["Review the open defect with the team."],
            }
        ],
    }


def test_portfolio_graph_returns_structured_grounded_analysis(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(valid_analysis())

    result = run_portfolio_analysis(data, model=model)

    assert isinstance(result, PortfolioAnalysis)
    assert model.schema is PortfolioFindings
    assert "summary" not in model.schema.model_fields
    assert result.findings[0].team_id == "alpha"
    assert model.request["portfolio_facts"][0]["team_id"] == "alpha"
    assert "available_evidence" in model.request


def test_hosted_demo_can_disable_local_ollama():
    assert local_ollama_enabled({}) is True
    assert local_ollama_enabled(
        {"testpulse": {"enable_local_ai": False}}
    ) is False


def test_local_ollama_setting_must_be_boolean():
    with pytest.raises(QAAgentConfigurationError, match="must be true or false"):
        local_ollama_enabled(
            {"testpulse": {"enable_local_ai": "false"}}
        )


def test_agent_receives_aggregate_metrics_not_issue_details(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(valid_analysis())

    run_portfolio_analysis(data, model=model)

    serialized = json.dumps(model.request)
    assert "Synthetic defect" not in serialized
    assert "QAA-1" not in serialized
    assert "issue_key" not in serialized
    assert "summary" not in serialized


def test_rejects_unknown_or_cross_team_evidence(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(valid_analysis(evidence_ref="team:beta:open_defects"))

    with pytest.raises(QAAgentValidationError, match="does not belong"):
        run_portfolio_analysis(data, model=model)


def test_allows_multiple_findings_for_one_team_when_evidence_is_grounded(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    response = valid_analysis()
    response["findings"].append(
        {
            **valid_analysis(evidence_ref="team:alpha:pass_rate")["findings"][0],
            "title": "Review test pass rate",
            "explanation": "The test pass rate indicates further validation is useful.",
        }
    )

    result = run_portfolio_analysis(
        data, model=FakeStructuredModel(response)
    )

    assert len(result.findings) == 2
    assert all(finding.team_id == "alpha" for finding in result.findings)


def test_portfolio_summary_uses_current_metrics_not_model_generated_text(
    project_files,
):
    history, teams_config = project_files
    issues_path = history / "jira_issues.csv"
    issues = pd.read_csv(issues_path, dtype=str, keep_default_na=False)
    delta_issues = []
    for number in range(1, 7):
        issue = issues.iloc[0].to_dict()
        issue.update(
            {
                "issue_key": f"QAD-{number}",
                "project_key": "QAD",
                "team_id": "delta",
                "issue_type": "Bug",
                "priority": "Critical",
                "status": "Open",
                "blocked": "true",
            }
        )
        delta_issues.append(issue)
    pd.concat([issues, pd.DataFrame(delta_issues)]).to_csv(
        issues_path, index=False
    )
    teams_config.write_text(
        teams_config.read_text(encoding="utf-8")
        + "  - {id: delta, name: Team Delta, project_key: QAD, domain: APIs}\n",
        encoding="utf-8",
    )

    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(
        history, history.parent / "no-events.jsonl", teams_config
    )
    model = FakeStructuredModel(
        {
            "findings": [
                {
                    **valid_analysis(
                        team_id="delta",
                        evidence_ref="team:delta:critical_open_defects",
                    )["findings"][0],
                    "title": "Review Team Delta critical defects",
                    "explanation": "Team Delta has critical defects requiring review.",
                }
            ]
        }
    )

    result = run_portfolio_analysis(data, model=model)

    assert "Open critical defects: 7 (Team Alpha: 1, Team Delta: 6)." in result.summary
    assert "Active blockers: 7." in result.summary
    assert "summary" not in model.schema.model_fields


def test_rejects_unregistered_teams(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(valid_analysis(team_id="unknown"))

    with pytest.raises(QAAgentValidationError, match="unknown team"):
        run_portfolio_analysis(data, model=model)


def test_rejects_unknown_evidence_reference(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(valid_analysis(evidence_ref="made-up-reference"))

    with pytest.raises(QAAgentValidationError, match="unknown evidence reference"):
        run_portfolio_analysis(data, model=model)


def test_schema_limits_findings_and_text():
    with pytest.raises(ValidationError):
        PortfolioAnalysis(
            summary="Too short",
            findings=[
                {
                    "team_id": f"team-{index}",
                    "risk_level": "High",
                    "title": "Risk",
                    "explanation": "This is a sufficiently long explanation.",
                    "evidence_refs": ["metric-ref"],
                    "recommended_actions": ["Review with the team."],
                }
                for index in range(5)
            ],
        )
    with pytest.raises(ValidationError):
        PortfolioAnalysis(
            summary="This report summary is long enough.",
            findings=[
                {
                    **valid_analysis()["findings"][0],
                    "recommended_actions": ["x" * 241],
                }
            ],
        )


def test_local_endpoint_rejects_non_loopback_destinations():
    assert _check_local_ollama_url("http://localhost:11434/") == (
        "http://localhost:11434"
    )
    with pytest.raises(QAAgentConfigurationError, match="Remote endpoints"):
        _check_local_ollama_url("https://example.com")


def test_local_model_connection_error_is_actionable(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(error=httpx.ConnectError("connection refused"))

    with pytest.raises(QAAgentUnavailableError, match="Start Ollama"):
        run_portfolio_analysis(data, model=model)


def test_ollama_model_errors_are_actionable(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    model = FakeStructuredModel(error=ollama.ResponseError("model not found"))

    with pytest.raises(QAAgentUnavailableError, match="model is available locally"):
        run_portfolio_analysis(data, model=model)


def test_analysis_does_not_modify_portfolio_data(project_files):
    history, teams_config = project_files
    from scripts.dashboard_data import load_dashboard_data

    data = load_dashboard_data(history, history.parent / "no-events.jsonl", teams_config)
    original = deepcopy(data)
    model = FakeStructuredModel(valid_analysis())

    run_portfolio_analysis(data, model=model)

    def assert_unchanged(actual, expected):
        if isinstance(actual, pd.DataFrame):
            pd.testing.assert_frame_equal(actual, expected)
        elif isinstance(actual, dict):
            assert actual.keys() == expected.keys()
            for key in actual:
                assert_unchanged(actual[key], expected[key])
        elif isinstance(actual, list):
            assert len(actual) == len(expected)
            for actual_item, expected_item in zip(actual, expected):
                assert_unchanged(actual_item, expected_item)
        else:
            assert actual == expected

    assert_unchanged(data, original)
