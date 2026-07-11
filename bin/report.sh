#!/usr/bin/env bash
# gitpodium — console leaderboard from the temporal data ($GITPODIUM_OUT/contrib-commits.tsv).
# Ranks contributors in any date window, optionally bucketed by period, with bot +
# bulk-commit filtering so vendored/generated dumps don't crown a "winner".
#
# Usage:
#   report.sh                              # all-time leaderboard (filtered)
#   report.sh 2025-01-01 2025-06-30        # window
#   report.sh 2025-01-01 2025-12-31 month  # per-month per-author breakdown
#   report.sh 2024 2025 quarter            # quarterly
#   report.sh 0000 9999 year               # yearly
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
case "${1:-}" in -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
FROM="${1:-0000-00-00}"; TO="${2:-9999-99-99}"; BY="${3:-}"
# Pad year / year-month bounds to full dates: awk compares strings, and
# "2025-01-01" > "2025" would silently drop the whole ending year.
case ${#FROM} in 4) FROM="$FROM-00-00" ;; 7) FROM="$FROM-00" ;; esac
case ${#TO}   in 4) TO="$TO-99-99"     ;; 7) TO="$TO-99"     ;; esac
MAXCHURN="${MAXCHURN:-10000}"; MAXFILES="${MAXFILES:-400}"; DROP_BOTS="${DROP_BOTS:-1}"

# keep(): the shared inclusion predicate.  $2 date, $3 author, $4 added, $5 deleted, $6 files, $7 sha
# DUP: same sha in two clones (mirrored/duplicated repo) counts once.
FILT='function keep(){ if(DUP[$7]++) return 0;
        if($2<from||$2>to) return 0;
        if(db && $3 ~ /\[bot\]$/) return 0;
        if(mc>0 && ($4+$5)>mc) return 0;
        if(mf>0 && $6>mf) return 0;
        return 1 }'

echo "window: $FROM .. $TO   filters: MAXCHURN=$MAXCHURN MAXFILES=$MAXFILES DROP_BOTS=$DROP_BOTS"
# --- transparency: what got excluded (no silent truncation) ---
awk -F'\t' -v from="$FROM" -v to="$TO" -v mc="$MAXCHURN" -v mf="$MAXFILES" -v db="$DROP_BOTS" '
  NR>1 && $2>=from && $2<=to { if(dup[$7]++) next
    tot++; totch+=$4+$5
    if(db && $3 ~ /\[bot\]$/)            { bc++; bch+=$4+$5 }
    else if((mc>0&&($4+$5)>mc)||(mf>0&&$6>mf)) { kc++; kch+=$4+$5 }
    else { keep++; keepch+=$4+$5 } }
  END{ printf "  commits: %d total  ->  %d kept, %d bulk-dropped, %d bot-dropped\n", tot,keep,kc,bc
       printf "  churn  : %d total  ->  %d kept, %d bulk-dropped, %d bot-dropped\n", totch,keepch,kch,bch }' "$TSV"
echo

if [ -z "$BY" ]; then
  awk -F'\t' -v from="$FROM" -v to="$TO" -v mc="$MAXCHURN" -v mf="$MAXFILES" -v db="$DROP_BOTS" "
    $FILT
    NR>1 && keep(){ A[\$3]+=\$4; D[\$3]+=\$5; C[\$3]++; rk=\$3 SUBSEP \$1; if(!(rk in s)){s[rk]=1; R[\$3]++} }
    END{ for(x in A) printf \"%s\t%d\t%d\t%d\t%d\t%d\n\", x,A[x],D[x],A[x]+D[x],C[x],R[x] }" "$TSV" \
  | sort -t$'\t' -k4,4 -nr \
  | awk -F'\t' 'BEGIN{printf "%-24s %9s %9s %9s %8s %5s\n","AUTHOR","ADDED","DEL","CHURN","COMMITS","REPOS"}
               {printf "%-24s %9d %9d %9d %8d %5d\n",$1,$2,$3,$4,$5,$6}'
else
  awk -F'\t' -v from="$FROM" -v to="$TO" -v by="$BY" -v mc="$MAXCHURN" -v mf="$MAXFILES" -v db="$DROP_BOTS" "
    $FILT
    function period(d){ if(by==\"year\")return substr(d,1,4);
      if(by==\"quarter\"){y=substr(d,1,4);m=substr(d,6,2)+0;return y\"-Q\"(int((m-1)/3)+1)}
      return substr(d,1,7) }
    NR>1 && keep(){ p=period(\$2); k=p SUBSEP \$3; A[k]+=\$4; D[k]+=\$5; C[k]++ }
    END{ for(k in A){ split(k,a,SUBSEP); printf \"%s\t%s\t%d\t%d\t%d\t%d\n\", a[1],a[2],A[k],D[k],A[k]+D[k],C[k] } }" "$TSV" \
  | sort -t$'\t' -k1,1 -k5,5nr \
  | awk -F'\t' 'BEGIN{printf "%-9s %-24s %9s %9s %9s %8s\n","PERIOD","AUTHOR","ADDED","DEL","CHURN","COMMITS"}
               {printf "%-9s %-24s %9d %9d %9d %8d\n",$1,$2,$3,$4,$5,$6}'
fi
