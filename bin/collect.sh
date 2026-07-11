#!/usr/bin/env bash
# gitpodium — temporal contribution collector: one row PER COMMIT across ALL branches
# of every cloned repo, stamped with the AUTHOR DATE, so you can slice/accumulate by
# any time period downstream.
# Output (TSV) -> $GITPODIUM_OUT/contrib-commits.tsv :  repo  date  author  added  deleted  files  sha
#   date          = author date (when the code was written), YYYY-MM-DD
#   added/deleted = per-commit line changes (numstat, NOT blame) — the only line metric with a time axis
# Usage: collect.sh <dir-of-clones>
set -euo pipefail
ROOT="${1:?usage: collect.sh <dir-of-clones>}"
OUT_DIR="${GITPODIUM_OUT:-$PWD}"
OUT="$OUT_DIR/contrib-commits.tsv"
# Optional shared identity map from build-mailmap.py; use it if present.
MM=(); [ -f "$OUT_DIR/.mailmap" ] && MM=(-c "mailmap.file=$OUT_DIR/.mailmap")
EXCLUDES=(   # vendored / generated / lockfiles / minified — so LOC can't be gamed
  ':(exclude)vendor/**' ':(exclude)third_party/**' ':(exclude)node_modules/**'
  ':(glob,exclude)**/*.min.js' ':(glob,exclude)**/*.min.css'
  ':(glob,exclude)**/package-lock.json' ':(glob,exclude)**/yarn.lock'
  ':(glob,exclude)**/pnpm-lock.yaml' ':(glob,exclude)**/*.lock'
  ':(glob,exclude)**/dist/**' ':(glob,exclude)**/build/**'
)
printf 'repo\tdate\tauthor\tadded\tdeleted\tfiles\tsha\n' > "$OUT"
for dir in "$ROOT"/*/; do
  [ -e "$dir/.git" ] || continue
  repo="$(basename "$dir")"
  # ONE rev-walk over all refs (dedups shared commits). Header line prefixed '@'
  # to distinguish it from numstat rows. --date=short => author date YYYY-MM-DD.
  # Sum numstat per commit, then flush one TSV row.
  # ${MM[@]+...}: empty-array expansion is an "unbound variable" under set -u on bash 3.2 (stock macOS)
  git ${MM[@]+"${MM[@]}"} -C "${dir%/}" log --all --no-merges --use-mailmap --numstat \
      --date=short --pretty=format:'@%H%x09%ad%x09%aN' -- . "${EXCLUDES[@]}" 2>/dev/null \
  | awk -F'\t' -v repo="$repo" '
      function flush(){ if (sha!="") printf "%s\t%s\t%s\t%d\t%d\t%d\t%s\n", repo, date, author, add, del, files, sha }
      /^@/ { flush(); sha=substr($1,2); date=$2; author=$3; add=0; del=0; files=0; next }
      NF==3 { files++; if ($1 ~ /^[0-9]+$/) { add+=$1; del+=$2 } }   # numstat ("-" = binary, skip counts)
      END  { flush() }
    ' >> "$OUT" \
  || echo "WARN: git log failed in $repo — skipped (rows above it kept)" >&2
done
echo "wrote $OUT  ($(( $(wc -l < "$OUT") - 1 )) commits)"
