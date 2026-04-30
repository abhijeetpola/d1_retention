"""Tool: get_rows — fetch raw daily rows for a chosen segment and date window.

This is the LLM's escape hatch when the question is "show me the data" rather
than "compute one number." It pulls a slice of the retention sheet by
platform / acquisition_source / date window, with opinionated defaults so the
LLM cannot accidentally pull the whole sheet.

Constraints baked in:
  - 30-day default window if no dates / days are passed.
  - 400-row hard cap; the tool refuses larger pulls with a hint to narrow.
  - Standard 11-column projection by default; the LLM has to name extra
    columns explicitly.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools._common import (
    VALID_PLATFORMS,
    VALID_SOURCES,
    get_rows as _get_rows_helper,
    sheet,
    server,
)

# Standard projection — what most diagnostics need without the full 50-column
# sheet. The LLM can pass `columns=[...]` to override.
_DEFAULT_COLUMNS: tuple[str, ...] = (
    "date",
    "platform",
    "acquisition_source",
    "dau",
    "installs",
    "d1",
    "d1_corrected",
    "d0_uninstalls",
    "pct_d0_notification_opt_in",
    "pct_d0_login",
    "avg_engagement_time_per_user",
)

_DEFAULT_DAYS = 30
_MAX_ROWS = 400


@server.tool(
    description=(
        "Fetch raw daily rows for a chosen segment and date window. Use this "
        "when the PM's question is 'show me the data' — e.g. 'D1 each day for "
        "iOS paid in February' or 'compare Android organic last 30 days vs "
        "prior 30'. Do NOT use this when one number suffices "
        "(use compute_rolling_average / compare_to_baseline instead). "
        "Window resolution rules: "
        "(a) if date_from AND date_to are both given, that range is used; "
        "(b) if only date_to + days, window = [date_to - days + 1, date_to]; "
        "(c) if only date_from + days, window = [date_from, date_from + days - 1]; "
        "(d) if only days, window = the most recent `days` days in the sheet; "
        "(e) if nothing is given, defaults to the last 30 days. "
        "Hard cap: 400 rows. If the requested window would return more, the "
        "tool refuses and returns ok=false with a hint to narrow. "
        "Default columns: date, platform, acquisition_source, dau, installs, "
        "d1, d1_corrected, d0_uninstalls, pct_d0_notification_opt_in, "
        "pct_d0_login, avg_engagement_time_per_user. Pass columns=[...] to "
        "override (must be valid column names from the sheet). "
        "Returns {ok, date_from, date_to, platform, acquisition_source, "
        "row_count, columns, rows: [{col: value, ...}, ...]}."
    )
)
def get_rows(
    platform: str | None = None,
    acquisition_source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    days: int | None = None,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    if platform is not None and platform not in VALID_PLATFORMS:
        return {
            "ok": False,
            "error": f"platform must be one of {VALID_PLATFORMS} or null, got {platform!r}",
        }
    if acquisition_source is not None and acquisition_source not in VALID_SOURCES:
        return {
            "ok": False,
            "error": (
                f"acquisition_source must be one of {VALID_SOURCES} or null, "
                f"got {acquisition_source!r}"
            ),
        }
    if days is not None and days <= 0:
        return {"ok": False, "error": f"days must be > 0, got {days}"}

    df = sheet()
    sheet_max = df["date"].max()

    parsed_from = pd.to_datetime(date_from, errors="coerce") if date_from else None
    parsed_to = pd.to_datetime(date_to, errors="coerce") if date_to else None
    if date_from and pd.isna(parsed_from):
        return {"ok": False, "error": f"date_from not parseable: {date_from!r}"}
    if date_to and pd.isna(parsed_to):
        return {"ok": False, "error": f"date_to not parseable: {date_to!r}"}

    # Resolve the window per the rules in the docstring.
    if parsed_from is not None and parsed_to is not None:
        win_from, win_to = parsed_from, parsed_to
    elif parsed_to is not None and days is not None:
        win_to = parsed_to
        win_from = win_to - pd.Timedelta(days=days - 1)
    elif parsed_from is not None and days is not None:
        win_from = parsed_from
        win_to = win_from + pd.Timedelta(days=days - 1)
    elif days is not None:
        win_to = sheet_max
        win_from = win_to - pd.Timedelta(days=days - 1)
    elif parsed_from is not None:
        win_from = parsed_from
        win_to = sheet_max
    elif parsed_to is not None:
        win_to = parsed_to
        win_from = win_to - pd.Timedelta(days=_DEFAULT_DAYS - 1)
    else:
        win_to = sheet_max
        win_from = win_to - pd.Timedelta(days=_DEFAULT_DAYS - 1)

    if win_from > win_to:
        return {
            "ok": False,
            "error": (
                f"resolved window is empty: date_from={win_from.date()} > "
                f"date_to={win_to.date()}"
            ),
        }

    # Validate columns up front.
    cols = list(columns) if columns else list(_DEFAULT_COLUMNS)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return {
            "ok": False,
            "error": f"unknown column(s): {missing}",
            "hint": (
                "Use a column name that appears in the sheet. The default "
                f"projection is {list(_DEFAULT_COLUMNS)}. For the full list, "
                "call load_file('sheets/d1_retention.csv') and read the header."
            ),
        }

    rows = _get_rows_helper(
        platform=platform,
        acquisition_source=acquisition_source,
        date_from=win_from,
        date_to=win_to,
    )

    if len(rows) > _MAX_ROWS:
        return {
            "ok": False,
            "error": (
                f"requested window would return {len(rows)} rows, exceeds the "
                f"{_MAX_ROWS}-row cap"
            ),
            "hint": (
                "Narrow the window with a smaller `days` or a tighter "
                "[date_from, date_to] range, or filter by platform / "
                "acquisition_source. If you genuinely need more, call "
                "load_file('sheets/d1_retention.csv')."
            ),
        }

    rows = rows.sort_values("date").reset_index(drop=True)
    rows["date"] = rows["date"].dt.strftime("%Y-%m-%d")
    projected = rows[cols].copy()

    # Convert NaN → None so the JSON payload is clean for the LLM.
    records = projected.where(pd.notna(projected), None).to_dict(orient="records")

    return {
        "ok": True,
        "date_from": str(win_from.date()),
        "date_to": str(win_to.date()),
        "platform": platform,
        "acquisition_source": acquisition_source,
        "row_count": len(records),
        "columns": cols,
        "rows": records,
    }
