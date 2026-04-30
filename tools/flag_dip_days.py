"""Tool: flag_dip_days — list every recent day that crossed the dip threshold."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools._common import (
    coerce_metric,
    get_rows,
    server,
    validate_segment,
)
from tools.compare_to_baseline import compare_to_baseline


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
    err = validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}
    if days_back <= 0:
        return {"ok": False, "error": f"days_back must be > 0, got {days_back}"}
    if baseline not in ("stable", "rolling7"):
        return {
            "ok": False,
            "error": f"baseline must be 'stable' or 'rolling7', got {baseline!r}",
        }

    df = get_rows(platform=platform, acquisition_source=acquisition_source)
    if metric not in df.columns:
        return {"ok": False, "error": f"unknown metric: {metric!r}"}
    df = df.dropna(subset=[metric])

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
        if delta <= -threshold_pp_drop or delta >= threshold_pp_drop:
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
