---
name: gitpodium
description: Interactively run a git contribution audit for the user. Use when someone asks "who contributed most" across a company's/team's repos, wants a contribution or activity audit, a per-month/quarter contributor breakdown, a code-review/pull-request/issue breakdown, or a shareable contributor leaderboard. This skill DRIVES the setup — it checks prerequisites (GitHub CLI auth), interviews the user for scope (which orgs/users/repos), the ranking metric, noise filters, and output, then clones, dedups identities, and produces a single self-contained HTML report covering both git churn AND (from the GitHub API) pull-request / code-review / review-comment / issue activity — so reviewers who write little code still show up. Do NOT expect the user to run commands themselves; you run the pipeline for them.
---

# gitpodium — interactive contribution audit

You (the agent) run this end to end. The user should never have to type a command.
Walk the setup as a short interview, confirm a plan, run the pipeline, deliver the
report, and **always** state the caveat. Ask questions in small batches (use
`AskUserQuestion` in Claude Code); don't interrogate one line at a time.

`GP` below = the path to this skill's directory. Every step writes artifacts into the
user's chosen output dir (`GITPODIUM_OUT`, default the current directory).

---

## Step 0 — Prerequisites (do this before asking anything else)

1. `gh auth status` — if not authenticated, tell the user to run `gh auth login`
   (in Claude Code they can type `! gh auth login`). Required token scopes: **`repo`**
   (private repos) and **`read:org`** (list org repos). Re-check before continuing.
2. Confirm `git`, `python3`, `bash`, `awk` exist (standard on macOS/Linux). Stop and
   report if `gh` or `python3` is missing.

Only proceed once `gh auth status` is green.

## Step 1 — Scope (what to audit)

Ask the user:
- **Which GitHub owners?** One or more **orgs** and/or **users** (e.g. `acme-inc acme-labs`).
  A user's own repos work too. Offer to run `gh org list` / `gh repo list <owner> --limit 5`
  to help them confirm the right names.
- **Whole owner or a subset?** If they only want specific repos, collect an
  `owner/repo` list and use a repos file instead of a whole org.
- Remind: private repos are included only if their `gh` token can see them.

Map → `clone` args, or a `-f repos.txt` file.

## Step 2 — Ranking metric

Ask: **rank by which metric?** (the HTML report always lets viewers switch live; this
sets the default view and the headline you report):

| Choice | Meaning |
|---|---|
| `churn` *(default)* | added + deleted lines — most common "how much code moved" |
| `commits` | number of commits — activity/cadence, less gameable by big refactors |
| `added` / `deleted` | growth vs. cleanup |
| `net` | added − deleted |
| `repos` | breadth (how many repos touched) |

Map → `GITPODIUM_METRIC=<choice>` (passed to the report build). This ranks the **git
churn** view. The report also ships a **Collaboration tab** (next paragraph) with its own
GitHub metrics — no need to choose between them, both are built.

### Also collected: GitHub collaboration (PRs, reviews, issues)

Beyond git history, gitpodium pulls **pull requests, code reviews, review comments, and
issues** from the GitHub API (`gitpodium github`) into a second **Collaboration** tab,
keyed by GitHub login. This is the work churn is blind to — a heavy reviewer who writes
little code finally ranks. Mention it when you pitch the report. Caveats to relay:
- Needs the `gh` API and only covers **GitHub-hosted** repos the token can see; subject to
  the GraphQL rate limit. Set `GITPODIUM_SKIP_GITHUB=1` to skip it (non-GitHub repos, or to
  save rate limit).
- **Issues** may be near-empty if the team uses Jira/Linear — that's expected, not a bug.
- Bots (GraphQL `Bot`-type actors, `*[bot]`, `extra_bots`) are excluded from reviewers too.

## Step 3 — Time window

Ask: **all-time, or a date range?** And for the console summary, bucket by
**month / quarter / year**? The HTML report always contains all history with a live
time filter; the window mainly shapes the console leaderboard you narrate.

Map → `rank [FROM TO [month|quarter|year]]`.

## Step 4 — Noise filters

Explain the defaults and let them adjust:
- **Bots** (`dependabot`, CI, AI agents) — excluded by default (`DROP_BOTS=1`).
- **Bulk/vendored dumps** (framework imports, generated code) — any single commit over
  `MAXCHURN=10000` lines or `MAXFILES=400` files is dropped so it can't crown a fake
  winner. Offer "raw, no filtering" (`MAXCHURN=0 MAXFILES=0 DROP_BOTS=0`) if they want it.

Map → env vars `DROP_BOTS`, `MAXCHURN`, `MAXFILES`.

## Step 5 — Output

Ask: **where should the report go?** Default: current directory → `./report.html`
(a single self-contained file; no server, safe to email/Slack). Set `GITPODIUM_OUT`.

## Step 6 — Confirm the plan, then run

Echo back a one-paragraph plan: *owners, metric, window, filters, output*. On approval,
export the chosen env vars and run — for many repos, run the clone in the background:

```bash
export GITPODIUM_OUT="<out-dir>" GITPODIUM_CLONES="<out-dir>/clones" GITPODIUM_METRIC="<metric>" \
       MAXCHURN=<n> MAXFILES=<n> DROP_BOTS=<0|1>
# GITPODIUM_CLONES must be set: clone-all.sh defaults to $PWD/clones, NOT $GITPODIUM_OUT/clones.
"$GP/bin/clone-all.sh"  <owners...>          # or: -f repos.txt   (idempotent; re-run updates)
"$GP/bin/build-mailmap.py" "$GITPODIUM_CLONES"
"$GP/bin/collect.sh"       "$GITPODIUM_CLONES"
"$GP/bin/rollup.sh"
"$GP/bin/collect-github.py" <owners...>      # PRs/reviews/issues -> github.json (gh API; skip w/ GITPODIUM_SKIP_GITHUB=1)
"$GP/bin/build-report.py"                    # -> $GITPODIUM_OUT/report.html (embeds both datasets)
```
(Equivalent one-shot: `"$GP/gitpodium" run <owners...>` after exporting the env vars —
`run` includes the GitHub step best-effort, so the git report still builds if the API fails.)

## Step 7 — Review identities (offer, don't force)

After `build-mailmap.py`, it prints how many identities merged and writes
`mailmap-review.md` — low-confidence guesses (one name is a prefix of another) left
**un**merged. Offer to show it. If the user confirms any merges, write them into a
`gitpodium.identity.json` (`force_merge` / `canonical_override` / `extra_bots` — see
`examples/gitpodium.identity.json`), set `GITPODIUM_IDENTITY` to it, and re-run
`build-mailmap.py` → `collect.sh` → `rollup.sh` → `build-report.py`.

## Step 8 — Deliver

- Check `$GITPODIUM_OUT/clone-failures.log` first — repos that failed to clone/update are
  listed there and the run continues without them. If it's non-empty, tell the user which
  repos are missing from the report.
- Point the user to `report.html` (they open it in any browser).
- Narrate the top few contributors with `"$GP/bin/report.sh"` (respects the same
  window/filter env). The transparency line shows how many commits/churn were dropped
  as bulk/bots — mention it so nothing looks hidden.
- Point out the **Collaboration tab** (if `github.json` was built): the top reviewers and
  the "churn-blind reviewers" count — people who review a lot but open few PRs, whom the
  git leaderboard misses entirely. This is the headline reason to look past churn.
- **ALWAYS close with the caveat** (non-negotiable):

> Churn ≠ contribution. Code review, mentoring, design, and debugging are invisible to
> git; squash-merged/deleted branches are unrecoverable. The Collaboration tab recovers
> *some* of that (reviews, PRs, issues) but not all of it. This is a
> **conversation-starter, not a stack-rank or a performance metric.**

## Quick reference (flag ↔ interview answer)

| Interview answer | Wiring |
|---|---|
| Owners / repos | `clone-all.sh <owner...>` or `-f repos.txt` |
| Metric (git churn view) | `GITPODIUM_METRIC=churn\|commits\|added\|deleted\|net\|repos` |
| Collaboration (PRs/reviews/issues) | `collect-github.py <owner...>` → `github.json` · skip: `GITPODIUM_SKIP_GITHUB=1` |
| Window / bucket | `report.sh FROM TO [month\|quarter\|year]` |
| Bots / bulk filters | `DROP_BOTS` `MAXCHURN` `MAXFILES` |
| Identity merges | `GITPODIUM_IDENTITY=gitpodium.identity.json` |
| Output dir | `GITPODIUM_OUT` (clones dir: `GITPODIUM_CLONES`) |
