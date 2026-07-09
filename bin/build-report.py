#!/usr/bin/env python3
"""gitpodium — bake monthly.json into the HTML template to produce a single,
self-contained report.html: one file, no server, no separate data file. Opens
straight from the filesystem (double-click) and is safe to email/Slack/host as-is.

Usage: build-report.py [monthly.json] [report.html]
  defaults: $GITPODIUM_OUT/monthly.json  ->  $GITPODIUM_OUT/report.html
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("GITPODIUM_OUT") or os.getcwd()
TEMPLATE = os.path.join(HERE, "..", "template", "report.template.html")
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, "monthly.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT_DIR, "report.html")
MARKER = "<!-- __GITPODIUM_DATA_SLOT__ -->"

if not os.path.exists(DATA):
    sys.exit(f"error: {DATA} not found — run collect.sh + rollup.sh first.")
tpl = open(TEMPLATE, encoding="utf-8").read()
if MARKER not in tpl:
    sys.exit(f"error: template {TEMPLATE} is missing the data-slot marker.")
raw = open(DATA, encoding="utf-8").read().strip()
# '<' only occurs inside JSON string values, where < is valid — this makes an
# embedded "</script>" impossible without changing the parsed data.
safe = raw.replace("<", "\\u003c")
html = tpl.replace(MARKER, f"<script>window.__GITPODIUM_DATA__={safe};</script>")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {OUT}  ({os.path.getsize(OUT) // 1024} KB, self-contained — open it in any browser)")
