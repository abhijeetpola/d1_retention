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

from pathlib import Path
from typing import Any

import pandas as pd

from tools._common import (
    DATA_DIR,
    PRIMARY_SHEET,
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


# Per-process cache of dictionary contents so we read each pivot dictionary
# at most once per `tune` invocation, even if the LLM calls get_rows on the
# same pivot multiple times.
_DICT_CACHE: dict[str, str] = {}


def _load_dictionary_for(sheet_name: str) -> tuple[str | None, str]:
    """Return (dictionary_path, dictionary_md) for a non-primary sheet.

    Returns (None, "") if the sheet has no dictionary registered or the file
    is missing. The path is the registry-declared one (relative to data/);
    the markdown is the file content.

    The primary sheet's dictionary is loaded into the prompt at preflight
    (in `tune`), so it is NOT bundled here — that would double-cost tokens.
    Pivot dictionaries are bundled because the LLM does not see them
    otherwise, and the substitution failures we have observed (count vs
    rate) come from the LLM lacking column-level semantics.
    """
    from tools._sheet_store import _load_registry  # local import to avoid cycles

    if sheet_name == PRIMARY_SHEET:
        return None, ""

    try:
        reg = _load_registry()
    except Exception:  # noqa: BLE001
        return None, ""

    entry = reg.get("tabs", {}).get(sheet_name) or {}
    rel = entry.get("dictionary")
    if not rel:
        return None, ""

    if rel in _DICT_CACHE:
        return rel, _DICT_CACHE[rel]

    candidate = (DATA_DIR / rel).resolve()
    try:
        candidate.relative_to(DATA_DIR)
    except ValueError:
        return rel, ""

    if not candidate.exists():
        return rel, ""

    try:
        content = candidate.read_text(encoding="utf-8")
    except OSError:
        return rel, ""

    _DICT_CACHE[rel] = content
    return rel, content


@server.tool(
    description=(
        "Fetch raw rows from a registered sheet for a chosen segment and "
        "(optional) date window. Use this when the PM's question is 'show me "
        "the data' rather than 'compute one number'. "
        "Default sheet is the primary daily fact table (`app_health_daily`). "
        "Pass sheet='app_d1_retention_health_daily' / `_weekly` / `_monthly` "
        "to read a cohort pivot instead — call `list_sheets()` to discover "
        "what is registered. "
        "Window resolution rules (only apply to sheets that have a `date` "
        "column): "
        "(a) if date_from AND date_to are both given, that range is used; "
        "(b) if only date_to + days, window = [date_to - days + 1, date_to]; "
        "(c) if only date_from + days, window = [date_from, date_from + days - 1]; "
        "(d) if only days, window = the most recent `days` days in the sheet; "
        "(e) if nothing is given, defaults to the last 30 days. "
        "For sheets WITHOUT a `date` column (the weekly/monthly pivots use "
        "`week` / `month` time buckets instead), the date-window parameters "
        "are ignored and all rows are returned (subject to the 400-row cap). "
        "Filter by `platform` and `acquisition_source` only if those columns "
        "exist on the chosen sheet. "
        "Hard cap: 400 rows. If the requested window would return more, the "
        "tool refuses and returns ok=false with a hint to narrow. "
        "On the primary sheet, the default column projection covers the most "
        "common diagnostic columns. On non-primary sheets, all columns are "
        "returned by default. Pass columns=[...] to override on either case. "
        "Returns {ok, sheet, date_from, date_to, platform, acquisition_source, "
        "row_count, columns, rows: [{col: value, ...}, ...], dictionary_path, "
        "dictionary_md}. For non-primary sheets, dictionary_md carries the "
        "full column reference for that pivot — read it before interpreting "
        "the rows so you do not confuse counts with rates. The primary "
        "sheet's dictionary is in your prompt under '# Primary sheet — column "
        "dictionary' and is NOT bundled here (would double-cost tokens)."
    )
)
def get_rows(
    sheet: str = PRIMARY_SHEET,
    platform: str | None = None,
    acquisition_source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    days: int | None = None,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    from tools._sheet_store import _resolve_alias

    try:
        canonical = _resolve_alias(sheet)
    except KeyError as e:
        return {"ok": False, "error": str(e)}

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

    df = _sheet_loader(canonical)
    has_date = "date" in df.columns

    # ----- Resolve the date window (only when the sheet has a date column) -----
    win_from = win_to = None
    if has_date:
        sheet_max = df["date"].max()
        parsed_from = pd.to_datetime(date_from, errors="coerce") if date_from else None
        parsed_to = pd.to_datetime(date_to, errors="coerce") if date_to else None
        if date_from and pd.isna(parsed_from):
            return {"ok": False, "error": f"date_from not parseable: {date_from!r}"}
        if date_to and pd.isna(parsed_to):
            return {"ok": False, "error": f"date_to not parseable: {date_to!r}"}

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

    # ----- Resolve the column projection -----
    if columns:
        cols = list(columns)
    elif canonical == PRIMARY_SHEET:
        cols = [c for c in _DEFAULT_COLUMNS if c in df.columns]
    else:
        cols = list(df.columns)

    missing = [c for c in cols if c not in df.columns]
    if missing:
        return {
            "ok": False,
            "error": f"unknown column(s) on sheet {canonical!r}: {missing}",
            "hint": (
                f"Use column names that appear on this sheet. Available: "
                f"{list(df.columns)}."
            ),
        }

    # ----- Pull rows via the helper -----
    rows = _get_rows_helper(
        sheet_name=canonical,
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
                "acquisition_source."
            ),
        }

    if has_date:
        rows = rows.sort_values("date").reset_index(drop=True)
        rows["date"] = rows["date"].dt.strftime("%Y-%m-%d")
    projected = rows[cols].copy()

    # Convert NaN → None so the JSON payload is clean for the LLM.
    records = projected.where(pd.notna(projected), None).to_dict(orient="records")

    # Pivot dictionaries travel with the data so the LLM has column-level
    # semantics in the same payload as the rows. Primary's dictionary is in
    # the prompt already, so it is NOT bundled here. See _load_dictionary_for.
    dict_path, dict_md = _load_dictionary_for(canonical)

    return {
        "ok": True,
        "sheet": canonical,
        "date_from": str(win_from.date()) if win_from is not None else None,
        "date_to": str(win_to.date()) if win_to is not None else None,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "row_count": len(records),
        "columns": cols,
        "rows": records,
        "dictionary_path": dict_path,
        "dictionary_md": dict_md or None,
    }


def _sheet_loader(name: str) -> pd.DataFrame:
    """Indirection for the test seam — calls the cached `sheet()` helper."""
    return sheet(name)
