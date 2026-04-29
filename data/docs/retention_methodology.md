<!-- desc: Three-stage retention framework, news significance taxonomy, post-news dip pattern, causal chain, stable baseline rationale -->
# D1 retention — methodology

The deep methodology behind the diagnostic checklist in `d1-retention-analysis.md`. Load this when the playbook checklist is not enough — when you need the *why* behind the steps, the news taxonomy, or the stable-baseline rationale.

This methodology is ported from the Times of India product analytics team's encoded expertise. The thresholds, ordering, and interpretive rules below are not generic best practices — they are calibrated to the TOI mobile app dataset.

## The three-stage retention framework

A failure at any stage kills D1.

```
STAGE 1: ACQUISITION
Who did we bring in, and with what promise?
(source mix, intent level, what content or ad converted them)
        ↓
STAGE 2: D0 EXPERIENCE
Did the app deliver in the first session?
(content relevance, session depth, activation actions taken)
        ↓
STAGE 3: HOOK TO RETURN
Did we give them a reason to come back — and execute on it?
(notification opt-in → right notification sent → compelling content pull)
```

The diagnostic checklist walks this top-down: source quality first (was the cohort lower-intent than usual?), then onboarding (did they activate?), then the hook (did the right push reach them?). When more than one stage looks broken, the **earliest stage is the lead** — fixing acquisition without fixing onboarding does not help, but fixing onboarding without fixing acquisition makes a difference.

## The causal chain

```
Install quality (source mix)
    → D0 activation (notification opt-in + login + session depth)
        → D1
            → D7 → D30
                → DAU → MAU → DAU/MAU (stickiness)
```

D0 is the **leading indicator**. D1 is the output. D7 / D30 / DAU / MAU are lagging outcomes.
- To move D1, work on D0.
- To move D7 and D30, first fix D1.

This is why the diagnostic checklist puts the heaviest weight on Stage-2 D0 signals — they tell you what the cohort experienced when it had a chance to form a return habit.

## Why thresholds are absolute (pp), not relative (%)

The PM's methodology compares the metric in **percentage points** to the trailing 7-day mean. A 2pp absolute drop on a baseline of 30% is meaningfully different from a 2% relative change. The 2pp / 4pp thresholds were calibrated against this dataset and survived peer review on the TOI analyst project.

- 2pp drop → flag, run the diagnostic, build a strong analytical reasoning.
- 4pp drop → alert, full diagnosis, surface proactively.
- 2–4pp rise → investigate, what-worked analysis.
- > 4pp rise → full what-worked analysis.

**Streak rule:** if D1 sits consistently above or below the rolling avg for 2+ days even with each daily delta < 2pp, the streak itself is the signal. Run the analysis.

**Oscillation rule:** if D1 alternates above/below the rolling avg for 3+ days without settling, that is variance, not trend. Report it as instability. Do not chase a "cause" for normal noise.

## iOS as a diagnostic tool

iOS is **not** the headline metric — Android organic is. But iOS is the cleanest comparator when Android moves.

- **Android drops + iOS drops** → external or common cause. News cycle, infra outage, cross-platform product change.
- **Android drops + iOS stable or up** → Android-specific. Acquisition, product, or infra issue scoped to Android.

iOS gets reported only when it helps explain Android. Not as a separate line item.

## The "always close a rise with: is this repeatable?" close

When D1 rises, the verdict has to answer one extra question that drops do not need: **will this hold?**

- **News-driven rise** → no. Will normalise once the story settles. **Watch for the post-news dip in the following days.**
- **Mix quality improvement** (organic share up, WTA / paid down) → possibly. Holds if the acquisition strategy holds.
- **D0 activation improvement** (login up, opt-in up) → yes, if a product change drove it. **Name the change.**
- **Unknown driver** → say so plainly. "D1 rose but the driver isn't visible in the data — notification execution is the most likely candidate."

## News significance taxonomy

Not every news day warrants a mention. The judgment: did the news environment meaningfully change what users did?

### What genuinely moves the needle

Events that make every Indian feel something — drive installs, return visits, sustained engagement across both platforms:

- **Armed conflict involving India** — Operation Sindoor, Kargil-scale events, India-Pakistan / China escalation. Highest-impact category.
- **Global conflicts with direct Indian stakes** — US-Iran war (crude prices, diaspora, shipping routes), Russia-Ukraine (wheat, energy, Indian students abroad).
- **Domestic mass-impact events** — Covid and public health emergencies, national budget, landmark Supreme Court verdicts, major terror attacks.
- **Economic shocks** — Sensex 2000+ point crash, rupee at historic lows, Trump tariffs directly targeting India.

What makes these needle-movers: **national scope**, **emotional salience for a broad Indian audience**, **a story that develops over days**.

### What holds retention stable but isn't a spike driver

- Ongoing election campaign coverage (steady engagement, not spikes).
- Ongoing geopolitical stories that haven't directly hit India yet.
- Cricket (India playing) — steady engagement lift, not dramatic D1 spikes unless a landmark moment (World Cup final).

### What does NOT move the needle nationally

- State-level accidents or disasters limited to one region.
- Regional political developments — state elections, CM changes, unless there's a massive national narrative.
- Celebrity news, entertainment, sports other than cricket.
- Incremental policy announcements.

**Test:** would this story make someone in Mumbai, Delhi, Bengaluru, AND Patna all open their news app? Yes across all four → national. Yes for one city → regional.

## Post-news dip pattern (cohort mean-reversion)

After a major news-driven spike, D1 often dips below baseline in the following days. The spike cohort was high-intent and news-motivated. Once the story settles, new installs revert to the usual lower-intent mix — but the rolling average is now anchored higher by the spike, making the reversion look worse than it is.

When a significant news event is logged (in `docs/major_events.md`) in the **preceding 3–7 days** and D1 is now soft, **flag post-news normalisation as the most likely driver** before running the standard diagnostic. This is not a product problem — it is cohort mean-reversion.

## Reading dual-date news context

When checking news for a flagged date, check **two** dates: the D1 return date AND the D0 cohort date (= return date − 1).

- **D1 news (return date)**: pull signal. A continuing or new high-significance story gives the cohort an active reason to open today.
  - Strong D1 news + D1 held up → news likely contributed.
  - Strong D1 news + D1 dropped → look inward; product or notification issues may be overriding the external pull.
- **D0 news (cohort date)**: install context. A high-significance D0 story explains why installs may have spiked and why all-DAU engagement was elevated.
  - On a newsy D0, expect `avg_engagement_time_per_user`, `avg_sessions_per_user`, `avg_pvs_per_session` to be elevated — directional only (all-DAU, not new-install-specific).
- **Same theme across D0 and D1** (a developing story) → narrative continuity supports retention.
- **High-significance D0 + quiet D1** → cohort installed into a spike with less pull to return. Expect softness. Check post-news dip before diagnosing a product problem.

## Stable baseline methodology

The diagnostic checklist uses two reference points:
- **7-day rolling average** — recent trend. Useful for streaks and short-term drift.
- **Stable baseline** — the clean, long-run reference. Computed via `compute_stable_baseline` MCP tool.

The stable baseline:
1. Pull all values of the metric from `baseline_start_date` (default `2026-01-01`) up to yesterday.
2. **Group by day of week** — a Monday baseline uses only past Mondays. D1 varies ~2pp across the week (Friday ~28%, Tuesday ~30% for Android organic).
3. **Remove outliers using IQR** — values outside `Q1 − 1.5×IQR` or `Q3 + 1.5×IQR` are dropped.
4. Return the mean of clean values.
5. **Fallbacks**: fewer than 4 observations for that weekday → use all weekdays. Fewer than 8 total values → skip outlier removal.

### Why `2026-01-01`

Acquisition strategy changed materially in Nov–Dec 2025: paid campaigns were paused, making the organic cohort cleaner and D1 structurally higher. **Pre-Jan 2026 data is not comparable to the current environment.** Update `baseline_start_date` only when:
- Paid campaigns are paused or restarted at significant scale.
- A new acquisition channel is added or removed.
- A major product change structurally shifts D1.

Document the reason whenever the baseline date is changed.

## Hard rules (recap)

These come from the system preamble; restated here for the LLM that loads only this doc:

- **No pattern claims without data.** Never write "typically", "usually", "tends to", "weekday-X is normally..." without verifying against the current run's data. Priors from training data are not findings.
- **Stage-ordered diagnosis.** Run the 8-step checklist in order. The most direct signal leads.
- **Diagnosis before evidence.** Verdict in sentence 1–2; evidence after.
- **No metric definitions in the headline report** — assume the PM knows what `d1`, `pct_d0_notification_opt_in`, etc. mean. Switch to definition mode only if the PM's query asks for it explicitly.
