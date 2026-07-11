#!/usr/bin/env bash
# gitpodium — clone (or fetch-update) every repo from the given GitHub OWNERS
# (organizations OR users) into $GITPODIUM_CLONES/, one dir per repo named
# "<owner>__<repo>". Full history, all branches. Idempotent (re-run to update).
# Uses the `gh` CLI's authenticated token.
#
# Usage:
#   clone-all.sh <owner> [owner...]        # e.g. clone-all.sh acme-inc acme-labs
#   clone-all.sh -f repos.txt              # explicit "owner/repo" per line (# comments ok)
#   GITPODIUM_ORGS="a b" clone-all.sh      # owners via env instead of args
#   GITPODIUM_CLONES=/path clone-all.sh …  # override clone dir (default ./clones)
set -uo pipefail   # NOT -e: continue past individual repo failures

DEST="${GITPODIUM_CLONES:-$PWD/clones}"
OUT_DIR="${GITPODIUM_OUT:-$PWD}"
FAIL="$OUT_DIR/clone-failures.log"

REPO_FILE=""; OWNERS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -f|--repos-file) REPO_FILE="${2:?-f needs a file}"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) OWNERS+=("$1"); shift ;;
  esac
done
if [ ${#OWNERS[@]} -eq 0 ] && [ -n "${GITPODIUM_ORGS:-}" ]; then
  read -r -a OWNERS <<< "$GITPODIUM_ORGS"
fi
if [ ${#OWNERS[@]} -eq 0 ] && [ -z "$REPO_FILE" ]; then
  echo "usage: clone-all.sh <owner> [owner...]   |   clone-all.sh -f repos.txt" >&2; exit 2
fi
command -v gh >/dev/null || { echo "error: gh (GitHub CLI) not found — https://cli.github.com" >&2; exit 1; }

mkdir -p "$DEST"; : > "$FAIL"

clone_one() {
  local nwo="$1" dest="$2"
  local dir="$dest/${nwo/\//__}"
  if [ -d "$dir/.git" ]; then
    if git -C "$dir" fetch --all --prune --quiet 2>/dev/null; then echo "updated  $nwo"
    else echo "FETCHERR $nwo"; echo "$nwo (fetch)" >> "$FAIL"; fi
    return
  fi
  # `gh repo clone` uses the authenticated token; flags after -- go to `git clone`.
  if gh repo clone "$nwo" "$dir" -- --quiet 2>/dev/null; then echo "cloned   $nwo"
  else echo "CLONEERR $nwo"; echo "$nwo (clone)" >> "$FAIL"; fi
}
export -f clone_one
export FAIL

{
  [ -n "$REPO_FILE" ] && grep -vE '^\s*(#|$)' "$REPO_FILE"
  for owner in "${OWNERS[@]:-}"; do
    [ -n "$owner" ] || continue
    # --source: skip forks — a fork imports its entire upstream author history and
    # would double-count shared commits. Add a specific fork via -f repos.txt.
    repos="$(gh repo list "$owner" --source --limit 1000 --json nameWithOwner -q '.[].nameWithOwner')"
    [ "$(printf '%s\n' "$repos" | grep -c .)" -ge 1000 ] && \
      echo "WARNING: $owner returned 1000 repos — gh list cap hit, some may be missing" >&2
    [ -n "$repos" ] && printf '%s\n' "$repos"
  done
} | sort -u | xargs -P 8 -I{} bash -c 'clone_one "$@"' _ {} "$DEST"

echo "----------------------------------------"
echo "clones dir : $DEST"
echo "repo count : $(find "$DEST" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')"
echo "disk usage : $(du -sh "$DEST" 2>/dev/null | cut -f1)"
if [ -s "$FAIL" ]; then echo "FAILURES   : see $FAIL"; cat "$FAIL"; else echo "failures   : none"; fi
