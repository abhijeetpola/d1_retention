<!-- desc: Push outages, login bugs, and app crashes — distinguishes infra-driven D1 dips from product-driven ones -->
# Known incidents — push, login, crashes

A short log of infra and app-level incidents in the window of
`sheets/d1_retention.csv`. Use this to distinguish a D1 dip caused by an
outage (one-day measurement artefact) from one caused by product or
acquisition changes (a real signal worth investigating).

This file is **oncall-maintained**. The rows below are illustrative
samples — replace with real incidents from your incident tracker.

## How to read this

| Column | Meaning |
|---|---|
| `Date` | Day the incident occurred (or peaked) |
| `Incident` | Short label |
| `Type` | push / login / crash / api / store |
| `Platform` | ios / android / both |
| `Detected via` | Source of the signal — alert, user reports, store ratings |
| `Resolved` | Same-day / next-day / multi-day / unresolved |

## Sample incidents

| Date | Incident | Type | Platform | Detected via | Resolved |
|---|---|---|---|---|---|
| 2025-11-09 | [Sample] Push delivery dropped to ~40% of normal volume | push | both | alert + drop in `pct_dau_via_notifications` | next-day |
| 2025-12-17 | [Sample] Android home feed crash on cold start | crash | android | crash reports + Play Store reviews | next-day (hotfix) |
| 2026-01-31 | [Sample] Login API timed out for ~3 hrs | login | both | alert | same-day |
| 2026-03-09 | [Sample] App Store review snag delayed iOS hotfix release | store | ios | release manager | multi-day |

## How to use this file

If a flagged dip date matches an incident row above, cite the incident in
the "Caveats" section and **discount the raw `d1` for that day** — use
`d1_corrected` or the trailing-7-day mean instead. If the dip is far
larger than typical for the incident type, call it out — there may be a
secondary cause stacked on top.

## Oncall instructions for maintaining

- Add a row whenever an incident lands above the "could move D1" bar.
  Routine alerts that didn't actually move metrics don't belong here.
- Date format: `YYYY-MM-DD`.
- For incidents that span multiple days, use the start date and put
  the duration in `Resolved`.
- If you're not sure whether the incident moved D1, add the row anyway
  with `Detected via: precaution` and let the analysis tell you.
