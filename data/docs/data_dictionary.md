<!-- desc: Definitions of every column in d1_retention.csv — d1 vs d1_corrected, sessions, pct_* denominators, d0_uninstall -->
# Data dictionary — `sheets/d1_retention.csv`

Reference for what each column means. Use this when interpreting numbers
and especially when deciding between `d1` and `d1_corrected` — they
disagree on incident days, and that disagreement is meaningful.

This file is **eng-maintained**. PMs flag corrections; eng updates.

## Identity columns

| Column | Meaning |
|---|---|
| `date` | UTC date the row describes. One row per (`date`, `platform`, `acquisition_source`) tuple. |
| `platform` | `ios` or `android`. |
| `acquisition_source` | One of `organic`, `paid`, `WTA` (whatsapp-to-app), `others`, `All`. `All` is the cross-source aggregate already present in the sheet. |

## Volume metrics

| Column | Meaning |
|---|---|
| `dau` | Daily active users on `date`. An "active" user is one with at least one session on that day. |
| `installs` | New installs first activated on `date`. |
| `uninstalls` | Uninstalls counted on `date` (any cohort, not just new installs). Set to `0` for iOS — App Store does not expose this signal. |
| `d0_uninstalls` | Same-day uninstalls — users who installed AND uninstalled on `date`. The strongest signal of install quality. iOS is `0`. |
| `net_installs` | `installs - uninstalls` on `date`. |

## Engagement metrics

| Column | Meaning |
|---|---|
| `pvs` | Page views in the day. |
| `sessions` | Sessions in the day. A session is a contiguous use of the app, ending after ~30 minutes of inactivity. |
| `logins` | Logins on `date`. |
| `avg_engagement_time_per_user` | Mean time-in-app per active user (in seconds). |
| `avg_sessions_per_user` | `sessions / dau`. |
| `avg_pvs_per_session` | `pvs / sessions`. |

## Channel-share metrics

These split DAU by how the user *opened* the app on `date`.

| Column | Meaning |
|---|---|
| `dau_via_notifications` | Users who opened the app from a push notification. |
| `dau_via_launcher` | Users who opened from the home screen / app drawer icon. |
| `dau_via_deeplink` | Users who opened from a deeplink (WhatsApp share, browser link, etc.). |
| `pct_dau_via_notifications` | `dau_via_notifications / dau`. |
| `pct_dau_via_launcher` | `dau_via_launcher / dau`. |
| `pct_dau_via_deeplink` | `dau_via_deeplink / dau`. |

A push-notification outage shows up as a sudden drop in
`pct_dau_via_notifications` (and a compensating rise in
`pct_dau_via_launcher` if some users still come back on their own).

## Retention metrics — the key triplet

`d1`, `d7`, `d30` are **lagged retention rates** anchored on the install
cohort.

| Column | Meaning |
|---|---|
| `d1` | Of the cohort that installed on `date - 1`, the share that returned on `date`. |
| `d7` | Of the cohort that installed on `date - 7`, the share that returned on `date`. |
| `d30` | Of the cohort that installed on `date - 30`, the share that returned on `date`. |

So a *low `d1` on `date`* really points at the *cohort that arrived
yesterday*. When investigating a `d1` dip on, say, March 9, the install
spike to look at is March 8.

## `d1_corrected` vs `d1` — why they disagree

The "corrected" variants adjust for known measurement artefacts:
late-attribution installs, push-receipt timing, server clock drift, and
in-app crash-loop sessions that fail to record correctly.

| Column | Meaning |
|---|---|
| `d1_corrected` | `d1` after correction; closer to the "true" cohort retention. |
| `d7_corrected` | `d7` after correction. |
| `d30_corrected` | `d30` after correction. |

On normal days, raw and corrected differ by 1–3 percentage points.
On **incident days** (notification outages, app crashes), raw `d1` can
be 2× lower than `d1_corrected` because the correction backs out the
crash-loop effect. **Trust `d1_corrected` for verdicts; use raw `d1`
to spot anomalies.**

## D0 funnel metrics

These describe the install cohort itself — what happened to users on
their first day.

| Column | Meaning |
|---|---|
| `pct_d0_notification_opt_in` | Of users installed on `date`, the share that opted into push notifications during onboarding. |
| `pct_d0_login` | Of users installed on `date`, the share that logged in on day 0. |
| `pct_dau_logged_in` | Of all DAU on `date`, the share that is logged in (any cohort). |

A drop in `pct_d0_notification_opt_in` predicts lower D7/D30 a week or
month out — opt-in is the single strongest leading indicator.

## A few non-obvious things to remember

- **`uninstalls` is gross, not by-cohort.** A high `uninstalls` on a
  given day does not mean the *new* cohort uninstalled — they might be
  long-tenured users churning. Use `d0_uninstalls` for cohort-quality
  signal.
- **`dau` is unique users, not sessions.** A user with three sessions
  on the same day counts once.
- **`platform=ios` rows have `uninstalls=0` and `d0_uninstalls=0`.**
  This is a measurement gap, not real behaviour. Don't attempt to
  test install-quality hypotheses on iOS.
- **`acquisition_source=All` is an aggregate.** Per-source breakdowns
  (`paid` vs `organic`) need the full sheet, not the inlined slice.
