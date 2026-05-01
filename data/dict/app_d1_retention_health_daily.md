<!-- desc: Definitions of every column in app_d1_retention_health_daily.csv — daily D1 cohort pivot. NOTE: covers android × WTA only -->
# Data dictionary — `sheets/app_d1_retention_health_daily.csv`

> Authoritative column reference for `sheets/app_d1_retention_health_daily.csv`. The playbook (`d1-retention-analysis.md`) carries the diagnostic flow and refers to this sheet by name; this file carries the column-level depth — coverage limits, the cohort-aggregated rate semantics, and when to prefer this sheet over the primary. Load via `load_file('dict/app_d1_retention_health_daily.md')` before reading this sheet for the first time in a run.

Daily D1 cohort retention pivot. **Pre-aggregated from the primary fact table** so you do not have to compute cohort rates yourself. Use this when the question is about a single day's D1 cohort and you want the methodology-correct number directly.

## Coverage limits — read this first

This pivot is **not** comprehensive. As of 2026-04, it covers:

| Dimension | Values present |
|---|---|
| `platform` | `android` only |
| `acquisition_source` | `WTA` only |

Every other segment combination (Android organic / paid / others, every iOS segment) is **absent** from this sheet. If the PM asks about Android organic D1 by day, do not reach for this pivot — fall back to the primary `app_health_daily` and read `d1_corrected` per day there. If the question is about a daily WTA cohort, this sheet is the authoritative source.

## Sheet structure

- One row per **(d1_cohort_day × platform × acquisition_source)**.
- The cohort_day is the **install day** — D1 retention of users who installed on that day and returned the next day.
- Rows whose `SUM of d1_installs = 0` show `d1_daily = #DIV/0!`. Treat these as null.

## Columns

| Column | Meaning |
|---|---|
| `d1_cohort_day` | Install day in `DD-Mon-YYYY` format (e.g., `30-Apr-2025`). The day the cohort installed. |
| `platform` | `android` only on this sheet. |
| `acquisition_source` | `WTA` only on this sheet. |
| `SUM of d1_installs` | Total installs on the cohort day for this segment. |
| `SUM of d1_users` | Total users from that cohort who returned on D1 (the next day). |
| `d1_daily` | Cohort-aggregated D1 rate = `SUM of d1_users / SUM of d1_installs`. Already computed; never re-derive by averaging. |

## When to prefer this sheet

- Question is "what was D1 for the WTA cohort on April 26 on Android?" — read this sheet directly, it has the answer.
- You want to compare WTA D1 across multiple consecutive cohort days — the sheet is daily-grained.

## When NOT to use this sheet

- Question involves Android organic / paid / others, or any iOS segment — those rows do not exist here. Use the primary `app_health_daily` and `d1_corrected` instead.
- You need engagement, opt-in, login, or any other signal beyond raw D1 — only the rate is here. The primary fact table has those.
- The question asks for a cohort window that crosses a week or month boundary in aggregate — use `app_d1_retention_health_weekly` or `app_d1_retention_health_monthly` so the boundary aggregation is correct.

## Methodology — cohort aggregation

D1 for a multi-day window must come from `sum(d1_users) / sum(d1_installs)` over the window's rows on this sheet. **Never average the `d1_daily` column.** Averaging daily rates equally weights small and large cohort days and gives a biased number. The pivot's daily values are correct as-is for each day; multi-day aggregation needs the install-weighted sum.
