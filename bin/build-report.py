#!/usr/bin/env python3
"""gitpodium — bake monthly.json into the HTML template to produce a single,
self-contained report.html: one file, no server, no separate data file. Opens
straight from the filesystem (double-click) and is safe to email/Slack/host as-is.

Usage: build-report.py [monthly.json] [report.html]
  defaults: $GITPODIUM_OUT/monthly.json  ->  $GITPODIUM_OUT/report.html
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("GITPODIUM_OUT") or os.getcwd()
TEMPLATE = os.path.join(HERE, "..", "template", "report.template.html")
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, "monthly.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT_DIR, "report.html")
GITHUB = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT_DIR, "github.json")
MARKER = "<!-- __GITPODIUM_DATA_SLOT__ -->"


def embed_safe(path, validate=False):
    raw = open(path, encoding="utf-8").read().strip()
    if validate:
        json.loads(raw)   # raises on truncated/invalid JSON — caller decides to skip
    # '<' only occurs inside JSON string values, where < is valid — this makes an
    # embedded "</script>" impossible without changing the parsed data.
    return raw.replace("<", "\\u003c")


if not os.path.exists(DATA):
    sys.exit(f"error: {DATA} not found — run collect.sh + rollup.sh first.")
tpl = open(TEMPLATE, encoding="utf-8").read()
if MARKER not in tpl:
    sys.exit(f"error: template {TEMPLATE} is missing the data-slot marker.")
safe = embed_safe(DATA)
# Optional agent-chosen default metric (the report still lets viewers switch live).
METRICS = {"churn", "commits", "added", "deleted", "net", "repos"}
metric = (os.environ.get("GITPODIUM_METRIC") or "").strip().lower()
mjs = f'window.__GITPODIUM_METRIC__="{metric}";' if metric in METRICS else ""
# Optional GitHub collaboration data (PRs/reviews/issues). Additive: the Collaboration
# tab only appears when this is present. Validate first — a truncated github.json must NOT
# take the core report's <script> down with it (it's embedded in the same block).
gjs = ""
if os.path.exists(GITHUB):
    try:
        gjs = f"window.__GITPODIUM_GITHUB__={embed_safe(GITHUB, validate=True)};"
    except (ValueError, OSError) as e:
        sys.stderr.write(f"warning: ignoring {GITHUB} ({e}) — Collaboration tab omitted.\n")
html = tpl.replace(MARKER, f"<script>{mjs}{gjs}window.__GITPODIUM_DATA__={safe};</script>")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {OUT}  ({os.path.getsize(OUT) // 1024} KB, self-contained — open it in any browser)")
