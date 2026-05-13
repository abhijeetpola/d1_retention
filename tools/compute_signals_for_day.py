"""Tool: compute_signals_for_day — all 8-step diagnostic signals for one date."""

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
from tools.compute_rolling_average import compute_rolling_average


@server.tool(
    description=(
        "For one flagged date, return the 8-step diagnostic signals so the "
        "LLM does not have to derive them. `date` is the install cohort day "
        "(the day users installed). D1 signals describe what changed for that "
        "cohort; return day is date + 1. "
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
    err = validate_segment(platform, acquisition_source)
    if err:
        return {"ok": False, "error": err}

    target = pd.to_datetime(date, errors="coerce")
    if pd.isna(target):
        return {"ok": False, "error": f"date not parseable: {date!r}"}

    cohort = target

    df = get_rows(platform=platform, acquisition_source=acquisition_source)
    cohort_row = df[df["date"] == cohort]
    if cohort_row.empty:
        return {
            "ok": False,
            "error": (
                f"no row for cohort_day {cohort.date()} in "
                f"{platform}/{acquisition_source}"
            ),
        }

    # Per-signal failure log. Empty in the happy path. When populated, the LLM
    # must distinguish "this signal could not be computed" from "this signal
    # genuinely did not move" — a None in the signals dict alone cannot tell
    # the two cases apart, but a corresponding entry here can.
    signal_errors: dict[str, str] = {}

    def _delta_pp(metric: str, on_date: pd.Timestamp, signal_key: str) -> float | None:
        cmp = compare_to_baseline(
            date=str(on_date.date()),
            metric=metric,
            platform=platform,
            acquisition_source=acquisition_source,
            baseline_kind="rolling7",
        )
        if cmp.get("ok"):
            return cmp["delta_pp"]
        signal_errors[signal_key] = str(cmp.get("error") or "compare_to_baseline returned ok=false")
        return None

    def _today(metric: str, on_date: pd.Timestamp) -> float | None:
        row = df[df["date"] == on_date]
        if row.empty:
            return None
        v = coerce_metric(row[metric]).dropna()
        return float(v.iloc[0]) if not v.empty else None

    # Cross-platform iOS comparator for the Stage-1 platform-check rule.
    ios_cmp_target = compare_to_baseline(
        date=str(target.date()),
        metric="d1_corrected",
        platform="ios",
        acquisition_source=acquisition_source,
        baseline_kind="rolling7",
    )
    if ios_cmp_target.get("ok"):
        ios_d1_delta_pp = ios_cmp_target["delta_pp"]
    else:
        ios_d1_delta_pp = None
        signal_errors["ios_d1_delta_pp"] = str(
            ios_cmp_target.get("error") or "compare_to_baseline returned ok=false"
        )

    # Same-segment D1 movement on `date`.
    plat_cmp = compare_to_baseline(
        date=str(target.date()),
        metric="d1_corrected",
        platform=platform,
        acquisition_source=acquisition_source,
        baseline_kind="rolling7",
    )
    if plat_cmp.get("ok"):
        platform_d1_delta_pp = plat_cmp["delta_pp"]
    else:
        platform_d1_delta_pp = None
        signal_errors["platform_d1_delta_pp"] = str(
            plat_cmp.get("error") or "compare_to_baseline returned ok=false"
        )

    # Stage-2 D0 signals on the cohort day (date − 1).
    opt_in_delta_pp = _delta_pp(
        "pct_d0_notification_opt_in", cohort, "pct_d0_notification_opt_in_delta_pp"
    )
    login_delta_pp = _delta_pp("pct_d0_login", cohort, "pct_d0_login_delta_pp")

    # Engagement: % change vs trailing mean (in %, not pp).
    eng_today = _today("avg_engagement_time_per_user", cohort)
    eng_avg = compute_rolling_average(
        metric="avg_engagement_time_per_user",
        platform=platform,
        acquisition_source=acquisition_source,
        end_date=str((cohort - pd.Timedelta(days=1)).date()),
        window_days=7,
    )
    if eng_today is not None and eng_avg.get("ok") and eng_avg["average"]:
        avg_engagement_delta_pct = round(
            ((eng_today - eng_avg["average"]) / eng_avg["average"]) * 100.0, 2
        )
    else:
        avg_engagement_delta_pct = None
        if eng_today is None:
            signal_errors["avg_engagement_time_delta_pct"] = (
                f"no engagement value for cohort_day {cohort.date()}"
            )
        elif not eng_avg.get("ok"):
            signal_errors["avg_engagement_time_delta_pct"] = str(
                eng_avg.get("error") or "trailing engagement rolling-average unavailable"
            )

    # D0 uninstall rate (Android only).
    uninstall_rate_delta_pp = None
    if platform == "android":
        df_local = df.copy()
        df_local["__d0_uninstall_rate"] = (
            coerce_metric(df_local["d0_uninstalls"])
            / coerce_metric(df_local["installs"])
        )
        cohort_idx = df_local[df_local["date"] == cohort].index
        if len(cohort_idx):
            today_rate = float(df_local.loc[cohort_idx[0], "__d0_uninstall_rate"])
            prior = df_local[
                (df_local["date"] >= cohort - pd.Timedelta(days=7))
                & (df_local["date"] < cohort)
            ]["__d0_uninstall_rate"].dropna()
            if not prior.empty and not pd.isna(today_rate):
                uninstall_rate_delta_pp = round(
                    (today_rate - prior.mean()) * 100.0, 2
                )
            else:
                signal_errors["d0_uninstall_rate_delta_pp"] = (
                    f"no prior 7-day uninstall data for cohort {cohort.date()}"
                    if prior.empty else f"today's uninstall rate is NaN on {cohort.date()}"
                )
        else:
            signal_errors["d0_uninstall_rate_delta_pp"] = (
                f"no row for cohort_day {cohort.date()} on android"
            )

    # Installs ratio: cohort-day installs / trailing 7-day mean.
    installs_today = _today("installs", cohort)
    installs_avg = compute_rolling_average(
        metric="installs",
        platform=platform,
        acquisition_source=acquisition_source,
        end_date=str((cohort - pd.Timedelta(days=1)).date()),
        window_days=7,
    )
    if (
        installs_today is not None
        and installs_avg.get("ok")
        and installs_avg["average"]
    ):
        installs_ratio = round(installs_today / installs_avg["average"], 3)
    else:
        installs_ratio = None
        if installs_today is None:
            signal_errors["installs_ratio"] = (
                f"no installs value for cohort_day {cohort.date()}"
            )
        elif not installs_avg.get("ok"):
            signal_errors["installs_ratio"] = str(
                installs_avg.get("error") or "trailing installs rolling-average unavailable"
            )

    return {
        "ok": True,
        "date": str(target.date()),
        "return_day": str((target + pd.Timedelta(days=1)).date()),
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
        # Per-signal failure log. Empty in the happy path. When a signal here
        # has a corresponding entry in `signal_errors`, the LLM must NOT claim
        # the signal "did not move" — the signal could not be computed at all.
        "signal_errors": signal_errors,
        "notes": [
            "platform_d1_delta_pp = today's D1 (install-aligned, d1_corrected) vs trailing 7-day mean.",
            "ios_d1_delta_pp = same-day iOS comparator for the platform-check rule.",
            "D0 deltas are evaluated on date (the install day); return_day = date + 1 is when D1 is measured.",
            "d0_uninstall_rate is Android-only (iOS does not provide this signal).",
            "installs_ratio compares cohort-day installs to the trailing 7-day mean.",
            "If a signal is null AND has an entry in signal_errors, treat as 'could not compute', not 'did not move'.",
        ],
    }
