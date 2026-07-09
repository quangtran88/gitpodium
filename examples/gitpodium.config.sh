# gitpodium config — copy to ./gitpodium.config.sh in your working dir; it is
# auto-sourced by the `gitpodium` entrypoint. All values are optional.

# GitHub owners (orgs or users) to audit. Used by `gitpodium run` with no args.
export GITPODIUM_ORGS="acme-inc acme-labs"

# Where clones live (default: ./clones). Point at an existing mirror to skip cloning.
# export GITPODIUM_CLONES="$PWD/clones"

# Where artifacts are written (default: current dir).
# export GITPODIUM_OUT="$PWD"

# Optional identity-merge overrides (see examples/gitpodium.identity.json).
# export GITPODIUM_IDENTITY="$PWD/gitpodium.identity.json"

# Bulk/bot filters — a single commit above these thresholds is treated as a
# vendored/generated import and dropped so it can't crown a fake "winner".
export MAXCHURN=10000   # drop commits with added+deleted above this
export MAXFILES=400     # drop commits touching more files than this
export DROP_BOTS=1      # exclude *[bot] accounts (0 to keep them)
