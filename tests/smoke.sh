#!/usr/bin/env bash
# gitpodium smoke test — builds a tiny fixture repo, runs the offline pipeline
# (mailmap -> collect -> rollup -> rank -> report) and asserts the leaderboard.
# No network: the clone and GitHub steps are skipped on purpose.
set -euo pipefail
GP="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

fixture="clones/fixture"
mkdir -p "$fixture"
git -C "$fixture" init -q
git -C "$fixture" config user.name  "Alice Example"
git -C "$fixture" config user.email "alice@example.com"
printf 'one\ntwo\n' > "$fixture/a.txt"
git -C "$fixture" add a.txt
git -C "$fixture" commit -qm "first"
printf 'three\nfour\nfive\n' > "$fixture/b.txt"
git -C "$fixture" add b.txt
git -C "$fixture" -c user.name="Bob Builder" -c user.email="bob@example.com" commit -qm "second"

"$GP/gitpodium" mailmap
"$GP/gitpodium" collect
"$GP/gitpodium" rollup

rank_out="$("$GP/gitpodium" rank)"
printf '%s\n' "$rank_out"
printf '%s\n' "$rank_out" | grep -q "Alice Example" || { echo "FAIL: Alice Example missing from rank output" >&2; exit 1; }
printf '%s\n' "$rank_out" | grep -q "Bob Builder"   || { echo "FAIL: Bob Builder missing from rank output" >&2; exit 1; }

"$GP/gitpodium" report
# -F + '=[': match the baked-in data assignment, not the template's static JS reads
grep -qF "window.__GITPODIUM_DATA__=[" report.html || { echo "FAIL: report.html missing embedded data" >&2; exit 1; }
grep -qi "^<!doctype html>" report.html  || { echo "FAIL: report.html missing doctype" >&2; exit 1; }

echo "smoke OK"
