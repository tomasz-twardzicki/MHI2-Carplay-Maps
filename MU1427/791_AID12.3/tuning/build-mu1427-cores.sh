#!/bin/sh
# Rebuild the MU1427/791 core.so files from the shared MU1367/791 build:
#   MU1367 core.so -> ../patch-core-mu1427.py (AES key offset) -> patch-core-tuning.py
# Writes the profile payload, the MQB Toolbox payload and the toolbox tuning options.
# Usage: build-mu1427-cores.sh [--check]   (--check: verify the committed files, write nothing)
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
TB="$REPO/releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4/Custom/carplay_maps_vc"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/mu1427-cores.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

# Base install: 30 fps, forced keyframe every 20 frames, map + narrow turn card.
BASE="--max-fps 30 --cluster-content map-card --safe-area 200,96,400,364"

cp "$REPO/MU1367/791_AID12.3/payload/profiles/MU1367/791/core.so" "$TMP/aes.so"
python3 "$REPO/MU1427/791_AID12.3/patch-core-mu1427.py" "$TMP/aes.so" >/dev/null

build() {   # $1 = output name, rest = patch-core-tuning.py options
    name="$1"; shift
    python3 "$HERE/patch-core-tuning.py" "$@" "$TMP/aes.so" "$TMP/$name.so" | sed "s#.*/$name.so #$name #"
}
build default $BASE
build no-card --max-fps 30 --cluster-content map --safe-area 200,80,400,380
build wide-card --max-fps 30 --cluster-content map-card --safe-area 160,96,480,364

place() {   # $1 = built name, $2 = destination
    if [ -n "$CHECK" ]; then
        cmp -s "$TMP/$1.so" "$2" && echo "ok       $2" || { echo "MISMATCH $2"; FAIL=1; }
    else
        mkdir -p "$(dirname "$2")"; cp "$TMP/$1.so" "$2"; echo "wrote    $2"
    fi
}
CHECK=""; FAIL=""
[ "${1:-}" = "--check" ] && CHECK=1
place default "$REPO/MU1427/791_AID12.3/payload/profiles/MU1427/791/core.so"
place default "$TB/payload/profiles/MU1427/791/core.so"
for v in default no-card wide-card; do
    place "$v" "$TB/tuning/MU1427/791/$v/core.so"
done
[ -z "$FAIL" ]
