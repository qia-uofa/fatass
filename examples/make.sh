#!/usr/bin/env bash
# Generic driver for the example pipelines (jrpg, ...). Each project
# supplies one file here: <project>.sig -- structure, transform defs, and
# (per fatass.signature.FULL_SIGNATURE's own "{...}" transforms-block
# syntax) each transform's own modify prompt, as a "#" comment right
# before it (see `fatass touch --help`'s own "-m" section for the exact
# two comment positions it reads).
#
# -t   touch:  scaffold the whole node tree AND every transform the
#              pipeline needs (as empty stubs only), in one
#              `fatass touch` call, which never calls the agent (see
#              `fatass create`'s own docstring: "Doesn't call free()").
#              Safe to re-run: `fatass touch` is idempotent — anything
#              already there is left alone and reported as such, not
#              an error.
# -m   modify: `fatass touch -p <project>.sig -m` -- same scaffolding
#              call as -t, plus a third pass that silently `modify`s
#              every transform IT JUST CREATED that has its own "#"
#              comment in the .sig file, using that comment as the
#              prompt — calls the agent for real, once per newly
#              created transform, so it's slow and not free. Re-running
#              it later (e.g. after adding a node+transform to the .sig
#              file) only touches/modifies what's new; anything already
#              there is left alone.
# -tm  same as -m (touch's own two creation passes always run first;
#              -m only adds the third, modify, pass on top).
#
# Usage:
#   ./make.sh -t  jrpg                        # roots the tree at path=top
#   ./make.sh -m  jrpg
#   ./make.sh -tm jrpg
#   ./make.sh -t  jrpg path=some.existing.node

set -euo pipefail

usage() {
    echo "Usage: $0 (-t|-m|-tm) <project> [path=some.existing.node]" >&2
    exit 1
}

[ $# -ge 2 ] || usage
MODE="$1"
PROJECT="$2"
shift 2
PATH_ARG="${1:-path=top}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIG_FILE="$SCRIPT_DIR/$PROJECT.sig"

do_touch() {
    local extra_args=("$@")
    [ -f "$SIG_FILE" ] || { echo "make.sh: no such file: $SIG_FILE" >&2; exit 1; }
    NODE_PATH="${PATH_ARG#path=}"
    python -m fatass cd "$NODE_PATH"
    python -m fatass touch -p "$SIG_FILE" "${extra_args[@]}"
    echo "make.sh: touch done."
}

case "$MODE" in
    -t)
        do_touch
        ;;
    -m|-tm)
        do_touch -m
        ;;
    *)
        usage
        ;;
esac
