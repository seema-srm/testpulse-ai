import pandas as pd

from scripts.table_styling import (
    status_for_display,
    style_outcome_deltas,
    style_outcome_table,
)


def test_status_labels_use_spaces_without_mutating_internal_statuses():
    assert status_for_display("NOT_EXECUTED") == "NOT EXECUTED"
    assert status_for_display("PASS") == "PASS"
    assert status_for_display(None) is None


def styles_by_cell(styler):
    return {
        cell: dict(styles)
        for cell, styles in styler._compute().ctx.items()
    }


def test_outcome_table_colors_failed_blocked_and_passed_values():
    frame = pd.DataFrame(
        {
            "Outcome": ["FAIL", "BLOCKED", "PASS"],
            "Failed": [1, 0, 0],
            "Blocked": [0, 1, 0],
        }
    )

    styles = styles_by_cell(
        style_outcome_table(
            frame,
            status_column="Outcome",
            failed_column="Failed",
            blocked_column="Blocked",
        )
    )

    assert styles[(0, 0)]["background-color"] == "#FEE2E2"
    assert styles[(1, 0)]["background-color"] == "#FFEDD5"
    assert styles[(2, 0)]["background-color"] == "#DCFCE7"
    assert styles[(0, 1)]["background-color"] == "#FEE2E2"
    assert styles[(1, 2)]["background-color"] == "#FFEDD5"
    assert (2, 1) not in styles
    assert (2, 2) not in styles
    assert frame.loc[0, "Outcome"] == "FAIL"


def test_defect_status_table_colors_open_in_progress_and_done():
    frame = pd.DataFrame({"Status": ["Open", "In Progress", "Done"]})

    styles = styles_by_cell(
        style_outcome_table(frame, status_column="Status")
    )

    assert styles[(0, 0)]["background-color"] == "#FFEDD5"
    assert styles[(1, 0)]["background-color"] == "#DBEAFE"
    assert styles[(2, 0)]["background-color"] == "#DCFCE7"


def test_compact_status_style_uses_colored_text_without_cell_fill():
    frame = pd.DataFrame({"Status": ["Open", "In Progress", "Done"]})

    styles = styles_by_cell(
        style_outcome_table(
            frame,
            status_column="Status",
            compact_status=True,
        )
    )

    assert styles[(0, 0)]["color"] == "#9A3412"
    assert styles[(1, 0)]["color"] == "#1E40AF"
    assert styles[(2, 0)]["color"] == "#166534"


def test_readiness_score_uses_colored_text_for_score_bands():
    frame = pd.DataFrame({"Score": [40, 65, 90]})
    styles = styles_by_cell(style_outcome_table(frame, score_column="Score"))

    assert styles[(0, 0)]["color"] == "#991B1B"
    assert styles[(1, 0)]["color"] == "#9A3412"
    assert styles[(2, 0)]["color"] == "#166534"
    assert all("background-color" not in cell_style for cell_style in styles.values())


def test_adverse_outcome_deltas_use_red_and_green():
    frame = pd.DataFrame({"Failed": [2, -1, 0], "Blocked": [1, -3, 0]})

    styles = styles_by_cell(
        style_outcome_deltas(
            frame,
            failed_column="Failed",
            blocked_column="Blocked",
        )
    )

    assert styles[(0, 0)]["background-color"] == "#FEE2E2"
    assert styles[(1, 0)]["background-color"] == "#DCFCE7"
    assert styles[(0, 1)]["background-color"] == "#FFEDD5"
    assert styles[(1, 1)]["background-color"] == "#DCFCE7"
    assert (2, 0) not in styles
    assert (2, 1) not in styles
