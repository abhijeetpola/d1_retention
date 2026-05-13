"""Tool: compute_stable_baseline — IQR-cleaned, day-of-week-grouped baseline."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools._common import (
    coerce_metric,
    cohort_rate,
    get_rows,
    RATE_METRICS,
    server,
    validate_segment,
)


_WEEKDAY_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


@server.tool(
    description=(
        "Compute the stable baseline for `metric` on the chosen segment. "
        "Methodology: take all values from `baseline_start_date` up to "
        "`baseline_end_date` (exclusive upper bound — pass the day before the "
        "target date so the target is never included in its own baseline); "
        "optionally restrict to one weekday (Monday through Sunday); optionally "
        "remove IQR outliers (Q1−1.5×IQR, Q3+1.5×IQR). Returns the mean of "
        "clean values. Defaults match the PM's documented methodology. "
        "weekday accepts case-insensitive names like 'monday' or None for all. "
        "baseline_end_date defaults to None (no upper bound) — always pass it "
        "when comparing to a specific date. "
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
    baseline_end_date: str | None = None,
    exclude_outliers_iqr: bool = True,
) -> dict[str, Any]:
    err = validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}

    start = pd.to_datetime(baseline_start_date, errors="coerce")
    if pd.isna(start):
        return {
            "ok": False,
            "error": f"baseline_start_date not parseable: {baseline_start_date!r}",
        }

    end: pd.Timestamp | None = None
    if baseline_end_date is not None:
        end = pd.to_datetime(baseline_end_date, errors="coerce")
        if pd.isna(end):
            return {
                "ok": False,
                "error": f"baseline_end_date not parseable: {baseline_end_date!r}",
            }

    df = get_rows(
        platform=platform,
        acquisition_source=acquisition_source,
        date_from=start,
        date_to=end,
    )
    if metric not in df.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}

    df["__metric"] = coerce_metric(df[metric])
    df = df.dropna(subset=["__metric"])

    weekday_name: str | None = None
    if weekday:
        target = weekday.strip().lower()
        if target not in _WEEKDAY_INDEX:
            return {
                "ok": False,
                "error": f"weekday must be a name like 'monday', got {weekday!r}",
            }
        df_weekday = df[df["date"].dt.weekday == _WEEKDAY_INDEX[target]]
        weekday_name = target
        # Fallback per PM methodology: fewer than 4 values for that weekday → use all.
        if len(df_weekday) >= 4:
            df = df_weekday
        else:
            weekday_name = (
                f"{target} (fallback: all weekdays — only {len(df_weekday)} "
                f"{target} obs)"
            )

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
    if exclude_outliers_iqr and len(values) >= 8:
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (values >= lo) & (values <= hi)
        outliers_removed = int((~mask).sum())
        values = values[mask]
        df = df[mask]

    if metric in RATE_METRICS:
        users_col, installs_col = RATE_METRICS[metric]
        baseline_val = cohort_rate(df, users_col, installs_col)
        if baseline_val is None:
            return {
                "ok": False,
                "error": (
                    f"no installs in window for {metric!r} "
                    f"({platform} / {acquisition_source})"
                ),
            }
    else:
        baseline_val = float(values.mean())

    return {
        "ok": True,
        "metric": metric,
        "platform": platform,
        "acquisition_source": acquisition_source,
        "weekday": weekday_name,
        "baseline_start_date": str(start.date()),
        "baseline": round(baseline_val, 6),
        "n_observations": int(values.size),
        "outliers_removed": outliers_removed,
    }
