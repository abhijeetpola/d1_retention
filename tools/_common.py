"""Shared helpers, constants, and the FastMCP server instance.

Every tool file in this folder imports `server` from here and decorates with
`@server.tool(...)`. The aggregator at `tune_mcp.py` triggers those imports.

PMs writing a new tool file: you almost never need to change anything in this
file. You import the helpers (get_rows / aggregate / cohort_rate / delta_pp /
filter_window) and use them in your new tool. If you need a helper that
doesn't exist, fill out the request.md template at the project root.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from mcp.server.fastmcp import FastMCP

# tools/_common.py is one level below project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = (PROJECT_ROOT / "data").resolve()
SHEET_PATH = (DATA_DIR / "sheets" / "d1_retention.csv").resolve()

# The single FastMCP instance every tool registers against.
server = FastMCP(name="sandbox")


# ---------------------------------------------------------------------------
# Shared constants — used across multiple tool files.
# ---------------------------------------------------------------------------

VALID_PLATFORMS: tuple[str, ...] = ("android", "ios")
VALID_SOURCES: tuple[str, ...] = ("organic", "paid", "WTA", "others", "All")
MIX_SOURCES: tuple[str, ...] = ("organic", "paid", "WTA", "others")  # excludes "All"

# For list_files / load_file description parsing.
_DESC_RE = re.compile(r"<!--\s*desc:\s*(.+?)\s*-->", re.IGNORECASE)
_BUILTIN_DESCS: dict[str, str] = {
    "sheets/d1_retention.csv": (
        "Daily retention sheet — 50 cols × all platforms × all acquisition "
        "sources × dates from 2025-05-01. Prefer `get_rows(...)` for "
        "targeted slices; load this whole file only when you need the full "
        "breakdown or older history `get_rows` cannot reach."
    ),
}


# ---------------------------------------------------------------------------
# Sheet loading + caching.
# The MCP server is short-lived (one subprocess per ./tune invocation), so a
# process-lifetime cache is enough.
# ---------------------------------------------------------------------------

_SHEET_CACHE: pd.DataFrame | None = None


def sheet() -> pd.DataFrame:
    """Return the full retention sheet as a DataFrame, cached after first read."""
    global _SHEET_CACHE
    if _SHEET_CACHE is None:
        df = pd.read_csv(SHEET_PATH, thousands=",", low_memory=False)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        _SHEET_CACHE = df
    return _SHEET_CACHE


def coerce_metric(s: pd.Series) -> pd.Series:
    """Coerce a metric column to float; non-numeric values (e.g. '#DIV/0!') become NaN."""
    return pd.to_numeric(s, errors="coerce")


def validate_segment(platform: str, acquisition_source: str) -> str | None:
    """Return an error message if (platform, acquisition_source) is invalid; else None."""
    if platform not in VALID_PLATFORMS:
        return f"platform must be one of {VALID_PLATFORMS}, got {platform!r}"
    if acquisition_source not in VALID_SOURCES:
        return (
            f"acquisition_source must be one of {VALID_SOURCES}, "
            f"got {acquisition_source!r}"
        )
    return None


# ---------------------------------------------------------------------------
# PM-friendly helpers. These are what new tool files should use.
# ---------------------------------------------------------------------------


def get_rows(
    *,
    platform: str | None = None,
    acquisition_source: str | None = None,
    date_from: str | pd.Timestamp | None = None,
    date_to: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return rows from the retention sheet, optionally filtered.

    All parameters are optional. Pass any combination of platform,
    acquisition_source, and a date window. Dates can be strings ('2026-04-01')
    or pandas Timestamps. The returned frame is a copy you can edit safely.

    Example:
        rows = get_rows(platform="android", acquisition_source="organic",
                        date_from="2026-04-01", date_to="2026-04-07")
    """
    df = sheet()
    mask = pd.Series(True, index=df.index)
    if platform is not None:
        mask &= df["platform"] == platform
    if acquisition_source is not None:
        mask &= df["acquisition_source"] == acquisition_source
    if date_from is not None:
        d = pd.to_datetime(date_from, errors="coerce")
        if pd.isna(d):
            raise ValueError(f"date_from not parseable: {date_from!r}")
        mask &= df["date"] >= d
    if date_to is not None:
        d = pd.to_datetime(date_to, errors="coerce")
        if pd.isna(d):
            raise ValueError(f"date_to not parseable: {date_to!r}")
        mask &= df["date"] <= d
    return df.loc[mask].copy()


def aggregate(
    rows: pd.DataFrame,
    column: str,
    kind: str = "sum",
) -> float | None:
    """Aggregate `column` across `rows`. Returns a scalar.

    `kind` is one of: 'sum', 'mean', 'median', 'count', 'min', 'max'.
    Non-numeric values (#DIV/0!, blanks) are ignored. Returns None if no
    numeric values are available.

    Example:
        total_installs = aggregate(rows, "installs", "sum")
        avg_d1 = aggregate(rows, "d1_corrected", "mean")
    """
    if column not in rows.columns:
        raise KeyError(f"column not in rows: {column!r}")
    values = coerce_metric(rows[column]).dropna()
    if values.empty:
        return None
    if kind == "sum":
        return float(values.sum())
    if kind == "mean":
        return float(values.mean())
    if kind == "median":
        return float(values.median())
    if kind == "count":
        return int(values.size)
    if kind == "min":
        return float(values.min())
    if kind == "max":
        return float(values.max())
    raise ValueError(
        f"kind must be one of sum/mean/median/count/min/max, got {kind!r}"
    )


def cohort_rate(
    rows: pd.DataFrame,
    users_col: str,
    installs_col: str,
) -> float | None:
    """Return the cohort-aggregated retention rate across `rows`.

    Computes sum(users_col) / sum(installs_col) — the methodology-correct way
    to compute weekly or monthly retention. Do NOT use mean() of a daily-rate
    column for periodic retention; that gives biased numbers (the methodology
    rule is documented in retention_methodology.md).

    Returns the rate as a fraction (0.276 = 27.6%). Returns None if there are
    no installs in the window.

    Example:
        monthly_d1 = cohort_rate(april_rows,
                                 users_col="d1_users",
                                 installs_col="d1_installs")
    """
    users = aggregate(rows, users_col, "sum")
    installs = aggregate(rows, installs_col, "sum")
    if users is None or installs is None or installs == 0:
        return None
    return float(users) / float(installs)


def delta_pp(today_value: float | None, baseline_value: float | None) -> float | None:
    """Return the percentage-point delta of today_value vs baseline_value.

    Both inputs are expected as fractions (0.293, not 29.3). Multiplies the
    difference by 100 and rounds to 2 decimals. Returns None if either input
    is None.

    Example:
        opt_in_change = delta_pp(today_opt_in, trailing_mean_opt_in)
        # 0.565 vs 0.609 → -4.4 (pp)
    """
    if today_value is None or baseline_value is None:
        return None
    return round((float(today_value) - float(baseline_value)) * 100.0, 2)


def filter_window(
    df: pd.DataFrame,
    end_date: str | pd.Timestamp,
    days: int,
) -> pd.DataFrame:
    """Return rows of `df` whose `date` falls in [end_date - (days-1), end_date].

    Useful for trailing windows (e.g. trailing 7 days). The returned frame is
    a copy. The window is inclusive on both ends.

    Example:
        trailing_7d = filter_window(android_organic_rows, "2026-04-15", 7)
    """
    if days <= 0:
        raise ValueError(f"days must be > 0, got {days}")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(end):
        raise ValueError(f"end_date not parseable: {end_date!r}")
    start = end - pd.Timedelta(days=days - 1)
    return df.loc[(df["date"] >= start) & (df["date"] <= end)].copy()


# ---------------------------------------------------------------------------
# File access helpers — used by list_files / load_file.
# Path-traversal protected: every read resolves under DATA_DIR or is rejected.
# ---------------------------------------------------------------------------


def safe_resolve(filename: str) -> Path | None:
    """Resolve `filename` relative to DATA_DIR; return None if it escapes."""
    if filename.startswith(("/", "~")):
        return None
    candidate = (DATA_DIR / filename).resolve()
    try:
        candidate.relative_to(DATA_DIR)
    except ValueError:
        return None
    return candidate


def render_table(path: Path, *, sep: str = ",", excel: bool = False) -> str:
    """Render a CSV/TSV/XLSX file as a Markdown table with a one-line header."""
    if excel:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path, sep=sep, thousands=",")
    rows, cols = df.shape
    header = (
        f"_{path.name}: {rows:,} rows × {cols} columns_\n\n"
        if rows > 0
        else f"_{path.name}: empty file_\n\n"
    )
    return header + df.to_markdown(index=False)


def extract_description(path: Path) -> str:
    """Return a one-line description for `path`.

    Order: builtin map → first-line `<!-- desc: ... -->` → first H1 within
    the first 6 lines → empty string.
    """
    rel = str(path.relative_to(DATA_DIR))
    if rel in _BUILTIN_DESCS:
        return _BUILTIN_DESCS[rel]
    if path.suffix.lower() not in (".md", ".txt"):
        return ""
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for _ in range(6):
                line = f.readline()
                if not line:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                m = _DESC_RE.search(stripped)
                if m:
                    return m.group(1)
                if stripped.startswith("# "):
                    return stripped[2:].strip()
    except OSError:
        pass
    return ""
