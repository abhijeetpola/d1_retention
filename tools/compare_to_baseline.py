"""Tool: compare_to_baseline — delta of one date vs a chosen baseline.

The dip-severity ladder (alert / flag / normal / rise_flag / rise_alert)
is applied here, using absolute pp thresholds per the PM methodology.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools._common import (
    coerce_metric,
    get_rows,
    server,
    validate_segment,
)
from tools.compute_rolling_average import compute_rolling_average
from tools.compute_stable_baseline import compute_stable_baseline


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
    err = validate_segment(platform, acquisition_source)
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

    rows = get_rows(
        platform=platform,
        acquisition_source=acquisition_source,
        date_from=target_date,
        date_to=target_date,
    )
    if metric not in rows.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}
    if rows.empty:
        return {
            "ok": False,
            "error": f"no row for {target_date.date()} in {platform}/{acquisition_source}",
        }
    value_series = coerce_metric(rows[metric]).dropna()
    if value_series.empty:
        return {"ok": False, "error": f"metric value missing on {target_date.date()}"}
    value = float(value_series.iloc[0])

    if baseline_kind == "stable":
        weekday_name = target_date.strftime("%A").lower()
        bl = compute_stable_baseline(
            metric=metric,
            platform=platform,
            acquisition_source=acquisition_source,
            weekday=weekday_name,
            baseline_end_date=str((target_date - pd.Timedelta(days=1)).date()),
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
            # Propagated from compute_rolling_average. The LLM should weaken
            # the severity verdict when partial_window is true (a 5-of-7 mean
            # is materially noisier than a full-7 mean).
            "partial_window": ra.get("partial_window", False),
            "coverage_pct": ra.get("coverage_pct", 100.0),
        }

    # Metric values in this sheet are fractional (0.293 = 29.3%). Convert the
    # delta to percentage points by multiplying by 100.
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
