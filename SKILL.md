---
name: gitpodium
description: Rank git contributors across all branches and full history of one or more GitHub orgs/users, then generate a single self-contained HTML leaderboard. Use when someone asks "who contributed most" across a company's repos, wants a contribution/activity audit, a per-month or per-quarter contributor breakdown, or a shareable contributor leaderboard. Handles identity dedup (one person, many git emails) and filters out vendored/generated bulk commits.
---

# gitpodium

Clone every repo under some GitHub owners, walk all branches of full history, rank
contributors by churn (added+deleted lines), and bake the result into one shareable
`report.html`.

## Prerequisites
- `gh` (GitHub CLI), authenticated: `gh auth status`
- `git`, `python3`, `bash`, `awk` (all standard on macOS/Linux)

## The one command
Run from an **empty working directory** — all artifacts land there.
```bash
/path/to/gitpodium/gitpodium run <owner> [owner...]
```
`<owner>` is a GitHub org **or** user. This does: clone → build identity mailmap →
collect per-commit data across all branches → monthly rollup → `report.html`.

Open `./report.html` in any browser (double-click; no server needed). It has period
filters, per-person trend charts, and light/dark themes.

## Step-by-step (if you need control)
```bash
gitpodium clone acme-inc acme-labs   # -> ./clones/ (idempotent; re-run to update)
gitpodium mailmap                    # -> ./.mailmap (dedup one person's many emails)
gitpodium collect                    # -> ./contrib-commits.tsv (all branches, author-dated)
gitpodium rollup                     # -> ./monthly.json + monthly.csv
gitpodium report                     # -> ./report.html (embeds the data; self-contained)
gitpodium rank                       # console leaderboard (all-time); also:
gitpodium rank 2025-01-01 2025-12-31 quarter   # windowed / bucketed
```

## Tuning (env vars)
- `MAXCHURN=10000` `MAXFILES=400` — drop single commits bigger than this (vendored/generated dumps). Set both to `0` to disable.
- `DROP_BOTS=1` — exclude `*[bot]` accounts.
- `GITPODIUM_IDENTITY=path.json` — force-merge/override identities (see `examples/gitpodium.identity.json`).
- `GITPODIUM_CLONES=path` — reuse an existing clone mirror; `GITPODIUM_OUT=path` — artifact dir.

## ALWAYS tell the user this caveat
Churn ≠ contribution. Review, mentoring, design, and debugging are invisible to git;
squash-merged deleted branches are unrecoverable. Present the leaderboard as a
**conversation-starter, not a stack-rank or a performance metric.**
