"""Reusable outcome colors for dashboard tables."""

import pandas as pd
from pandas.io.formats.style import Styler

FAILURE_STYLE = "background-color: #FEE2E2; color: #991B1B; font-weight: 600"
BLOCKED_STYLE = "background-color: #FFEDD5; color: #9A3412; font-weight: 600"
SUCCESS_STYLE = "background-color: #DCFCE7; color: #166534; font-weight: 600"
NEUTRAL_STYLE = "background-color: #E2E8F0; color: #334155; font-weight: 600"
IN_PROGRESS_STYLE = "background-color: #DBEAFE; color: #1E40AF; font-weight: 600"

STATUS_STYLES = {
    "FAIL": FAILURE_STYLE,
    "BLOCKED": BLOCKED_STYLE,
    "PASS": SUCCESS_STYLE,
    "DONE": SUCCESS_STYLE,
    "OPEN": BLOCKED_STYLE,
    "IN PROGRESS": IN_PROGRESS_STYLE,
    "NOT_EXECUTED": NEUTRAL_STYLE,
    "NOT EXECUTED": NEUTRAL_STYLE,
}
STATUS_TEXT_COLORS = {
    "FAIL": "#991B1B",
    "BLOCKED": "#9A3412",
    "PASS": "#166534",
    "DONE": "#166534",
    "OPEN": "#9A3412",
    "IN PROGRESS": "#1E40AF",
    "NOT_EXECUTED": "#334155",
    "NOT EXECUTED": "#334155",
}


def status_for_display(value: object) -> object:
    """Replace internal status separators for a human-readable table label."""
    if not isinstance(value, str):
        return value
    return value.replace("_", " ")


def _status_style(value: object) -> str:
    if pd.isna(value):
        return ""
    return STATUS_STYLES.get(str(value).strip().upper(), "")


def _compact_status_style(value: object) -> str:
    if pd.isna(value):
        return ""
    color = STATUS_TEXT_COLORS.get(str(value).strip().upper())
    return f"color: {color}; font-weight: 600" if color else ""


def _score_text_style(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        score = float(str(value).strip().removesuffix("%"))
    except (TypeError, ValueError):
        return ""
    if score >= 80:
        color = "#166534"
    elif score >= 50:
        color = "#9A3412"
    else:
        color = "#991B1B"
    return f"color: {color}; font-weight: 600"


def _count_style(style: str):
    def apply(value: object) -> str:
        if pd.isna(value):
            return ""
        try:
            return style if float(value) > 0 else ""
        except (TypeError, ValueError):
            return ""

    return apply


def style_outcome_table(
    frame: pd.DataFrame,
    *,
    status_column: str | None = None,
    failed_column: str | None = None,
    blocked_column: str | None = None,
    score_column: str | None = None,
    compact_status: bool = False,
) -> Styler:
    """Apply semantic styles to status text and positive failure/block counts."""
    styled = frame.style
    if status_column is not None:
        style_status = _compact_status_style if compact_status else _status_style
        styled = styled.map(style_status, subset=[status_column])
    if failed_column is not None:
        styled = styled.map(
            _count_style(FAILURE_STYLE), subset=[failed_column]
        )
    if blocked_column is not None:
        styled = styled.map(
            _count_style(BLOCKED_STYLE), subset=[blocked_column]
        )
    if score_column is not None:
        styled = styled.map(_score_text_style, subset=[score_column])
    return styled


def style_outcome_deltas(
    frame: pd.DataFrame,
    *,
    failed_column: str | None = None,
    blocked_column: str | None = None,
) -> Styler:
    """Highlight rising adverse counts and use green for reductions."""

    def delta_style(value: object, adverse_style: str) -> str:
        if pd.isna(value):
            return ""
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return ""
        if numeric_value > 0:
            return adverse_style
        if numeric_value < 0:
            return SUCCESS_STYLE
        return ""

    styled = frame.style
    if failed_column is not None:
        styled = styled.map(
            lambda value: delta_style(value, FAILURE_STYLE),
            subset=[failed_column],
        )
    if blocked_column is not None:
        styled = styled.map(
            lambda value: delta_style(value, BLOCKED_STYLE),
            subset=[blocked_column],
        )
    return styled
