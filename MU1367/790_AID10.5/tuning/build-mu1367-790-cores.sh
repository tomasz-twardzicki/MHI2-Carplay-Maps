#!/bin/sh
# Rebuild the MU1367/790 core.so files from the stock 790 build (shared with MU1102 and MU1440):
#   stock 790 core.so -> patch-core-tuning.py
# Writes the profile payload, the MQB Toolbox payload and the toolbox tuning options.
# Usage: build-mu1367-790-cores.sh [--check]   (--check: verify the committed files, write nothing)
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TB="$REPO/releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4/Custom/carplay_maps_vc"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/mu1367-790-cores.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

# All options: 30 fps, forced keyframe every 20 frames (stock interval).
# Base install: map + turn card, safe area narrowed to half the width and extended to the frame bottom.
BASE="--max-fps 30 --cluster-content map-card --safe-area 253,16,504,360"

# The MU1102 profile carries the same stock 790 core.so; it stays untouched as the build input.
cp "$REPO/MU1102/790_AID10.5/payload/profiles/MU1102/790/core.so" "$TMP/stock.so"

build() {   # $1 = output name, rest = patch-core-tuning.py options
    name="$1"; shift
    python3 "$HERE/patch-core-tuning.py" "$@" "$TMP/stock.so" "$TMP/$name.so" | sed "s#.*/$name.so #$name #"
}
build default $BASE
build wide-card --max-fps 30 --cluster-content map-card --safe-area 202,16,606,360
build low-card --max-fps 30 --cluster-content map-card --safe-area 253,48,504,328
build no-card --max-fps 30
cp "$TMP/stock.so" "$TMP/stock-40fps.so"

place() {   # $1 = built name, $2 = destination
    if [ -n "$CHECK" ]; then
        cmp -s "$TMP/$1.so" "$2" && echo "ok       $2" || { echo "MISMATCH $2"; FAIL=1; }
    else
        mkdir -p "$(dirname "$2")"; cp "$TMP/$1.so" "$2"; echo "wrote    $2"
    fi
}
CHECK=""; FAIL=""
[ "${1:-}" = "--check" ] && CHECK=1
place default "$REPO/MU1367/790_AID10.5/payload/profiles/MU1367/790/core.so"
place default "$TB/payload/profiles/MU1367/790/core.so"
for v in default wide-card low-card no-card stock-40fps; do
    place "$v" "$TB/tuning/MU1367/790/$v/core.so"
done
[ -z "$FAIL" ]
