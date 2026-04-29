"""MCP server for the PM tuning sandbox.

Tools the LLM can call mid-reasoning:

File access:
  - list_files()             — see what's in the sandbox folder
  - load_file(filename)      — read one file by relative path

Deterministic D1 retention math (the LLM uses these instead of computing
averages or applying thresholds itself):
  - compute_rolling_average  — rolling average for one date with caller-chosen window
  - compute_stable_baseline  — IQR-cleaned, day-of-week-grouped baseline
  - compare_to_baseline      — delta of a date vs stable baseline (or rolling-7)
  - flag_dip_days            — list of days that crossed the dip threshold
  - compute_signals_for_day  — 8-step diagnostic signals for one flagged day

Path-traversal protected: every file read resolves under DATA_DIR or is rejected.

Launched as a subprocess by `./tune` via:
    python tune_mcp.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = (PROJECT_ROOT / "data").resolve()
SHEET_PATH = (DATA_DIR / "sheets" / "d1_retention.csv").resolve()

server = FastMCP(name="sandbox")

# Cache the full sheet on first read; the MCP server is short-lived (one
# subprocess per ./tune invocation), so a process-lifetime cache is fine.
_SHEET_CACHE: pd.DataFrame | None = None


def _sheet() -> pd.DataFrame:
    global _SHEET_CACHE
    if _SHEET_CACHE is None:
        df = pd.read_csv(SHEET_PATH, thousands=",", low_memory=False)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        _SHEET_CACHE = df
    return _SHEET_CACHE


def _filter_sheet(platform: str, acquisition_source: str) -> pd.DataFrame:
    df = _sheet()
    return df[
        (df["platform"] == platform)
        & (df["acquisition_source"] == acquisition_source)
    ].copy()


def _coerce_metric(s: pd.Series) -> pd.Series:
    """Coerce a metric column to float, treating non-numeric (#DIV/0! etc.) as NaN."""
    return pd.to_numeric(s, errors="coerce")


@server.tool(
    description=(
        "List every file available in the sandbox data folder, each with a "
        "one-line description of its purpose. Returns "
        "{'files': [{'path': '<relative path>', 'desc': '<one-line description>'}, ...]}. "
        "Use the description to decide which files are worth loading via load_file('<path>'). "
        "Empty desc means the file did not declare one."
    )
)
def list_files() -> dict[str, list[dict[str, str]]]:
    if not DATA_DIR.exists():
        return {"files": []}
    items: list[dict[str, str]] = []
    for p in sorted(DATA_DIR.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        items.append(
            {
                "path": str(p.relative_to(DATA_DIR)),
                "desc": _extract_description(p),
            }
        )
    return {"files": items}


_DESC_RE = re.compile(r"<!--\s*desc:\s*(.+?)\s*-->", re.IGNORECASE)
_BUILTIN_DESCS: dict[str, str] = {
    "sheets/d1_retention.csv": (
        "Daily retention sheet — 50 cols × all platforms × all acquisition "
        "sources × dates from 2025-05-01. Pre-loaded slice in the prompt is "
        "the 'All' source for the last 180 days; load this file for "
        "per-source breakdowns or older history."
    ),
}


def _extract_description(path: Path) -> str:
    """Best-effort one-line description for `path`.

    Order: builtin map → first-line `<!-- desc: ... -->` → first H1 within first
    6 lines → empty string.
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


@server.tool(
    description=(
        "Load one file from the sandbox data folder. "
        "Supported types: .csv, .tsv, .xlsx, .md, .txt, .json, .yaml, .yml. "
        "CSV/TSV/XLSX are rendered as Markdown tables. Other types are returned "
        "as text. The filename is relative to the data/ folder, e.g. "
        "'docs/causal_doc.md' or 'sheets/d1_retention.csv'."
    )
)
def load_file(filename: str) -> dict[str, Any]:
    target = _safe_resolve(filename)
    if target is None:
        return {
            "ok": False,
            "error": (
                f"refusing to load {filename!r}: must be a relative path "
                f"that stays within data/. Try list_files() to see what is "
                f"available."
            ),
        }
    if not target.exists():
        available = list_files()["files"]
        return {
            "ok": False,
            "error": f"file not found: {filename!r}",
            "available": available,
        }
    if not target.is_file():
        return {"ok": False, "error": f"not a file: {filename!r}"}

    suffix = target.suffix.lower()
    try:
        if suffix in (".csv", ".tsv"):
            content = _render_table(target, sep="\t" if suffix == ".tsv" else ",")
        elif suffix == ".xlsx":
            content = _render_table(target, excel=True)
        elif suffix in (".md", ".txt"):
            content = target.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".json":
            content = json.dumps(
                json.loads(target.read_text(encoding="utf-8")), indent=2
            )
        elif suffix in (".yaml", ".yml"):
            content = target.read_text(encoding="utf-8", errors="replace")
        else:
            return {"ok": False, "error": f"unsupported file type: {suffix}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return {"ok": True, "filename": filename, "content": content}


def _safe_resolve(filename: str) -> Path | None:
    """Resolve `filename` relative to DATA_DIR; return None if it escapes."""
    if filename.startswith(("/", "~")):
        return None
    candidate = (DATA_DIR / filename).resolve()
    try:
        candidate.relative_to(DATA_DIR)
    except ValueError:
        return None
    return candidate


def _render_table(path: Path, *, sep: str = ",", excel: bool = False) -> str:
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


# ---------------------------------------------------------------------------
# Deterministic D1 retention math — exposed as MCP tools.
#
# Every tool takes the metric / platform / acquisition_source explicitly so the
# LLM can compute against any segment, not just the inlined slice.
# ---------------------------------------------------------------------------


_VALID_PLATFORMS = ("android", "ios")
_VALID_SOURCES = ("organic", "paid", "WTA", "others", "All")


def _validate_segment(platform: str, acquisition_source: str) -> str | None:
    if platform not in _VALID_PLATFORMS:
        return f"platform must be one of {_VALID_PLATFORMS}, got {platform!r}"
    if acquisition_source not in _VALID_SOURCES:
        return f"acquisition_source must be one of {_VALID_SOURCES}, got {acquisition_source!r}"
    return None


@server.tool(
    description=(
        "Compute the rolling average of `metric` over `window_days` ending on "
        "`end_date` (inclusive) for one platform × acquisition_source segment. "
        "Use this whenever you need a 7-day or any-N-day rolling average — do "
        "not derive it yourself. Returns "
        "{ok, metric, platform, acquisition_source, end_date, window_days, "
        "average, n_observations}. Set window_days=7 for the standard 7-day "
        "rolling baseline used in the dip threshold rules."
    )
)
def compute_rolling_average(
    metric: str,
    platform: str,
    acquisition_source: str,
    end_date: str,
    window_days: int = 7,
) -> dict[str, Any]:
    err = _validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}
    if window_days <= 0:
        return {"ok": False, "error": f"window_days must be > 0, got {window_days}"}

    df = _filter_sheet(platform, acquisition_source)
    if metric not in df.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}

    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(end):
        return {"ok": False, "error": f"end_date not parseable: {end_date!r}"}

    start = end - pd.Timedelta(days=window_days - 1)
    window = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    values = _coerce_metric(window[metric]).dropna()
    if values.empty:
        return {
            "ok": False,
            "error": (
                f"no values for metric={metric} in {start.date()}..{end.date()} "
                f"({platform} / {acquisition_source})"
            ),
        }
    return {
        "ok": True,
        "metric": metric,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "end_date": str(end.date()),
        "start_date": str(start.date()),
        "window_days": window_days,
        "average": round(float(values.mean()), 6),
        "n_observations": int(values.size),
    }


@server.tool(
    description=(
        "Compute the stable baseline for `metric` on the chosen segment. "
        "Methodology: take all values from `baseline_start_date` up to the "
        "latest available date; optionally restrict to one weekday (Monday "
        "through Sunday); optionally remove IQR outliers (Q1−1.5×IQR, "
        "Q3+1.5×IQR). Returns the mean of clean values. "
        "Defaults match the PM's documented methodology. "
        "weekday accepts case-insensitive names like 'monday' or None for all. "
        "Returns {ok, metric, platform, acquisition_source, weekday, "
        "baseline_start_date, baseline, n_observations, outliers_removed}."
    )
)
def compute_stable_baseline(
    metric: str,
    platform: str,
    acquisition_source: str,
    weekday: str | None = None,
    baseline_start_date: str = "2026-01-01",
    exclude_outliers_iqr: bool = True,
) -> dict[str, Any]:
    err = _validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}

    df = _filter_sheet(platform, acquisition_source)
    if metric not in df.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}

    start = pd.to_datetime(baseline_start_date, errors="coerce")
    if pd.isna(start):
        return {
            "ok": False,
            "error": f"baseline_start_date not parseable: {baseline_start_date!r}",
        }
    df = df[df["date"] >= start].copy()
    df["__metric"] = _coerce_metric(df[metric])
    df = df.dropna(subset=["__metric"])

    weekday_name = None
    if weekday:
        target = weekday.strip().lower()
        valid = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        if target not in valid:
            return {"ok": False, "error": f"weekday must be a name like 'monday', got {weekday!r}"}
        df_weekday = df[df["date"].dt.weekday == valid[target]]
        weekday_name = target
        # Fallback per the PM methodology: if fewer than 4 values for that
        # weekday, fall back to all weekdays.
        if len(df_weekday) >= 4:
            df = df_weekday
        else:
            weekday_name = f"{target} (fallback: all weekdays — only {len(df_weekday)} {target} obs)"

    values = df["__metric"].astype(float)
    if values.empty:
        return {
            "ok": False,
            "error": (
                f"no values for metric={metric} since {start.date()} "
                f"({platform} / {acquisition_source})"
            ),
        }

    outliers_removed = 0
    # Skip outlier removal if too few values per the PM methodology.
    if exclude_outliers_iqr and len(values) >= 8:
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        kept = values[(values >= lo) & (values <= hi)]
        outliers_removed = int(len(values) - len(kept))
        values = kept

    return {
        "ok": True,
        "metric": metric,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "weekday": weekday_name,
        "baseline_start_date": str(start.date()),
        "baseline": round(float(values.mean()), 6),
        "n_observations": int(values.size),
        "outliers_removed": outliers_removed,
    }


@server.tool(
    description=(
        "Compare a date's value of `metric` to a baseline. "
        "baseline_kind='stable' uses compute_stable_baseline (day-of-week "
        "grouped, IQR-cleaned). baseline_kind='rolling7' uses the 7-day "
        "rolling average ending on the day BEFORE `date` (i.e. the trailing "
        "7-day mean — the comparator the PM uses for dip flagging). Returns "
        "{ok, date, metric, value, baseline, baseline_kind, delta_pp, "
        "delta_relative_pct, severity}. severity is one of 'normal' (<2pp), "
        "'flag' (2-4pp drop), 'alert' (>4pp drop), 'rise_flag' (2-4pp rise), "
        "'rise_alert' (>4pp rise) per the PM's documented thresholds."
    )
)
def compare_to_baseline(
    date: str,
    metric: str,
    platform: str,
    acquisition_source: str,
    baseline_kind: str = "stable",
) -> dict[str, Any]:
    err = _validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}
    if baseline_kind not in ("stable", "rolling7"):
        return {
            "ok": False,
            "error": f"baseline_kind must be 'stable' or 'rolling7', got {baseline_kind!r}",
        }

    target_date = pd.to_datetime(date, errors="coerce")
    if pd.isna(target_date):
        return {"ok": False, "error": f"date not parseable: {date!r}"}

    df = _filter_sheet(platform, acquisition_source)
    if metric not in df.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}

    row = df[df["date"] == target_date]
    if row.empty:
        return {"ok": False, "error": f"no row for {target_date.date()} in {platform}/{acquisition_source}"}
    value_raw = _coerce_metric(row[metric]).dropna()
    if value_raw.empty:
        return {"ok": False, "error": f"metric value missing on {target_date.date()}"}
    value = float(value_raw.iloc[0])

    if baseline_kind == "stable":
        weekday_name = target_date.strftime("%A").lower()
        bl = compute_stable_baseline(
            metric=metric,
            platform=platform,
            acquisition_source=acquisition_source,
            weekday=weekday_name,
        )
        if not bl.get("ok"):
            return bl
        baseline = bl["baseline"]
        baseline_meta = {
            "weekday": bl["weekday"],
            "n_observations": bl["n_observations"],
            "outliers_removed": bl["outliers_removed"],
        }
    else:
        prev_day = target_date - pd.Timedelta(days=1)
        ra = compute_rolling_average(
            metric=metric,
            platform=platform,
            acquisition_source=acquisition_source,
            end_date=str(prev_day.date()),
            window_days=7,
        )
        if not ra.get("ok"):
            return ra
        baseline = ra["average"]
        baseline_meta = {
            "window": "trailing 7 days",
            "n_observations": ra["n_observations"],
        }

    # Metric values in this sheet are fractional (0.293 = 29.3%). Express the
    # delta in percentage points by multiplying by 100.
    delta_pp = round((value - baseline) * 100.0, 2)
    delta_rel_pct = (
        round(((value - baseline) / baseline) * 100.0, 2)
        if baseline != 0
        else None
    )
    if delta_pp <= -4:
        severity = "alert"
    elif delta_pp <= -2:
        severity = "flag"
    elif delta_pp >= 4:
        severity = "rise_alert"
    elif delta_pp >= 2:
        severity = "rise_flag"
    else:
        severity = "normal"

    return {
        "ok": True,
        "date": str(target_date.date()),
        "metric": metric,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "value": round(value, 6),
        "baseline": round(baseline, 6),
        "baseline_kind": baseline_kind,
        "baseline_meta": baseline_meta,
        "delta_pp": delta_pp,
        "delta_relative_pct": delta_rel_pct,
        "severity": severity,
    }


@server.tool(
    description=(
        "Scan the most recent `days_back` days and return every day where "
        "`metric` has moved enough vs the chosen baseline to warrant a "
        "diagnostic. Defaults match the PM's methodology: 2pp drop = flag, "
        "4pp drop = alert (rises also returned with rise_flag/rise_alert). "
        "baseline='rolling7' is the trailing 7-day mean ending the day before; "
        "baseline='stable' uses compute_stable_baseline. Returns {ok, "
        "metric, platform, acquisition_source, days_scanned, threshold_pp_drop, "
        "threshold_pp_alert, baseline, flagged: [{date, value, baseline, "
        "delta_pp, severity}, ...]}."
    )
)
def flag_dip_days(
    metric: str,
    platform: str,
    acquisition_source: str,
    days_back: int = 30,
    threshold_pp_drop: float = 2.0,
    threshold_pp_alert: float = 4.0,
    baseline: str = "rolling7",
    baseline_start_date: str = "2026-01-01",
) -> dict[str, Any]:
    err = _validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}
    if days_back <= 0:
        return {"ok": False, "error": f"days_back must be > 0, got {days_back}"}
    if baseline not in ("stable", "rolling7"):
        return {"ok": False, "error": f"baseline must be 'stable' or 'rolling7', got {baseline!r}"}

    df = _filter_sheet(platform, acquisition_source)
    if metric not in df.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}
    df = df.dropna(subset=[metric])

    # Determine the date window to scan.
    max_date = df["date"].max()
    if pd.isna(max_date):
        return {"ok": False, "error": "no rows in segment"}
    start = max_date - pd.Timedelta(days=days_back - 1)
    window = df[(df["date"] >= start) & (df["date"] <= max_date)].copy()

    flagged: list[dict[str, Any]] = []
    for _, row in window.iterrows():
        cmp = compare_to_baseline(
            date=str(row["date"].date()),
            metric=metric,
            platform=platform,
            acquisition_source=acquisition_source,
            baseline_kind=baseline,
        )
        if not cmp.get("ok"):
            continue
        delta = cmp["delta_pp"]
        # Keep both drops and rises so the LLM can apply the rule it wants.
        if (
            delta <= -threshold_pp_drop
            or delta >= threshold_pp_drop
        ):
            severity = (
                "alert" if delta <= -threshold_pp_alert
                else "flag" if delta <= -threshold_pp_drop
                else "rise_alert" if delta >= threshold_pp_alert
                else "rise_flag"
            )
            flagged.append({
                "date": cmp["date"],
                "value": cmp["value"],
                "baseline": cmp["baseline"],
                "delta_pp": delta,
                "severity": severity,
            })

    return {
        "ok": True,
        "metric": metric,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "days_scanned": int(len(window)),
        "scan_start": str(start.date()),
        "scan_end": str(max_date.date()),
        "threshold_pp_drop": threshold_pp_drop,
        "threshold_pp_alert": threshold_pp_alert,
        "baseline": baseline,
        "baseline_start_date": baseline_start_date if baseline == "stable" else None,
        "flagged": flagged,
    }


_MIX_SOURCES = ("organic", "paid", "WTA", "others")


@server.tool(
    description=(
        "Compute the per-source acquisition mix shift for a single date and "
        "platform — Stage 1 step 2 of the diagnostic checklist. "
        "Use this to answer 'did WTA / paid / others share spike on the cohort day?' — "
        "do NOT load the full sheet and compute by hand. "
        "Returns each source's installs, share-of-platform-total, the share "
        "delta in percentage points vs the trailing baseline_days mean, and "
        "the install-volume ratio vs the baseline mean. The denominator for "
        "share excludes the 'All' aggregate row. "
        "Returns {ok, date, platform, baseline_days, baseline_window, "
        "total_installs_today, total_installs_baseline_mean, "
        "total_installs_ratio, by_source: {source: {installs, share_pct, "
        "baseline_mean_installs, baseline_mean_share_pct, share_delta_pp, "
        "installs_ratio_vs_baseline}}, biggest_mover}."
    )
)
def compute_acquisition_mix_shift(
    date: str,
    platform: str,
    baseline_days: int = 7,
) -> dict[str, Any]:
    if platform not in _VALID_PLATFORMS:
        return {"ok": False, "error": f"platform must be one of {_VALID_PLATFORMS}, got {platform!r}"}
    if baseline_days <= 0:
        return {"ok": False, "error": f"baseline_days must be > 0, got {baseline_days}"}

    target = pd.to_datetime(date, errors="coerce")
    if pd.isna(target):
        return {"ok": False, "error": f"date not parseable: {date!r}"}

    df = _sheet()
    df = df[(df["platform"] == platform) & (df["acquisition_source"] != "All")].copy()
    if df.empty:
        return {"ok": False, "error": f"no rows for platform={platform!r} (excluding 'All')"}

    df["installs"] = _coerce_metric(df["installs"]).fillna(0)

    pivot = df.pivot_table(
        index="date",
        columns="acquisition_source",
        values="installs",
        aggfunc="sum",
    ).fillna(0)
    # Ensure every source column exists even if no rows had data for it.
    for s in _MIX_SOURCES:
        if s not in pivot.columns:
            pivot[s] = 0.0
    pivot = pivot[list(_MIX_SOURCES)]
    pivot["__total"] = pivot[list(_MIX_SOURCES)].sum(axis=1)
    for s in _MIX_SOURCES:
        pivot[f"{s}__share"] = pivot[s].where(pivot["__total"] > 0, other=0) / pivot["__total"].replace(
            0, pd.NA
        )

    if target not in pivot.index:
        return {
            "ok": False,
            "error": f"no row for {target.date()} on platform={platform!r}",
        }

    baseline_start = target - pd.Timedelta(days=baseline_days)
    baseline_end = target - pd.Timedelta(days=1)
    baseline_rows = pivot[
        (pivot.index >= baseline_start) & (pivot.index <= baseline_end)
    ]
    if baseline_rows.empty:
        return {
            "ok": False,
            "error": (
                f"baseline window has no rows ({baseline_start.date()}.."
                f"{baseline_end.date()})"
            ),
        }

    today_row = pivot.loc[target]
    today_total = float(today_row["__total"])
    baseline_total_mean = float(baseline_rows["__total"].mean())
    total_ratio = (
        round(today_total / baseline_total_mean, 3) if baseline_total_mean else None
    )

    by_source: dict[str, dict[str, Any]] = {}
    for s in _MIX_SOURCES:
        today_installs = float(today_row[s])
        today_share = float(today_row.get(f"{s}__share") or 0.0)
        baseline_mean_installs = float(baseline_rows[s].mean())
        baseline_share_series = baseline_rows[f"{s}__share"].dropna()
        baseline_mean_share = (
            float(baseline_share_series.mean()) if not baseline_share_series.empty else 0.0
        )
        share_delta_pp = round((today_share - baseline_mean_share) * 100.0, 2)
        installs_ratio = (
            round(today_installs / baseline_mean_installs, 3)
            if baseline_mean_installs > 0
            else None
        )
        by_source[s] = {
            "installs": int(today_installs),
            "share_pct": round(today_share * 100.0, 2),
            "baseline_mean_installs": round(baseline_mean_installs, 1),
            "baseline_mean_share_pct": round(baseline_mean_share * 100.0, 2),
            "share_delta_pp": share_delta_pp,
            "installs_ratio_vs_baseline": installs_ratio,
        }

    biggest_mover = max(
        _MIX_SOURCES, key=lambda s: abs(by_source[s]["share_delta_pp"])
    )

    return {
        "ok": True,
        "date": str(target.date()),
        "platform": platform,
        "baseline_days": baseline_days,
        "baseline_window": f"{baseline_start.date()}..{baseline_end.date()}",
        "total_installs_today": int(today_total),
        "total_installs_baseline_mean": round(baseline_total_mean, 1),
        "total_installs_ratio": total_ratio,
        "by_source": by_source,
        "biggest_mover": biggest_mover,
    }


@server.tool(
    description=(
        "For one flagged date, return the 8-step diagnostic signals so the "
        "LLM does not have to derive them. The signals are vs the trailing "
        "7-day mean ending the day BEFORE the cohort day (= date − 1 for D1) "
        "so they describe what changed for the cohort behind that day's D1. "
        "Returns {ok, date, d1_cohort_day, platform, acquisition_source, "
        "signals: {platform_d1_delta_pp, ios_d1_delta_pp, "
        "pct_d0_notification_opt_in_delta_pp, pct_d0_login_delta_pp, "
        "d0_uninstall_rate_delta_pp, avg_engagement_time_delta_pct, "
        "installs_ratio, weekday}, raw: {today, trailing_mean}}. Each *_delta_pp "
        "is in percentage points; installs_ratio compares cohort-day installs "
        "to the trailing 7-day mean (1.5 = installs spike)."
    )
)
def compute_signals_for_day(
    date: str,
    platform: str,
    acquisition_source: str,
) -> dict[str, Any]:
    err = _validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}

    target = pd.to_datetime(date, errors="coerce")
    if pd.isna(target):
        return {"ok": False, "error": f"date not parseable: {date!r}"}

    cohort = target - pd.Timedelta(days=1)

    df = _filter_sheet(platform, acquisition_source)
    cohort_row = df[df["date"] == cohort]
    if cohort_row.empty:
        return {"ok": False, "error": f"no row for cohort_day {cohort.date()} in {platform}/{acquisition_source}"}

    def _delta_pp(metric: str, on_date: pd.Timestamp) -> float | None:
        cmp = compare_to_baseline(
            date=str(on_date.date()),
            metric=metric,
            platform=platform,
            acquisition_source=acquisition_source,
            baseline_kind="rolling7",
        )
        return cmp["delta_pp"] if cmp.get("ok") else None

    def _today(metric: str, on_date: pd.Timestamp) -> float | None:
        row = df[df["date"] == on_date]
        if row.empty:
            return None
        v = _coerce_metric(row[metric]).dropna()
        return float(v.iloc[0]) if not v.empty else None

    # Platform delta: same-segment d1 movement (already covered by D1 metric);
    # cross-platform iOS comparator helps the platform-check rule (Step 1).
    df_ios = _filter_sheet("ios", acquisition_source)
    ios_cmp_target = compare_to_baseline(
        date=str(target.date()),
        metric="d1",
        platform="ios",
        acquisition_source=acquisition_source,
        baseline_kind="rolling7",
    )
    ios_d1_delta_pp = ios_cmp_target["delta_pp"] if ios_cmp_target.get("ok") else None

    # D1 itself (same platform/source) on `date`.
    plat_cmp = compare_to_baseline(
        date=str(target.date()),
        metric="d1",
        platform=platform,
        acquisition_source=acquisition_source,
        baseline_kind="rolling7",
    )
    platform_d1_delta_pp = plat_cmp["delta_pp"] if plat_cmp.get("ok") else None

    # Stage-2 D0 signals are evaluated on the cohort day (date − 1).
    opt_in_delta_pp = _delta_pp("pct_d0_notification_opt_in", cohort)
    login_delta_pp = _delta_pp("pct_d0_login", cohort)

    # Engagement: % change vs trailing mean (in %, not pp).
    eng_today = _today("avg_engagement_time_per_user", cohort)
    eng_avg = compute_rolling_average(
        metric="avg_engagement_time_per_user",
        platform=platform,
        acquisition_source=acquisition_source,
        end_date=str((cohort - pd.Timedelta(days=1)).date()),
        window_days=7,
    )
    avg_engagement_delta_pct = (
        round(((eng_today - eng_avg["average"]) / eng_avg["average"]) * 100.0, 2)
        if eng_today is not None and eng_avg.get("ok") and eng_avg["average"]
        else None
    )

    # D0 uninstall rate (Android only). Computed per day so we can compare to a
    # rolling rate.
    uninstall_rate_delta_pp = None
    if platform == "android":
        df_local = df.copy()
        df_local["__d0_uninstall_rate"] = (
            _coerce_metric(df_local["d0_uninstalls"])
            / _coerce_metric(df_local["installs"])
        )
        cohort_idx = df_local[df_local["date"] == cohort].index
        if len(cohort_idx):
            today_rate = float(df_local.loc[cohort_idx[0], "__d0_uninstall_rate"])
            prior = df_local[
                (df_local["date"] >= cohort - pd.Timedelta(days=7))
                & (df_local["date"] < cohort)
            ]["__d0_uninstall_rate"].dropna()
            if not prior.empty and not pd.isna(today_rate):
                uninstall_rate_delta_pp = round((today_rate - prior.mean()) * 100.0, 2)

    # Installs ratio: cohort-day installs / trailing 7-day mean.
    installs_today = _today("installs", cohort)
    installs_avg = compute_rolling_average(
        metric="installs",
        platform=platform,
        acquisition_source=acquisition_source,
        end_date=str((cohort - pd.Timedelta(days=1)).date()),
        window_days=7,
    )
    installs_ratio = (
        round(installs_today / installs_avg["average"], 3)
        if installs_today is not None
        and installs_avg.get("ok")
        and installs_avg["average"]
        else None
    )

    return {
        "ok": True,
        "date": str(target.date()),
        "d1_cohort_day": str(cohort.date()),
        "platform": platform,
        "acquisition_source": acquisition_source,
        "signals": {
            "platform_d1_delta_pp": platform_d1_delta_pp,
            "ios_d1_delta_pp": ios_d1_delta_pp,
            "pct_d0_notification_opt_in_delta_pp": opt_in_delta_pp,
            "pct_d0_login_delta_pp": login_delta_pp,
            "d0_uninstall_rate_delta_pp": uninstall_rate_delta_pp,
            "avg_engagement_time_delta_pct": avg_engagement_delta_pct,
            "installs_ratio": installs_ratio,
            "weekday": target.strftime("%A"),
        },
        "notes": [
            "platform_d1_delta_pp = today's D1 (return-aligned) vs trailing 7-day mean.",
            "ios_d1_delta_pp = same-day iOS comparator for the platform-check rule.",
            "D0 deltas are evaluated on d1_cohort_day (= date − 1).",
            "d0_uninstall_rate is Android-only (iOS does not provide this signal).",
            "installs_ratio compares cohort-day installs to the trailing 7-day mean.",
        ],
    }


if __name__ == "__main__":
    server.run()
