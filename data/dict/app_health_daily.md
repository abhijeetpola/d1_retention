<!-- desc: Definitions of every column in app_health_daily.csv — d1 (return-aligned) vs d1_corrected (install-aligned), engagement caveats, data gaps -->
# Data dictionary — `sheets/app_health_daily.csv`

> Authoritative column reference for `sheets/app_health_daily.csv`. The playbook (`d1-retention-analysis.md`) carries the diagnostic flow and references columns by name with one-line meanings; this file carries the column-level depth — every column, the data gaps section, and methodology rationale. Load via `load_file('dict/app_health_daily.md')` when the diagnostic needs more than the playbook's inline summaries.

Reference for what each column means. Use this to interpret numbers and to decide between `d1` and `d1_corrected` — they are aligned to **different dates** and confusing them produces wrong verdicts.

## Sheet structure & key conventions

- One row per **(date × platform × acquisition_source)**.
- T-1 basis: April 19 row contains April 18 data.
- `acquisition_source = 'All'` is a **pre-calculated aggregate**, not a sum of the others. Always use `acquisition_source = 'All'` (or filter to a specific source). Do not add organic + paid + WTA + others.
- Rows with `#DIV/0!` = zero installs in that cohort. Treat as null.
- `installs` is **activated installs** — counted when a user installs AND opens the app. Not raw Play Store / App Store downloads.

## Identity columns

| Column | Meaning |
|---|---|
| `date` | UTC date the row describes. |
| `platform` | `android` or `ios`. |
| `acquisition_source` | `organic`, `paid`, `WTA` (whatsapp-to-app), `others`, or `All` (aggregate). |
| `week`, `month` | Week / month the date falls into. |

## Volume metrics

| Column | Meaning |
|---|---|
| `dau` | Daily active users. |
| `installs` | New activated installs. |
| `uninstalls` | App uninstalls — **Android only**. iOS rows have `0`. |
| `d0_uninstalls` | Users who installed AND uninstalled on the same day. **Android only.** |
| `net_installs` | `installs - uninstalls`. For iOS, `net_installs = installs` because uninstalls aren't available. |

## Retention rates — return-date aligned (`d1`, `d7`, `d30`)

For row dated **April 16**:
- `d1` = D1 retention of the **April 15 cohort** (installed Apr 15, returned Apr 16).
- `d7` = D7 of the April 9 cohort (installed Apr 9, returned Apr 16).
- `d30` = D30 of the March 17 cohort.

So a *low `d1` on `date`* really points at the *cohort that arrived `date − 1`*. When investigating an Apr 16 dip, the cohort to scrutinise is **Apr 15** (`d1_cohort_day`).

## Retention rates — install-date aligned (`d1_corrected`, `d7_corrected`, `d30_corrected`)

For row dated **April 16**:
- `d1_corrected` = D1 retention of users who **installed on April 16** (will return Apr 17).
- `d7_corrected` = D7 of the April 16 install cohort (return Apr 23).
- `d30_corrected` = D30 of the April 16 install cohort (return May 16).

**Most recent dates are blank** because the cohort hasn't completed D1/D7/D30 yet. This is **not** a measurement-artefact correction; it is just an alignment shift.

**Definition of D1:** installed day X, opened the app on day X+1. Always cohort-aligned to the install day.

**Use `d1_corrected` for the headline** (clean cohort attribution). Use raw `d1` for anomaly spotting — when something happened on `date` that affected returners more than installers.

## Retention — absolute counts and helpers

| Column | Meaning |
|---|---|
| `d1_users`, `d7_users`, `d30_users` | Absolute users returning on their D1 / D7 / D30 today. |
| `d1_installs`, `d7_installs`, `d30_installs` | Installs mapped to `d1_cohort_day`, `d7_cohort_day`, `d30_cohort_day`. |
| `d1_cohort_day` = `date − 1` | The install cohort whose D1 falls today. |
| `d7_cohort_day` = `date − 7` | Cohort whose D7 falls today. |
| `d30_cohort_day` = `date − 30` | Cohort whose D30 falls today. |

**Pivot rule (no exceptions, authoritative version):** weekly or monthly D1/D7/D30 must come from the dedicated cohort-aggregated pivots — `app_d1_retention_health_weekly` (full segment matrix) or `app_d1_retention_health_monthly` (Android × {WTA, paid} only). The pivots compute `sum(d1_users) / sum(d1_installs)` per period — the methodology-correct rate.

**Never average daily rates** from this primary fact table to produce a weekly or monthly number. Averaging daily rates ignores install-day weighting and gives a biased result: small days and large days contribute equally to the mean even though they represent very different numbers of users. If the right pivot does not exist for the segment in question, sum the absolute counts (`d1_users`, `d1_installs`) yourself over the window from this sheet, then divide once.

The playbook's "Choosing the right sheet" section is the procedural version of this rule; it tells the LLM which `get_rows(sheet=...)` call to make for a given question. That section follows from the rationale here.

## DAU channel breakdown

| Column | Meaning |
|---|---|
| `dau_via_notifications` | DAU who opened via push notification click. |
| `dau_via_launcher` | DAU who opened via the home-screen icon. |
| `dau_via_deeplink` | DAU who opened via a deeplink (WhatsApp share, web link, etc.). |
| `pct_dau_via_notifications` | `dau_via_notifications / dau`. |
| `pct_dau_via_launcher` | `dau_via_launcher / dau`. |
| `pct_dau_via_deeplink` | `dau_via_deeplink / dau`. |

**Important:** these three channels **overlap** — one user can be counted in more than one. They do **not** sum to DAU.

A push-notification outage shows up as a sudden drop in `pct_dau_via_notifications` (and a compensating rise in `pct_dau_via_launcher` if some users still come back on their own).

## Engagement (all-DAU, not cohort-specific)

| Column | Meaning |
|---|---|
| `pvs` | Total page views in the day. |
| `sessions` | Total sessions in the day. |
| `logins` | Total login events. |
| `avg_engagement_time_per_user` | Mean time-in-app per active user (seconds). |
| `avg_sessions_per_user` | `sessions / dau`. |
| `avg_pvs_per_session` | `pvs / sessions`. |

**Important caveat:** these are all-DAU, **not** new-install-cohort-specific. Use directionally when checking D0 session quality (Step 4 of the diagnostic checklist).

## D0 behaviour (new install cohort, on install day)

| Column | Meaning |
|---|---|
| `d0_notification_opt_in` | Absolute new users who opted into push during onboarding. |
| `pct_d0_notification_opt_in` | `d0_notification_opt_in / installs`. The **strongest leading indicator** for D1, D7, D30. |
| `d0_login` | Absolute new users who logged in on day 0. |
| `pct_d0_login` | `d0_login / installs`. |

## Logged-in users

| Column | Meaning |
|---|---|
| `dau_logged_in` | Absolute DAU who are logged in. |
| `pct_dau_logged_in` | `dau_logged_in / dau`. |

## Data gaps (priority-ranked)

These signals matter for the diagnostic but are **not** in the sheet. The LLM should name them as gaps when relevant, not pretend to evaluate them.

**Partial-window baselines are a related class of gap.** When `compute_rolling_average` is asked for a 7-day window but only N < 7 days of data exist for the (metric × platform × source) combination, the tool returns the mean of those N days with a `partial_window: true` flag and a `coverage_pct` value. `compare_to_baseline` propagates this through `baseline_meta.partial_window`. A delta computed against a 5-of-7 mean is materially noisier than a delta computed against a full-7 mean — the playbook's "Partial-baseline rule" requires the LLM to mark the rolling row as PARTIAL and weaken the severity badge by one step in this case. Treat partial windows as a data gap that softens the verdict, not as silent input to a confident severity label.

### Priority 1 — critical (block diagnosis)

| Gap | Stage |
|---|---|
| D0 avg engagement time — new installs only (current is all-DAU). | 2 |
| D0 page views — new installs only. | 2 |
| D0 sessions — new installs only. | 2 |
| D1 notification send rate (of opted-in users, what % actually received a push?). | 3 |
| D1 notification CTR / open rate (of those who received it, what % returned via the push?). | 3 |

### Priority 2 — important

| Gap | Stage |
|---|---|
| WTA source content category (what article converted the web user?). | 1 |
| D0 content category consumed by new installs. | 2 |
| D0 feature usage (search, save, follow topic). | 2 |

### Priority 3 — valuable

| Gap | Stage |
|---|---|
| D0 crash rate — new installs. Silent D1 killer. | 2 |
| D0 personalisation completion. | 2 |
| D1 notification content type. | 3 |
| D1 notification send time. | 3 |
