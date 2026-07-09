#!/usr/bin/env python3
"""gitpodium — draft a .mailmap so one person split across multiple git identities
(name/email variants) collapses to a single contributor in the leaderboard.

Automatic merges (safe, no config needed):
  1. shared real (non-generic) email        -> same person
  2. identical normalized display name       -> same person
  3. non-human committers                     -> automation[bot] (dropped by DROP_BOTS=1)

Optional overrides via a JSON config (env GITPODIUM_IDENTITY or --config <file>):
  {
    "force_merge":         [["janedoe", "jane-doe-corp"]],   # normalized names that are one person
    "canonical_override":  {"acmebot": ["Jane Doe", "jane@acme.com"]},  # pin a cluster's identity
    "extra_bots":          ["ci-runner", "release-bot"]      # extra non-human names to exclude
  }

Residual low-confidence guesses (one name is a prefix of another, different emails) are
left UNMERGED and listed in mailmap-review.md for optional follow-up.

Outputs -> $GITPODIUM_OUT/.mailmap  and  $GITPODIUM_OUT/mailmap-review.md
Usage: build-mailmap.py [clones-dir] [--config identity.json]
"""
import os, re, sys, json, subprocess, unicodedata
from collections import Counter, defaultdict

argv = sys.argv[1:]
CONFIG = os.environ.get("GITPODIUM_IDENTITY")
if "--config" in argv:
    i = argv.index("--config"); CONFIG = argv[i + 1]; del argv[i:i + 2]
ROOT = argv[0] if argv else os.environ.get("GITPODIUM_CLONES", "clones")
OUT_DIR = os.environ.get("GITPODIUM_OUT") or os.getcwd()

cfg = {}
if CONFIG:
    with open(CONFIG) as f:
        cfg = json.load(f)
FORCE_MERGE = [set(g) for g in cfg.get("force_merge", [])]
CANONICAL_OVERRIDE = {k: tuple(v) for k, v in cfg.get("canonical_override", {}).items()}
DEFAULT_BOTS = {"claude", "workstation", "agent-crew"}
EXTRA_BOTS = {str(b).strip().lower() for b in cfg.get("extra_bots", [])}
BOT_NAMES = DEFAULT_BOTS | EXTRA_BOTS


def norm_name(n):
    n = n.replace('đ', 'd').replace('Đ', 'D')
    n = unicodedata.normalize('NFKD', n)
    n = ''.join(c for c in n if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', n.lower())


def is_generic(email):
    """Shared/placeholder email — unsafe to auto-merge two *different* people on."""
    e = (email or '').lower()
    if not e or '@' not in e:
        return True
    if e.endswith('@users.noreply.github.com'):      # per-user unique -> SAFE
        return False
    local, _, host = e.partition('@')
    if host in ('example.com', 'example.org', 'localhost', 'localhost.localdomain', 'github.com'):
        return True
    if local in ('root', 'ubuntu', 'ec2-user', 'admin', 'git', 'jenkins', 'runner',
                 'builder', 'node', 'www-data', 'user'):
        return True
    if 'noreply' in local or 'no-reply' in local:
        return True
    if re.search(r'(^|[.-])ip-\d', host) or 'compute.internal' in host \
       or host.endswith('.internal') or host.endswith('.local'):
        return True
    return False


def is_nonhuman(name, email):
    n = (name or '').strip().lower()
    e = (email or '').lower()
    local = e.partition('@')[0]
    if e == 'noreply@anthropic.com':
        return True
    if n in BOT_NAMES or local in BOT_NAMES:
        return True
    return False


# 1) collect raw identities (no mailmap) with commit counts
counts = Counter()
dirs = [d for d in sorted(os.listdir(ROOT)) if os.path.isdir(os.path.join(ROOT, d, '.git'))]
for d in dirs:
    p = os.path.join(ROOT, d)
    try:
        out = subprocess.run(['git', '-C', p, 'log', '--all', '--no-merges', '--pretty=%an%x09%ae'],
                             capture_output=True, text=True, timeout=180).stdout
    except Exception:
        continue
    for line in out.splitlines():
        if '\t' not in line:
            continue
        name, email = line.split('\t', 1)
        counts[(name.strip(), email.strip().lower())] += 1

idents = list(counts)

# 2) union-find
parent = {i: i for i in idents}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb

by_email = defaultdict(list)     # (a) shared non-generic email
for i in idents:
    if not is_generic(i[1]):
        by_email[i[1]].append(i)
for grp in by_email.values():
    for other in grp[1:]:
        union(grp[0], other)

norm_index = defaultdict(list)   # (b) identical normalized name
for i in idents:
    nn = norm_name(i[0])
    if nn:
        norm_index[nn].append(i)
for grp in norm_index.values():
    for other in grp[1:]:
        union(grp[0], other)

for group in FORCE_MERGE:        # (c) manual overrides
    reps = [i for nn in group for i in norm_index.get(nn, [])]
    for other in reps[1:]:
        union(reps[0], other)

clusters = defaultdict(list)
for i in idents:
    clusters[find(i)].append(i)


def canonical(members):
    """(display_name, email): email = most commits; name prefers a spaced real name."""
    for (n, e) in members:
        ov = CANONICAL_OVERRIDE.get(norm_name(n))
        if ov:
            return ov
    cid = max(members, key=lambda m: counts[m])
    names = defaultdict(int)
    for (n, e) in members:
        names[n] += counts[(n, e)]
    spaced = {n: c for n, c in names.items() if ' ' in n.strip()}
    pick = max((spaced or names).items(), key=lambda kv: kv[1])[0]
    return pick, cid[1]


# 3) write .mailmap
mailmap = ["# Auto-generated by gitpodium build-mailmap.py.",
           "# Merges: shared-email + same-name + force_merge. Non-human committers -> automation[bot].", ""]
human_merges = 0
nonhuman_aliases = []
for members in clusters.values():
    if any(is_nonhuman(n, e) for (n, e) in members):
        for (n, e) in members:
            nonhuman_aliases.append(f"automation[bot] <automation@localhost> {n} <{e}>")
        continue
    if len(members) == 1:
        continue
    human_merges += 1
    cname, cemail = canonical(members)
    mailmap.append(f"{cname} <{cemail}>")
    for (n, e) in members:
        if (n, e) != (cname, cemail):
            mailmap.append(f"{cname} <{cemail}> {n} <{e}>")
if nonhuman_aliases:
    mailmap += ["", "# --- non-human committers (excluded) ---", "automation[bot] <automation@localhost>"]
    mailmap += nonhuman_aliases
with open(os.path.join(OUT_DIR, ".mailmap"), "w") as f:
    f.write("\n".join(mailmap) + "\n")

# 4) residual review — prefix-name guesses still in different clusters
canon = {root: canonical(m) for root, m in clusters.items()}
ccommits = {root: sum(counts[m] for m in ms) for root, ms in clusters.items()}
names = [(norm_name(cn), root) for root, (cn, ce) in canon.items()
         if len(norm_name(cn)) >= 4 and not any(is_nonhuman(*m) for m in clusters[root])]
seen = set(); residual = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, ra = names[i]; b, rb = names[j]
        if find(clusters[ra][0]) == find(clusters[rb][0]) or a == b:
            continue
        if (a.startswith(b) or b.startswith(a)) and frozenset((ra, rb)) not in seen:
            seen.add(frozenset((ra, rb))); residual.append((ra, rb))
rev = ["# Residual review — OPTIONAL (low-confidence, left UNMERGED)", "",
       "One display name is a prefix of another with different emails — maybe the same",
       "person, maybe not. If correct, add them to force_merge in your identity config and re-run.", ""]
for ra, rb in sorted(residual, key=lambda p: -(ccommits[p[0]] + ccommits[p[1]])):
    (na, ea), (nb, eb) = canon[ra], canon[rb]
    rev.append(f'- "{na}" <{ea}> ({ccommits[ra]} c)  ~  "{nb}" <{eb}> ({ccommits[rb]} c)')
with open(os.path.join(OUT_DIR, "mailmap-review.md"), "w") as f:
    f.write("\n".join(rev) + "\n")

# 5) summary
humans = sum(1 for ms in clusters.values() if not any(is_nonhuman(*m) for m in ms))
print(f"raw identities (name+email):     {len(idents)}")
print(f"distinct people after merges:    {humans}")
print(f"  multi-identity people merged:  {human_merges}")
print(f"non-human clusters -> bot:       {sum(1 for ms in clusters.values() if any(is_nonhuman(*m) for m in ms))}")
print(f"residual prefix guesses (review):{len(residual)}")
print(f"\nwrote {OUT_DIR}/.mailmap  and  {OUT_DIR}/mailmap-review.md")
