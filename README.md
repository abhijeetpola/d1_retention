# PM Tuning Sandbox — D1 Retention Analysis

A small project that lets the product team tune the LLM analysis for D1 retention without writing any code.

You edit one Markdown file. You run one command. You read the report.

That's it.

---

## What's in this folder

| File / folder | What it is |
|---|---|
| `d1-retention-analysis.md` | **The one file you edit.** It contains the hypothesis, instructions for the LLM, and the report shape you want. |
| `data/sheets/d1_retention.csv` | The retention dataset. You don't edit this — an engineer drops it in and refreshes it. |
| `data/docs/` | **Drop any extra context here.** Causal docs, release notes, data dictionaries — anything you'd like the LLM to optionally read when needed. |
| `outputs/` | Where the generated report lands after each run. |
| `tune` | The one command you run. |
| `tune_mcp.py`, `config.yaml`, `pyproject.toml` | Engineer-managed plumbing. You don't need to touch these. |

---

## One-time setup

```bash
# Install dependencies
uv sync

# Make sure Claude CLI is logged in
claude --version
# (if not installed, get it from https://claude.com/code)

# Sanity check
./tune doctor
```

If `./tune doctor` says everything is fine, you're ready.

---

## The tuning loop

```
1. Open d1-retention-analysis.md in any text editor (VS Code, TextEdit,
   Cursor, vim — anything you like).

2. Edit the prose. Common tuning moves:
   - Sharpen a hypothesis
   - Change the steps you want the LLM to take
   - Adjust the "Report shape" section to ask for different sections
   - Add or remove caveats / instructions

3. ⌘S to save.

4. Switch to Terminal in this folder and run either:
        ./tune
   or with a one-shot question on top:
        ./tune "Why did D1 dip on March 8?"

5. The script:
   - reads your prose
   - reads the data
   - calls Claude (you'll see a spinner with elapsed time ticking up)
   - renders the final report inline in your Terminal
   - writes the report into outputs/<today>-d1-retention-analysis.md
   - auto-opens it in your default Markdown viewer

6. Read the report. Decide what's still vague, what you'd want pivoted,
   what new hypothesis to test. Edit the prose again. Repeat.
```

Each run typically takes 2–5 minutes. Cost is around $0.30–$1.50 (charged
to your Claude subscription, not to a separate API budget). If a run takes
much longer or costs much more, the LLM is probably re-loading the full sheet
unnecessarily — see the troubleshooting section.

---

## What you can ask the LLM to do in the prose

In your `d1-retention-analysis.md`:

- **Refer to columns by name** — e.g., "compare `d1` against `d1_corrected`",
  "look at `pct_dau_via_notifications` on dip days"
- **Ask it to load extra files** — e.g., "if you want context on what changed,
  call `load_file('docs/release_log.md')`"
- **Ask it to load the full sheet** — the inlined table is a slice (last 180
  days, **`platform=android × acquisition_source=organic`**, the PM-default
  headline cohort). For other platforms or sources, prose-instruct:
  "if your verdict changes when you look at iOS or paid acquisition,
  call `load_file('sheets/d1_retention.csv')` for the full breakdown"

The LLM also has `list_files()` available — it can call this to see what's in
`data/` if it needs to.

### Deterministic D1 retention math (MCP tools)

Beyond `list_files` / `load_file`, the LLM has five deterministic-math tools
it can call mid-reasoning. These exist so the LLM does NOT have to compute
rolling averages or apply thresholds itself — the PM can tune the methodology
in the playbook prose without worrying about LLM arithmetic mistakes.

| Tool | What it does |
|---|---|
| `compute_rolling_average(metric, platform, acquisition_source, end_date, window_days)` | Rolling average over a caller-chosen window. |
| `compute_stable_baseline(metric, platform, acquisition_source, weekday=None, baseline_start_date)` | IQR-cleaned, day-of-week-grouped mean (the PM's "stable baseline" methodology). |
| `compare_to_baseline(date, metric, platform, acquisition_source, baseline_kind="stable" \| "rolling7")` | Delta of one date vs the chosen baseline; returns severity (`flag` / `alert` / `rise_flag` / `rise_alert` / `normal`). |
| `flag_dip_days(metric, platform, acquisition_source, days_back, threshold_pp_drop, threshold_pp_alert, baseline)` | List of every day in the window that crossed the threshold. |
| `compute_signals_for_day(date, platform, acquisition_source)` | All eight diagnostic signals for one flagged day in one call (platform delta, iOS comparator, D0 opt-in / login / uninstall change, engagement change, installs ratio, weekday). |

Defaults match the PM methodology (2pp = flag, 4pp = alert, baseline starts
2026-01-01) but every parameter is exposed. PMs can ask "show me last 30 days
with a 1pp threshold" and the LLM will pass through the override.

---

## How to add an extra context document

Just drop the file into `data/docs/`:

```bash
cp ~/Documents/our-causal-doc.md data/docs/causal_doc.md
```

Then mention it in your playbook prose:

```markdown
If you want my mental model of how product changes flow into retention,
call `load_file('docs/causal_doc.md')` before forming verdicts.
```

The LLM will load it mid-reasoning when the playbook asks.

---

## Comparing two runs

Each run lands in a dated file under `outputs/`. The most recent always has a
sibling symlink at `outputs/latest.md`.

To see how a prose change affected the analysis:

```bash
diff outputs/2026-04-28-d1-retention-analysis.md outputs/2026-04-29-d1-retention-analysis.md
```

Or use VS Code's Source Control panel to see line-level diffs visually.

---

## Quick reference

| Command | What it does |
|---|---|
| `./tune` | Run the analysis end-to-end using just the playbook prose. |
| `./tune "Why did D1 dip on March 8?"` | Run end-to-end AND add a one-shot question for this specific run. The question is appended to the prompt with a "PM's specific question for THIS run" header — Claude treats it as the primary lens for the TL;DR and verdicts. |
| `./tune doctor` | Sanity-check the environment (claude installed, files in place). |
| `./tune --dry-run` | Show the prompt that would be sent. Don't call Claude. Useful for sanity checks while you tune the prose. |
| `./tune --dry-run "your question"` | Same, with the inline question included. Confirm the prompt looks right before paying for a real run. |
| `./tune --quiet` | Skip the inline report rendering in the terminal (only write the file). |
| `./tune --no-open` | Don't auto-open the report in your default Markdown viewer (only print inline + write file). |

### When you run `./tune`, the report is rendered in the Terminal AND written to a file

After Claude finishes:

1. The report is **rendered inline** in your Terminal using Markdown formatting (headings, tables, bullets) — you can scroll up and read it without leaving the Terminal.
2. The file `outputs/<date>-d1-retention-analysis.md` is written to disk.
3. `outputs/latest.md` (a symlink) is updated to point at the latest run.
4. Your default Markdown viewer auto-opens the file (suppress with `--no-open`).

### Two ways to use the inline-question feature

**As a quick one-off question** without changing the playbook:

```bash
./tune "Compare last week's D1 to the prior week. Where did the gap widen?"
```

This is great for "I just want to ask one thing on top of the standard analysis."

**As a tuning lever** alongside playbook edits:

```bash
$EDITOR d1-retention-analysis.md            # tune the structural prose
./tune "specifically focus on iOS deeplink share"   # add a per-run focus
```

The playbook prose is for stable, structural framing. The inline question is for ad-hoc focus on a single run. Both go into the same prompt; the inline question is highlighted to the LLM as "the primary lens for THIS run."

---

## When something doesn't look right

- **The report says "I cannot determine ..."** → the prose probably gave Claude too little to work with, OR the data slice doesn't have what you asked about. Try `./tune --dry-run` to see what data is being sent.
- **Claude says "file not found"** → call `list_files()` from inside the playbook prose: tell the LLM to start with `list_files()` to see what's there.
- **Cost is higher than expected** → you're probably making Claude load the full CSV when it doesn't need it. Tune the prose so it only calls `load_file('sheets/d1_retention.csv')` when the inlined slice is truly insufficient.
- **`./tune` errors out with "claude not found"** → run `claude --version` to confirm the CLI is installed and logged in.

If something is genuinely broken, talk to the engineer. The plumbing
(`tune`, `tune_mcp.py`, `config.yaml`) is theirs.
