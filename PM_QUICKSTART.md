# PM Quickstart

One page. Get the sandbox running in five minutes.

## What you need

- macOS or Linux terminal
- Python 3.11 or newer (check: `python3 --version`)
- `uv` package manager (check: `uv --version`; install if missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Claude Code CLI, signed in (check: `claude --version`)

## One-time setup

```bash
git clone https://github.com/santoshroyal/d1_retention.git
cd d1_retention
uv sync
./tune doctor
```

`./tune doctor` should print all green checks. If anything is red, the message tells you what to fix.

## Your first run

```bash
./tune
```

This reads `d1-retention-analysis.md` (the playbook) and writes a report to `outputs/`. The report opens automatically; the latest one is always at `outputs/latest.md`.

You can also pass a question:

```bash
./tune "why did Android organic D1 dip last week?"
```

## Tuning the analysis

The whole tuning loop is one file: `d1-retention-analysis.md`. Open it in any editor, change the prose — hypothesis, diagnostic steps, report shape — and re-run `./tune`. That is the entire workflow.

Optional context lives in `data/docs/` (release notes, holidays, news events, methodology). The LLM loads what it needs on its own; you do not have to reference them.

## Where things go

| What | Where |
|---|---|
| The playbook you tune | `d1-retention-analysis.md` |
| Each run's report | `outputs/<date>-d1-retention-analysis.md` |
| Latest report (symlink) | `outputs/latest.md` |
| Context docs the LLM may load | `data/docs/` |

## When something does not work

| Symptom | Try this |
|---|---|
| `claude` not signed in | Run `claude` once and complete sign-in. |
| Sheet refresh failed (network) | Re-run `./tune`, or force a refetch with `./tune --refresh`. |
| Anything else | `./tune doctor` — the output names the broken thing. |

For deeper architecture and conventions, see `README.md`. You do not need to read it to use the sandbox.
