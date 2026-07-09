# gitpodium — agent instructions (Codex / OpenCode / any AGENTS.md-aware CLI)

gitpodium ranks git contributors across all branches and full history of one or more
GitHub orgs/users and produces a single self-contained `report.html`. Use it when the
user wants to know who contributed most across a set of repos, wants a contribution
audit, a per-month/quarter breakdown, or a shareable contributor leaderboard.

## When to reach for this
Triggers: "who contributed most", "rank contributors", "contribution audit / leaderboard",
"activity across all our repos", "who wrote the most code this quarter".

## Prerequisites
`gh` (authenticated — check `gh auth status`), `git`, `python3`, `bash`, `awk`.

## Run it
From an **empty working dir** (all outputs land there):
```bash
./gitpodium run <owner> [owner...]     # owner = GitHub org OR user
# -> ./report.html   (clone → mailmap → collect → rollup → embed)
```
Individual steps if you need them: `clone`, `mailmap`, `collect`, `rollup`, `report`
(HTML), `rank` (console). See `SKILL.md` for the full breakdown and tuning env vars
(`MAXCHURN`, `MAXFILES`, `DROP_BOTS`, `GITPODIUM_IDENTITY`, `GITPODIUM_CLONES`, `GITPODIUM_OUT`).

## Non-negotiable caveat to surface every time
Churn (added+deleted lines) ≠ contribution. Review, mentoring, design, and debugging
don't show up in git; squash-merged/deleted branches are lost. Present the output as a
**conversation-starter, never a stack-rank or performance metric.**
