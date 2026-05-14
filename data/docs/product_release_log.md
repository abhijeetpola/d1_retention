<!-- desc: App releases, feature flags, A/B test starts, and push-scheduler changes — eng/PM maintained -->
# Product release log — what shipped when

A short log of app releases, feature flags, A/B tests, and push-scheduler
changes inside the window of `sheets/app_health_daily.csv`. Use this to explain
step-changes in retention that don't line up with external news.

This file is **eng/PM-maintained**. The rows below are illustrative
samples — replace with real changes you shipped.

## How to read this

| Column | Meaning |
|---|---|
| `Date` | Day the change reached production (or A/B started) |
| `Change` | Short label of what shipped |
| `Type` | release / flag-on / flag-off / A-B start / A-B end / push-change |
| `Cohort affected` | Platform / acquisition source / DAU segment touched |
| `Expected retention effect` | What the team expected at launch |

## Sample entries

| Date | Change | Type | Cohort affected | Expected retention effect |
|---|---|---|---|---|
| 2025-09-15 | [Sample] App release 7.4.0 — new home feed for Android | release | Android, all sources | D1 up 1–2 pp over 4 weeks |
| 2025-11-08 | [Sample] Notification scheduler v2 — fewer, smarter pushes | push-change | All platforms | Notification share down ~15%, D1 stable, pct_dau_via_launcher up |
| 2026-01-20 | [Sample] Personalised onboarding A/B for paid Android | A-B start | Android paid | D1 up 3–5 pp on the test arm; control unchanged |
| 2026-03-05 | [Sample] Login wall removed for cricket section | flag-off | All platforms | pct_dau_logged_in down, sessions per user up, D1 mixed |

## How to use this file

If a flagged dip or a sustained shift in any column lines up with a release
row above, cite it in the "Key findings" section and treat the release as
the most likely driver. If a dip happens *despite* the release predicting
the opposite (e.g., D1 fell after a release expected to lift it), call it
out — that's where the PM wants to focus.

## Eng/PM instructions for maintaining

- One row per change that the team thinks could move the metric.
- Keep retention-irrelevant releases (small bugfixes, copy changes) out
  of this file.
- Date format: `YYYY-MM-DD`. For A/B tests, use the start date and add a
  separate end-date row when the test concludes.
- Cross-link to the release notes / Linear ticket in `Notes` if helpful.
