#!/usr/bin/env python3
"""gitpodium — collect GitHub *collaboration* activity per login via the gh GraphQL API.

This is the platform-metadata companion to the git-history collector (collect.sh).
Pull requests, code reviews, review comments and issues never touch git, so churn is
blind to them — a heavy reviewer who opens few PRs is invisible to a commit leaderboard.
This surfaces that work.

Writes $GITPODIUM_OUT/github.json — one record per (month, login):
  [{"month":"YYYY-MM","login":..,"prs_opened":n,"prs_merged":n,
    "reviews":n,"review_comments":n,"issues":n}, ...]

Usage:
  collect-github.py <owner> [owner...]      # orgs and/or users (same as clone-all.sh)
  collect-github.py -f repos.txt            # explicit "owner/repo" per line (# comments ok)
  GITPODIUM_ORGS="a b" collect-github.py    # owners via env instead of args

Honors: DROP_BOTS (default 1), GITPODIUM_IDENTITY (its "extra_bots" list), GITPODIUM_OUT.
Only works for GitHub-hosted repos the gh token can see; subject to the GraphQL rate limit.
"""
import os, sys, json, shutil, subprocess, collections

OUT_DIR = os.environ.get("GITPODIUM_OUT") or os.getcwd()
DROP_BOTS = os.environ.get("DROP_BOTS", "1") != "0"

# Machine accounts GitHub reports as __typename "User" (so the Bot check misses them).
DEFAULT_BOT_LOGINS = {"web-flow", "ghost"}

# Two independent connections paginated in separate loops — a single query holding both
# would re-fetch the finished stream (and its heavy nested reviews) on every remaining page.
# reviews(first:100) is intentionally un-paginated: a PR with >100 review submissions
# truncates the overflow (rare; the page-cap note covers the analogous PR/issue case).
PR_QUERY = """
query($owner:String!, $repo:String!, $cur:String) {
  repository(owner:$owner, name:$repo) {
    pullRequests(first:50, after:$cur) {
      pageInfo { hasNextPage endCursor }
      nodes {
        merged
        createdAt
        mergedAt
        author { __typename login }
        reviews(first:100) {
          nodes { author { __typename login } submittedAt comments { totalCount } }
        }
      }
    }
  }
}
"""

ISSUE_QUERY = """
query($owner:String!, $repo:String!, $cur:String) {
  repository(owner:$owner, name:$repo) {
    issues(first:100, after:$cur) {
      pageInfo { hasNextPage endCursor }
      nodes { createdAt author { __typename login } }
    }
  }
}
"""


def load_extra_bots():
    bots = set(DEFAULT_BOT_LOGINS)
    p = os.environ.get("GITPODIUM_IDENTITY")
    if p and os.path.exists(p):
        try:
            j = json.load(open(p, encoding="utf-8"))
            bots |= {str(b).lower() for b in j.get("extra_bots", [])}
        except Exception as e:  # noqa: BLE001 - config is best-effort
            sys.stderr.write(f"warning: could not read {p}: {e}\n")
    return bots


EXTRA_BOTS = load_extra_bots()


def login_of(actor):
    """Return a human login, or None if the actor is missing or a bot."""
    if not actor:
        return None
    if DROP_BOTS and actor.get("__typename") == "Bot":
        return None
    login = actor.get("login")
    if not login:
        return None
    low = login.lower()
    if DROP_BOTS and (low.endswith("[bot]") or low in EXTRA_BOTS):
        return None
    return login


def month(ts):
    return ts[:7] if ts and len(ts) >= 7 else None


def gql(query, owner, repo, cur):
    args = ["gh", "api", "graphql", "-F", f"owner={owner}", "-F", f"repo={repo}",
            "-F", "query=" + query]
    if cur:
        args += ["-F", f"cur={cur}"]
    r = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip().replace("\n", " ")[:160]
        sys.stderr.write(f"  ! {owner}/{repo}: {err}\n")
        return None
    return json.loads(r.stdout)["data"]["repository"]


def paginate(query, owner, repo, key, maxpages, handle):
    """Walk one connection to exhaustion. Returns (pages, capped)."""
    cur, pages = None, 0
    while pages < maxpages:
        d = gql(query, owner, repo, cur)
        if d is None:
            return pages, False   # per-repo error already logged; give up on this stream
        pages += 1
        blk = d[key]
        handle(blk["nodes"])
        if not blk["pageInfo"]["hasNextPage"]:
            return pages, False
        cur = blk["pageInfo"]["endCursor"]
    return pages, True            # hit the page cap with more to fetch


def discover_repos(argv):
    """Mirror clone-all.sh: -f file | owner args | GITPODIUM_ORGS -> list of (owner, repo)."""
    repo_file, owners = None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__); sys.exit(0)
        if a in ("-f", "--repos-file"):
            if i + 1 >= len(argv):
                sys.exit("error: -f needs a file")
            repo_file = argv[i + 1]; i += 2; continue
        owners.append(a); i += 1
    if not owners and os.environ.get("GITPODIUM_ORGS"):
        owners = os.environ["GITPODIUM_ORGS"].split()

    nwos = []
    if repo_file:
        for line in open(repo_file, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                nwos.append(line)
    for owner in owners:
        # --source: skip forks, mirroring clone-all.sh — a fork's upstream history
        # isn't this owner's work. Add a specific fork via -f repos.txt.
        r = subprocess.run(
            ["gh", "repo", "list", owner, "--source", "--limit", "1000",
             "--json", "nameWithOwner", "-q", ".[].nameWithOwner"],
            capture_output=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            sys.stderr.write(f"  ! gh repo list {owner}: {r.stderr.strip()[:160]}\n")
            continue
        found = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        if len(found) >= 1000:
            sys.stderr.write(f"  ! {owner} returned 1000 repos — gh list cap hit, some may be missing\n")
        nwos += found

    seen, pairs = set(), []
    for nwo in sorted(set(nwos)):
        if "/" not in nwo or nwo in seen:
            continue
        seen.add(nwo)
        o, rp = nwo.split("/", 1)
        pairs.append((o, rp))
    return pairs


def main():
    if not shutil.which("gh"):
        sys.exit("error: gh (GitHub CLI) not found — https://cli.github.com")
    pairs = discover_repos(sys.argv[1:])
    if not pairs:
        sys.exit("usage: collect-github.py <owner...> | -f repos.txt   (needs gh auth)")

    # counters keyed by (month, login)
    pr_open = collections.Counter()
    pr_merged = collections.Counter()
    reviews = collections.Counter()
    rev_comments = collections.Counter()
    issues = collections.Counter()

    def handle_prs(nodes):
        for n in nodes:
            author = login_of(n.get("author"))
            if author:
                m = month(n.get("createdAt"))
                if m:
                    pr_open[(m, author)] += 1
                if n.get("merged"):
                    mm = month(n.get("mergedAt")) or m
                    if mm:
                        pr_merged[(mm, author)] += 1
            # One review credit per (PR, reviewer): earliest review's month;
            # sum that reviewer's inline comments on the PR. Skip self-reviews.
            per_reviewer = {}
            for rv in n["reviews"]["nodes"]:
                rl = login_of(rv.get("author"))
                if not rl or rl == author:
                    continue
                cur = per_reviewer.get(rl)
                sub = rv.get("submittedAt")
                c = (rv.get("comments") or {}).get("totalCount", 0) or 0
                if cur is None:
                    per_reviewer[rl] = [sub, c]
                else:
                    if sub and (cur[0] is None or sub < cur[0]):
                        cur[0] = sub
                    cur[1] += c
            for rl, (sub, c) in per_reviewer.items():
                # pending-only reviews have no submittedAt — credit the PR's month
                m = month(sub) or month(n.get("createdAt"))
                if not m:
                    continue
                reviews[(m, rl)] += 1
                rev_comments[(m, rl)] += c

    def handle_issues(nodes):
        for n in nodes:
            a = login_of(n.get("author"))
            m = month(n.get("createdAt"))
            if a and m:
                issues[(m, a)] += 1

    for owner, repo in pairs:
        pr_pages, pr_capped = paginate(PR_QUERY, owner, repo, "pullRequests", 80, handle_prs)
        iss_pages, iss_capped = paginate(ISSUE_QUERY, owner, repo, "issues", 40, handle_issues)
        capped = " — PAGE CAP HIT, counts truncated" if pr_capped or iss_capped else ""
        sys.stderr.write(f"  ✓ {owner}/{repo} ({pr_pages}+{iss_pages} pages){capped}\n")

    # merge counters into (month, login) records
    keys = set(pr_open) | set(pr_merged) | set(reviews) | set(rev_comments) | set(issues)
    records = []
    for (m, login) in sorted(keys):
        records.append({
            "month": m, "login": login,
            "prs_opened": pr_open[(m, login)],
            "prs_merged": pr_merged[(m, login)],
            "reviews": reviews[(m, login)],
            "review_comments": rev_comments[(m, login)],
            "issues": issues[(m, login)],
        })

    out = os.path.join(OUT_DIR, "github.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=0, separators=(",", ":"))
        f.write("\n")

    # console summary: top collaborators all-time (reviews + PRs)
    tot = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in records:
        t = tot[r["login"]]
        t[0] += r["prs_opened"]; t[1] += r["prs_merged"]
        t[2] += r["reviews"]; t[3] += r["review_comments"]; t[4] += r["issues"]
    ranked = sorted(tot.items(), key=lambda kv: -(kv[1][0] + kv[1][2]))
    sys.stderr.write(f"\nwrote {out}  ({len(records)} month-rows, {len(tot)} people, {len(pairs)} repos)\n")
    sys.stderr.write(f"\n{'login':22} {'PRs':>5} {'merged':>7} {'reviews':>8} {'rev-cmts':>9} {'issues':>7}\n")
    sys.stderr.write("-" * 62 + "\n")
    for login, t in ranked[:20]:
        sys.stderr.write(f"{login:22} {t[0]:5} {t[1]:7} {t[2]:8} {t[3]:9} {t[4]:7}\n")


if __name__ == "__main__":
    main()
