"""Interactive synthetic QA dashboard for TestPulse AI."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from scripts.dashboard_data import (
    EVENTS,
    HISTORY,
    RELEASE_READINESS_BLOCKER_POINTS,
    RELEASE_READINESS_CRITICAL_DEFECT_POINTS,
    RELEASE_READINESS_PASS_RATE,
    RELEASE_READINESS_PASS_RATE_POINTS,
    TEAMS_CONFIG,
    build_sprint_metrics,
    build_team_metrics,
    load_dashboard_data,
)
from scripts.simulation import record_simulation
from scripts.table_styling import (
    status_for_display,
    style_outcome_deltas,
    style_outcome_table,
)
from scripts.qa_agent import (
    DEFAULT_FIREWORKS_MODEL,
    PortfolioAnalysis,
    QAAgentError,
    build_portfolio_summary,
    fireworks_ai_enabled,
    get_fireworks_api_key,
    prepare_portfolio_facts,
    run_portfolio_analysis,
)
from scripts.status_memory import (
    STATUS_MEMORY_DB,
    build_weekly_status_report,
    format_weekly_status_excel,
    format_weekly_status_markdown,
    get_latest_weekly_status_report,
    get_previous_weekly_status_report,
    save_weekly_status_report,
    team_status_frame,
    week_over_week_frame,
)

st.set_page_config(page_title="TestPulse AI | QA Portfolio", layout="wide")

TEAM_COLORS = {
    "alpha": "#2563EB",
    "beta": "#0F766E",
    "gamma": "#7C3AED",
    "delta": "#475569",
}
TEAM_BADGE_COLORS = {
    "alpha": "blue",
    "beta": "green",
    "gamma": "violet",
    "delta": "gray",
}


@st.cache_data
def get_dashboard_data():
    return load_dashboard_data(HISTORY, EVENTS, TEAMS_CONFIG)


def show_recent_changes(data):
    rows = []
    for event in data["events"]:
        target_type = event.get("target_type")
        target_id = event.get("target_id")
        if target_type is None and "issue_key" in event:
            target_type = "defect"
            target_id = event["issue_key"]
        elif target_type == "issue":
            target_type = "defect"

        rows.append(
            {
                "Event": event.get("event_id", ""),
                "Type": target_type,
                "Record": target_id,
                "Previous Status": status_for_display(
                    event.get(
                        "previous_status",
                        event.get("previous_baseline_status", "Unknown"),
                    )
                ),
                "New Status": status_for_display(
                    event.get("new_status", "")
                ),
                "Date": event.get("event_date", ""),
                "Note": event.get("note", ""),
            }
        )

    if rows:
        changes = pd.DataFrame(rows[::-1])
        st.dataframe(
            style_outcome_table(changes, status_column="New Status"),
            hide_index=True,
            width="stretch",
            column_config={
                "Previous Status": st.column_config.TextColumn(width="medium"),
                "New Status": st.column_config.TextColumn(width="medium"),
            },
            alt="Simulation changes showing each record's previous and new status.",
        )
    else:
        st.info("No simulation changes recorded for this dataset yet.")


def _fireworks_configuration_for_app():
    try:
        secrets = st.secrets
        enabled = fireworks_ai_enabled(secrets)
        api_key = get_fireworks_api_key(secrets)
    except StreamlitSecretNotFoundError:
        secrets = {}
        enabled = fireworks_ai_enabled(secrets)
        api_key = get_fireworks_api_key(secrets)
    return enabled, api_key


def show_ai_risk_analysis(data):
    st.title("AI Risk Analysis")
    enabled, api_key = _fireworks_configuration_for_app()
    if not enabled:
        st.caption("Fireworks AI analysis is disabled in this deployment.")
        st.info(
            "The portfolio summary below is calculated from synthetic metrics. "
            "Enable Fireworks AI in the [testpulse] settings to run model analysis."
        )
        st.subheader("Portfolio Summary")
        st.write(build_portfolio_summary(data))
        return

    if not api_key:
        st.caption("Fireworks AI is not configured for this deployment.")
        st.info(
            "Add FIREWORKS_API_KEY to Streamlit Secrets (or the local environment) "
            "to enable AI-generated findings. The factual portfolio summary remains "
            "available without an API key."
        )
        st.subheader("Portfolio Summary")
        st.write(build_portfolio_summary(data))
        return

    st.caption("Read-only analysis of synthetic portfolio metrics using Fireworks AI.")
    st.info(
        "The portfolio summary is calculated directly from current metrics. Fireworks "
        "receives aggregate team and sprint metrics only to produce risk findings; it "
        "cannot access "
        "individual issue details, connect to Jira/Zephyr, or write simulation events. "
        "These aggregate synthetic metrics are sent to Fireworks AI. Review suggested "
        "actions before using them."
    )

    if st.button("Run Portfolio Analysis", type="primary"):
        try:
            with st.spinner(
                "Analyzing synthetic metrics with Fireworks AI..."
            ):
                analysis = run_portfolio_analysis(data, api_key=api_key)
        except QAAgentError as exc:
            st.error(str(exc), title="Analysis Could Not Be Completed")
        else:
            st.session_state["qa_portfolio_analysis"] = analysis.model_dump()
            st.session_state["qa_portfolio_analysis_evidence"] = (
                prepare_portfolio_facts(data)[1]
            )

    saved_analysis = st.session_state.get("qa_portfolio_analysis")
    evidence = st.session_state.get("qa_portfolio_analysis_evidence")
    if not saved_analysis or not evidence:
        st.caption(
            "Select Run Portfolio Analysis to generate findings. The default model is "
            f"`{DEFAULT_FIREWORKS_MODEL}`; override it with "
            "`TESTPULSE_FIREWORKS_MODEL`."
        )
        return

    analysis = PortfolioAnalysis.model_validate(saved_analysis)
    team_names = {team["id"]: team["name"] for team in data["teams"]}
    st.subheader("Portfolio Summary")
    st.write(analysis.summary)

    st.subheader("Ranked Team Findings")
    st.caption(
        "Risk levels: :red-badge[High] :orange-badge[Medium] :green-badge[Low]"
    )
    for rank, finding in enumerate(analysis.findings, start=1):
        with st.container(border=True):
            st.markdown(f"### {rank}. {finding.title}")
            risk_color = {
                "High": "red",
                "Medium": "orange",
                "Low": "green",
            }[finding.risk_level]
            team_name = team_names[finding.team_id]
            st.markdown(
                f":{risk_color}-badge[{finding.risk_level} Risk] · "
                f":{TEAM_BADGE_COLORS[finding.team_id]}-badge[{team_name}]"
            )
            st.write(finding.explanation)
            st.markdown("**Evidence**")
            evidence_columns = st.columns(
                min(len(finding.evidence_refs), 4), wrap=True
            )
            for column, ref in zip(evidence_columns, finding.evidence_refs):
                fact = evidence[ref]
                with column:
                    st.metric(label=fact["label"], value=fact["value"])
            st.markdown("**Suggested Actions (Human Review Required)**")
            for action in finding.recommended_actions:
                st.write(f"- {action}")


def show_weekly_status_report(data):
    st.title("Weekly Status Report")
    st.caption(
        "Persistent, local memory of synthetic team status, blockers, and sprint carryovers."
    )
    st.info(
        "Reports are saved in a local SQLite file. Refreshing a report updates that "
        "week's entry; previous weeks remain available for week-over-week comparison."
    )

    report_date = st.date_input("Report Week", value=date.today())
    if st.button("Generate / Refresh Weekly Report", type="primary"):
        report = build_weekly_status_report(data, report_date)
        previous_report = get_previous_weekly_status_report(
            report["week_start"], STATUS_MEMORY_DB
        )
        save_weekly_status_report(report, STATUS_MEMORY_DB)
        st.session_state["weekly_status_report"] = report
        st.session_state["weekly_status_previous_report"] = previous_report

    report = st.session_state.get("weekly_status_report")
    previous_report = st.session_state.get("weekly_status_previous_report")
    if report is None:
        report = get_latest_weekly_status_report(STATUS_MEMORY_DB)
        if report is not None:
            previous_report = get_previous_weekly_status_report(
                report["week_start"], STATUS_MEMORY_DB
            )
    if report is None:
        st.caption(
            "Generate a report to start persistent weekly memory. Later reports "
            "will compare against the previous saved week."
        )
        return

    st.subheader(
        f"Week Of {report['week_start']} - {report['week_end']}"
    )
    st.write(report["summary"])

    previous_by_team = {
        team["team_id"]: team for team in (previous_report or {}).get("teams", [])
    }
    metric_columns = st.columns(4)
    for column, team in zip(metric_columns, report["teams"]):
        previous = previous_by_team.get(team["team_id"])
        pass_delta = (
            f"{team['pass_rate'] - previous['pass_rate']:+.2f} pts"
            if previous
            else None
        )
        with column:
            st.markdown(
                f":{TEAM_BADGE_COLORS[team['team_id']]}-badge[{team['team_name']}]"
            )
            st.metric(
                "Pass Rate",
                f"{team['pass_rate']:.2f}%",
                delta=pass_delta,
            )

    st.subheader("Team Status")
    st.dataframe(
        style_outcome_table(
            team_status_frame(report),
            failed_column="Failed Tests",
            blocked_column="Blocked Tests",
        ),
        hide_index=True,
        width="stretch",
        alt="Weekly team risk, completion, test, and defect metrics.",
    )
    if previous_report:
        st.subheader("Week-over-Week Changes")
        st.dataframe(
            style_outcome_deltas(
                week_over_week_frame(report, previous_report),
                failed_column="Failed Tests",
                blocked_column="Blocked Tests",
            ),
            hide_index=True,
            width="stretch",
            alt="Changes in team pass rates, completion, defects, and test outcomes.",
        )

    st.subheader("Blockers")
    if report["blockers"]:
        st.dataframe(
            style_outcome_table(
                pd.DataFrame(
                    [
                        {
                            "Team": blocker["team_name"],
                            "Issue": blocker["issue_key"],
                            "Title": blocker["summary"],
                            "Priority": blocker["priority"],
                            "Status": blocker["status"],
                        }
                        for blocker in report["blockers"]
                    ]
                ),
                status_column="Status",
                compact_status=True,
            ),
            hide_index=True,
            width="stretch",
            alt="Active synthetic issues explicitly marked as blocked.",
        )
    else:
        st.info("No active blockers are recorded.")

    st.subheader("What Has Been Stuck for More Than One Sprint?")
    if report["stuck_items"]:
        st.dataframe(
            style_outcome_table(
                pd.DataFrame(
                    [
                        {
                            "Team": item["team_name"],
                            "Issue": item["issue_key"],
                            "Title": item["summary"],
                            "Status": item["status"],
                            "State": "Active" if item["active"] else "Resolved",
                            "Priority": item["priority"],
                            "Sprints": item["stuck_sprints"],
                        }
                        for item in report["stuck_items"]
                    ]
                ),
                status_column="Status",
            ),
            hide_index=True,
            width="stretch",
            alt="Active synthetic issues carried over across multiple sprints.",
        )
    else:
        st.info("No active multi-sprint carryover items are recorded.")

    if previous_report:
        st.caption(
            f"Week-over-week changes compare with the saved report for "
            f"{previous_report['week_start']}."
        )
    else:
        st.caption("No earlier weekly report is saved yet; this report starts memory.")

    with st.container(horizontal=True):
        st.download_button(
            "Download Markdown",
            data=format_weekly_status_markdown(report, previous_report),
            file_name=f"weekly-status-{report['week_start']}.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download Excel",
            data=format_weekly_status_excel(report, previous_report),
            file_name=f"weekly-status-{report['week_start']}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def show_executive_dashboard(data):
    st.title("TestPulse AI")
    st.caption("Synthetic QA Portfolio Performance Across Four Teams")
    st.caption(
        "Test pass rate = PASS / (PASS + FAIL + BLOCKED); "
        "Not Executed tests are excluded."
    )
    metrics = build_team_metrics(data)
    total_defects = int(metrics["defect_count"].sum())
    open_defects = int(metrics["open_defects"].sum())
    avg_pass_rate = float(metrics["pass_rate"].mean())

    cards = st.columns(5)
    cards[0].metric("QA Teams", len(metrics), border=True)
    cards[1].metric("Test Cases", len(data["current"]["test_cases"]), border=True)
    cards[2].metric("Defects", total_defects, border=True)
    cards[3].metric("Open Defects", open_defects, border=True)
    cards[4].metric(
        "Average Test Pass Rate", f"{avg_pass_rate:.1f}%", border=True
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Current Team Comparison")
        comparison = metrics.sort_values("pass_rate", ascending=False)
        chart = px.bar(
            comparison,
            x="name",
            y="pass_rate",
            color="name",
            color_discrete_map={
                team["name"]: TEAM_COLORS[team["id"]] for team in data["teams"]
            },
            text_auto=".1f",
            labels={"name": "QA Team", "pass_rate": "Pass Rate (%)"},
            range_y=[0, 100],
        )
        chart.update_layout(showlegend=False, yaxis_ticksuffix="%")
        st.plotly_chart(
            chart,
            width="stretch",
            alt="Bar chart comparing current test pass rates across QA teams.",
        )
    with right:
        st.subheader("Sprint Pass Rate Trend")
        sprint_metrics = build_sprint_metrics(data)
        chart = px.line(
            sprint_metrics,
            x="sprint_number",
            y="pass_rate",
            color="team_name",
            color_discrete_map={
                team["name"]: TEAM_COLORS[team["id"]] for team in data["teams"]
            },
            markers=True,
            labels={
                "sprint_number": "Sprint",
                "pass_rate": "Replay-Adjusted Pass Rate (%)",
                "team_name": "QA Team",
            },
        )
        chart.update_layout(yaxis_ticksuffix="%")
        st.plotly_chart(
            chart,
            width="stretch",
            alt="Line chart showing replay-adjusted pass rates for each team across sprints.",
        )

    st.subheader("Portfolio Scorecard")
    st.caption(
        f"Release Readiness Score (0–100): {RELEASE_READINESS_CRITICAL_DEFECT_POINTS} "
        f"points for no open critical defects, {RELEASE_READINESS_BLOCKER_POINTS} "
        f"for no active blockers, and up to {RELEASE_READINESS_PASS_RATE_POINTS} "
        f"for test pass rate (scaled to {RELEASE_READINESS_PASS_RATE:.0f}%)."
    )
    scorecard = metrics[
        [
            "name",
            "domain",
            "issue_count",
            "completion_rate",
            "defect_count",
            "open_defects",
            "critical_open_defects",
            "execution_count",
            "pass_rate",
            "release_readiness_score",
        ]
    ].rename(
        columns={
            "name": "Team",
            "domain": "Product Area",
            "issue_count": "Issues",
            "completion_rate": "Completion (%)",
            "defect_count": "Defects",
            "open_defects": "Open Defects",
            "critical_open_defects": "Open Critical",
            "execution_count": "Executions",
            "pass_rate": "Pass Rate (%)",
            "release_readiness_score": "Release Readiness Score",
        }
    )
    scorecard["Completion (%)"] = scorecard["Completion (%)"].map(
        lambda value: f"{value:.1f}%"
    )
    scorecard["Pass Rate (%)"] = scorecard["Pass Rate (%)"].map(
        lambda value: f"{value:.1f}%"
    )
    scorecard["Release Readiness Score"] = scorecard[
        "Release Readiness Score"
    ].map(lambda value: f"{value:.1f}%")
    st.dataframe(
        style_outcome_table(scorecard, score_column="Release Readiness Score"),
        hide_index=True,
        width="stretch",
        alt="Current issue completion, defect, and execution metrics for all QA teams.",
    )
    st.subheader("Recent Changes")
    show_recent_changes(data)


def show_team_details(data):
    metrics = build_team_metrics(data)
    teams = data["teams"]
    selected = st.selectbox(
        "Select a QA Team",
        teams,
        format_func=lambda team: f"{team['name']} — {team['domain']}",
    )
    team_id = selected["id"]
    team_metrics = metrics[metrics["id"] == team_id].iloc[0]
    st.title(f"{selected['name']} · {selected['domain']}")
    st.markdown(
        f":{TEAM_BADGE_COLORS[team_id]}-badge[{selected['name']}] "
        f":{TEAM_BADGE_COLORS[team_id]}[{selected['domain']}]"
    )

    team_cases = data["current"]["test_cases"]
    team_cases = team_cases[team_cases["team_id"] == team_id]
    cards = st.columns(5)
    cards[0].metric(
        "Issue Completion", f"{team_metrics['completion_rate']}%", border=True
    )
    cards[1].metric("Open Defects", int(team_metrics["open_defects"]), border=True)
    cards[2].metric(
        "Test Pass Rate", f"{team_metrics['pass_rate']:.1f}%", border=True
    )
    cards[3].metric(
        "Blocked Executions", int(team_metrics["blocked"]), border=True
    )
    cards[4].metric("Test Cases", len(team_cases), border=True)
    sprint_metrics = build_sprint_metrics(data, team_id)
    st.subheader("Sprint Pass Rate Trend")
    trend = go.Figure()
    trend.add_trace(
        go.Scatter(
            x=sprint_metrics["sprint_number"],
            y=sprint_metrics["baseline_pass_rate"],
            mode="lines+markers",
            name="Historical Baseline",
            line={"color": TEAM_COLORS[team_id], "dash": "dot"},
        )
    )
    trend.add_trace(
        go.Scatter(
            x=sprint_metrics["sprint_number"],
            y=sprint_metrics["pass_rate"],
            mode="lines+markers",
            name="Current After Replay",
            line={"color": TEAM_COLORS[team_id], "width": 3},
        )
    )
    trend.update_layout(
        xaxis_title="Sprint",
        yaxis_title="Test Pass Rate (%)",
        yaxis_ticksuffix="%",
        hovermode="x unified",
    )
    st.plotly_chart(
        trend,
        width="stretch",
        alt=f"Historical and replay-adjusted test pass rates for {selected['name']} across sprints.",
    )

    st.subheader("Sprint Metrics")
    sprint_table = sprint_metrics[
        [
            "sprint_number",
            "issue_count",
            "completion_rate",
            "defect_count",
            "open_defects",
            "passed",
            "failed",
            "blocked",
            "not_executed",
            "baseline_pass_rate",
            "pass_rate",
        ]
    ].rename(
        columns={
            "sprint_number": "Sprint",
            "issue_count": "Issues",
            "completion_rate": "Completion (%)",
            "defect_count": "Defects",
            "open_defects": "Open Defects",
            "passed": "Passed",
            "failed": "Failed",
            "blocked": "Blocked",
            "not_executed": "Not Executed",
            "baseline_pass_rate": "Baseline Pass Rate (%)",
            "pass_rate": "Current Pass Rate (%)",
        }
    )
    st.dataframe(
        style_outcome_table(
            sprint_table,
            failed_column="Failed",
            blocked_column="Blocked",
        ),
        hide_index=True,
        width="stretch",
        alt=f"Sprint-level issue, defect, and test execution metrics for {selected['name']}.",
    )

    current = data["current"]
    defects = current["issues"][
        (current["issues"]["team_id"] == team_id)
        & (current["issues"]["issue_type"] == "Bug")
    ]
    executions = current["executions"][current["executions"]["team_id"] == team_id]
    execution_table = executions[
        ["execution_id", "sprint_id", "test_id", "status", "executed_at"]
    ].copy()
    execution_table["status"] = execution_table["status"].map(status_for_display)
    defects_column, executions_column = st.columns(2)
    with defects_column:
        st.subheader("Defects")
        st.dataframe(
            style_outcome_table(
                defects[["issue_key", "sprint_id", "priority", "status", "summary"]],
                status_column="status",
            ),
            hide_index=True,
            width="stretch",
            alt=f"Defect records for {selected['name']}.",
        )
    with executions_column:
        st.subheader("Test Executions")
        st.dataframe(
            style_outcome_table(
                execution_table,
                status_column="status",
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "status": st.column_config.TextColumn(
                    "Outcome", width="medium"
                )
            },
            alt=f"Test execution records for {selected['name']}.",
        )


def show_simulation_center(data):
    st.title("Simulation Center")
    st.caption(
        "Changes Append To The Simulation Event Log. Historical CSVs And Snapshots Are Read-Only."
    )
    issue_tab, execution_tab = st.tabs(["Defect Status", "Test Execution Outcome"])

    with issue_tab:
        selected_team = st.selectbox(
            "Team",
            data["teams"],
            key="issue_team",
            format_func=lambda team: team["name"],
        )
        team_issues = data["current"]["issues"]
        team_issues = team_issues[
            (team_issues["team_id"] == selected_team["id"])
            & (team_issues["issue_type"] == "Bug")
        ]
        with st.form("issue_simulation"):
            issue_key = st.selectbox(
                "Defect",
                team_issues["issue_key"].tolist(),
                key=f"issue_key_{selected_team['id']}",
            )
            current_issue_status = team_issues.loc[
                team_issues["issue_key"] == issue_key, "status"
            ].iloc[0]
            st.caption(f"Current Status: {current_issue_status}")
            issue_status = st.selectbox("New Status", ["Open", "In Progress", "Done"])
            issue_note = st.text_input("Simulation Note", value="Manual dashboard simulation")
            issue_submitted = st.form_submit_button("Record Defect Change")
        if issue_submitted:
            try:
                event = record_simulation(
                    "issue",
                    issue_key,
                    issue_status,
                    issue_note,
                )
            except (OSError, ValueError) as exc:
                st.error(f"Could not record simulation: {exc}")
            else:
                st.success(
                    f"Recorded {event['target_id']} as {event['new_status']}."
                )
                st.session_state.pop("qa_portfolio_analysis", None)
                st.session_state.pop("qa_portfolio_analysis_evidence", None)
                st.cache_data.clear()
                st.rerun()

    with execution_tab:
        selected_team = st.selectbox(
            "Team",
            data["teams"],
            key="execution_team",
            format_func=lambda team: team["name"],
        )
        team_executions = data["current"]["executions"]
        team_executions = team_executions[
            team_executions["team_id"] == selected_team["id"]
        ]
        with st.form("execution_simulation"):
            execution_id = st.selectbox(
                "Test Execution",
                team_executions["execution_id"].tolist(),
                key=f"execution_id_{selected_team['id']}",
            )
            current_execution_status = team_executions.loc[
                team_executions["execution_id"] == execution_id, "status"
            ].iloc[0]
            st.caption(f"Current Outcome: {current_execution_status}")
            execution_status = st.selectbox(
                "New Outcome",
                ["PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"],
                format_func=lambda status: status.replace("_", " "),
            )
            execution_note = st.text_input(
                "Simulation Note",
                value="Manual dashboard simulation",
                key="execution_note",
            )
            execution_submitted = st.form_submit_button("Record Execution Change")
        if execution_submitted:
            try:
                event = record_simulation(
                    "execution",
                    execution_id,
                    execution_status,
                    execution_note,
                )
            except (OSError, ValueError) as exc:
                st.error(f"Could not record simulation: {exc}")
            else:
                st.success(
                    f"Recorded {event['target_id']} as {event['new_status']}."
                )
                st.session_state.pop("qa_portfolio_analysis", None)
                st.session_state.pop("qa_portfolio_analysis_evidence", None)
                st.cache_data.clear()
                st.rerun()

    st.subheader("Simulation Event History")
    show_recent_changes(data)


def executive_dashboard_page():
    show_executive_dashboard(get_dashboard_data())


def team_details_page():
    show_team_details(get_dashboard_data())


def ai_risk_analysis_page():
    show_ai_risk_analysis(get_dashboard_data())


def weekly_status_report_page():
    show_weekly_status_report(get_dashboard_data())


def simulation_center_page():
    show_simulation_center(get_dashboard_data())


def build_navigation_pages():
    return [
        st.Page(
            executive_dashboard_page,
            title="Executive Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            team_details_page,
            title="Team Details",
            icon=":material/groups:",
        ),
        st.Page(
            ai_risk_analysis_page,
            title="AI Risk Analysis",
            icon=":material/insights:",
        ),
        st.Page(
            weekly_status_report_page,
            title="Weekly Status Report",
            icon=":material/assessment:",
        ),
        st.Page(
            simulation_center_page,
            title="Simulation Center",
            icon=":material/science:",
        ),
    ]


def main():
    page = st.navigation(build_navigation_pages(), position="sidebar")
    page.run()


if __name__ == "__main__":
    main()
