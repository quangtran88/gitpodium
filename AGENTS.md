# gitpodium — agent instructions (Codex / OpenCode / any AGENTS.md-aware CLI)

gitpodium is **agent-driven**: when the user wants to know who contributed most across a
set of repos, YOU run the whole audit for them — check prerequisites, interview them for
the setup, run the pipeline, deliver a self-contained `report.html`, and state the caveat.
The user should not have to type commands.

## When to use
Triggers: "who contributed most", "rank contributors", "contribution/activity audit",
"leaderboard across our repos", "who wrote the most code this quarter".

## Run it as an interview (don't dump commands on the user)

1. **Prerequisites.** `gh auth status` — if not authed, have them run `gh auth login`
   (needs `repo` + `read:org` scopes). Confirm `git` + `python3`. Don't proceed until green.
2. **Scope.** Ask which GitHub **owners** (orgs and/or users), or a specific `owner/repo`
   list. Private repos need token access.
3. **Metric.** Ask how to rank the git-churn view: `churn` (default) / `commits` /
   `added` / `deleted` / `net` / `repos`. → `GITPODIUM_METRIC`.
4. **Window.** All-time or a date range; bucket the console view by month/quarter/year.
5. **Filters.** Bots off by default (`DROP_BOTS=1`); bulk/vendored dumps dropped via
   `MAXCHURN=10000`/`MAXFILES=400`. Offer raw (all `0`).
6. **Output.** Where `report.html` goes → `GITPODIUM_OUT` (default: current dir).
7. **Confirm** the plan, then run (export the env, then):
   ```bash
   ./gitpodium run <owner...>        # clone → mailmap → collect → rollup → github → report.html
   ```
   `run` also pulls **PRs, code reviews, review comments, and issues** from the GitHub API
   (`gitpodium github`) into a **Collaboration** tab keyed by GitHub login — the review/PR
   work git churn can't see. It's best-effort: needs the `gh` API and GitHub-hosted repos,
   skip with `GITPODIUM_SKIP_GITHUB=1` (non-GitHub repos / rate limit). Issues may be sparse
   if the team uses Jira/Linear — expected, not a bug.
8. **Review identities** (optional): after the mailmap step, offer `mailmap-review.md`;
   confirmed merges go into `GITPODIUM_IDENTITY=gitpodium.identity.json`, then re-run.
9. **Deliver:** point to `report.html`, narrate the top contributors via `./gitpodium rank`
   (it prints how much was dropped as bulk/bots), point out the **Collaboration tab**'s top
   reviewers + "churn-blind reviewers" (heavy reviewers who open few PRs), and give the
   caveat below.

Full step-by-step and the flag↔answer table live in `SKILL.md`.

## Non-negotiable caveat to surface every time
Churn (added+deleted lines) ≠ contribution. Review, mentoring, design, and debugging
don't show up in git; squash-merged/deleted branches are lost. The Collaboration tab
recovers *some* of that (reviews, PRs, issues) but not all of it. Present the output as a
**conversation-starter, never a stack-rank or performance metric.**
