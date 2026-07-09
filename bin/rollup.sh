#!/usr/bin/env bash
# gitpodium — monthly per-author rollup for the HTML leaderboard.
# Reads $GITPODIUM_OUT/contrib-commits.tsv (collect.sh), applies bot + bulk/vendor
# filters, and writes monthly.csv + monthly.json (the report's data feed).
# Record: month(YYYY-MM), author, added, deleted, churn, commits, repos(distinct that month)
# Rows sorted month ascending, then churn descending (= per-month leaderboard order).
#
# Tunable filters (env vars):
#   MAXCHURN=10000  drop any single commit with added+deleted above this  (vendor/generated imports)
#   MAXFILES=400    drop any single commit touching more files than this
#   DROP_BOTS=1     exclude *[bot] accounts (0 to keep them)
# Set MAXCHURN=0 MAXFILES=0 to disable the bulk filter and see raw numbers.
set -euo pipefail
OUT_DIR="${GITPODIUM_OUT:-$PWD}"
TSV="$OUT_DIR/contrib-commits.tsv"
[ -f "$TSV" ] || { echo "missing $TSV — run collect.sh <clones> first" >&2; exit 1; }
MAXCHURN="${MAXCHURN:-10000}"; MAXFILES="${MAXFILES:-400}"; DROP_BOTS="${DROP_BOTS:-1}"

# Aggregate to month+author, tracking distinct repos, then sort into leaderboard order.
recs="$(
  awk -F'\t' -v mc="$MAXCHURN" -v mf="$MAXFILES" -v db="$DROP_BOTS" '
    NR>1 {
      if(db && $3 ~ /\[bot\]$/)          next     # bots
      if(mc>0 && ($4+$5)>mc)             next     # bulk/vendor/generated import
      if(mf>0 && $6>mf)                  next
      m=substr($2,1,7); if(length(m)<7)  next
      k=m SUBSEP $3
      add[k]+=$4; del[k]+=$5; com[k]++
      rk=k SUBSEP $1; if(!(rk in seen)){ seen[rk]=1; rep[k]++ }
    }
    END{ for(k in add){ split(k,a,SUBSEP)
      printf "%s\t%s\t%d\t%d\t%d\t%d\t%d\n", a[1],a[2],add[k],del[k],add[k]+del[k],com[k],rep[k] } }
  ' "$TSV" | sort -t$'\t' -k1,1 -k5,5nr
)"

# CSV (author quoted; embedded quotes doubled per RFC 4180)
{
  echo "month,author,added,deleted,churn,commits,repos"
  printf '%s\n' "$recs" | awk -F'\t' '{ a=$2; gsub(/"/,"\"\"",a); printf "%s,\"%s\",%d,%d,%d,%d,%d\n",$1,a,$3,$4,$5,$6,$7 }'
} > "$OUT_DIR/monthly.csv"

# JSON (flat array of records; backslash + quote escaped, UTF-8 preserved)
printf '%s\n' "$recs" | awk -F'\t' '
  BEGIN{ printf "[\n" }
  { a=$2; gsub(/\\/,"\\\\",a); gsub(/"/,"\\\"",a)
    sep = (NR>1) ? ",\n" : ""
    printf "%s  {\"month\":\"%s\",\"author\":\"%s\",\"added\":%d,\"deleted\":%d,\"churn\":%d,\"commits\":%d,\"repos\":%d}", sep,$1,a,$3,$4,$5,$6,$7 }
  END{ printf "\n]\n" }
' > "$OUT_DIR/monthly.json"

echo "wrote:"
echo "  $OUT_DIR/monthly.csv   ($(($(wc -l < "$OUT_DIR/monthly.csv")-1)) rows)"
echo "  $OUT_DIR/monthly.json"
