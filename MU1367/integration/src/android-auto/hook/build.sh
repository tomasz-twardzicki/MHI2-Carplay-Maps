#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Android Auto: build the MacsInSpace gal hook (libgal_hook.so) and libdmdt_flush.so for MU1161 from a pinned commit,
# with every SD card path taken out (patch_no_sd.py) and the player's fresh-IDR request (patch_keyframe.py, audit A-AA6).
# and the experimental setup-response resend (patch_config_kf.py, A-AA15). Built twice; both builds must be byte-identical. Host test of the keyframe patch: test/run_keyframe_test.sh.
#
#   build.sh <out dir> [gamma]
#
# gamma: also patch_rg.py (AA 1.7 navigation -> rg RAM mailbox, pmcp_rg.c; active only with GAL_PMCP_RG=1), build tag
# -pmcp-g2 (g1 = before the 2026-11-03 liveness review). Without it the output is the AA 1 / 2 / 3 hook (tag -pmcp-kf2), byte for byte as before.
#
# Needs: docker with the qnx65-armv7-toolchain:8.5 image (luka-dev/qnx65-armv7-toolchain, see aa/README.md), git, python3,
# and a MacsInSpace/mib-cluster-map clone holding the pinned commit (default <workspace>/upstream/macsinspace, made by
# install.sh, or PMCP_MACS).
set -euo pipefail

OUT=${1:?out dir}
VARIANT=${2:-}
TAG=pmcp-kf2
case "$VARIANT" in "") ;; gamma) TAG=pmcp-g2 ;; *) echo "FAIL: unknown variant $VARIANT" >&2; exit 1 ;; esac
H=$(cd "$(dirname "$0")" && pwd)
WS=$(cd "$H/../../.." && pwd)     # workspace: upstream/ lives next to this repository (as in install.sh)
MACS="${PMCP_MACS:-$WS/upstream/macsinspace}"
COMMIT=07361db860b1d09e3901e9002b4222889a8a8c18   # 2026-10-29, built-in MHI2_ER_VWG13_P4512 profile, nav_translate
IMAGE=qnx65-armv7-toolchain:8.5

fail() { echo "FAIL: $*" >&2; exit 1; }
[ ! -e "$OUT" ] || fail "out dir exists: $OUT"
git -C "$MACS" cat-file -e "$COMMIT^{commit}" 2>/dev/null || fail "commit $COMMIT not in $MACS (git fetch)"
mkdir -p "$OUT/src"
OUT=$(cd "$OUT" && pwd)
git -C "$MACS" archive "$COMMIT" src dmdt_flush LICENSE | tar -x -C "$OUT/src"
python3 -I "$H/patch_no_sd.py" "$OUT/src"
python3 -I "$H/patch_keyframe.py" "$OUT/src"
python3 -I "$H/patch_config_kf.py" "$OUT/src"
[ "$VARIANT" = gamma ] && python3 -I "$H/patch_rg.py" "$OUT/src"

for n in 1 2; do
    mkdir "$OUT/build$n"
    docker run --rm --platform=linux/amd64 -v "$OUT/src":/w:ro -v "$OUT/build$n":/out -w /w "$IMAGE" bash -c '
set -e
export PATH=/opt/qnx650/host/linux/x86/usr/bin:$PATH QNX_HOST=/opt/qnx650/host/linux/x86 QNX_TARGET=/opt/qnx650/target/qnx6
P=arm-unknown-nto-qnx6.5.0eabi
$P-gcc -O2 -Wall -Wextra -shared -fPIC -I./src -DGAL_HOOK_BUILD="\"'"${COMMIT:0:7}-$TAG"'\"" ./src/*.c \
    -Wl,--exclude-libs,ALL -lsocket -o /out/libgal_hook.so
$P-gcc -O2 -Wall -shared -fPIC dmdt_flush/dmdt_flush.c -Wl,--exclude-libs,ALL -o /out/libdmdt_flush.so
$P-strip --strip-debug /out/libgal_hook.so /out/libdmdt_flush.so
bad=$($P-nm -D --defined-only /out/libgal_hook.so | awk "{print \$3}" | grep -Ev "^(_ZN|gal_hook_|fc_|vc_|hook_fix_enabled|_init|_fini|__bss|_edata|_end|__end__|_bss_end__|__bss_start__|__bss_end__|__data_start|__exidx_start|__exidx_end|_btext|_stack)" || true)
[ -z "$bad" ] || { echo "foreign exports: $bad"; exit 1; }
[ "$($P-nm /out/libgal_hook.so | grep -ci emutls || true)" = 0 ] || { echo "emutls"; exit 1; }
$P-readelf -d /out/libgal_hook.so | grep NEEDED'
done
for f in libgal_hook.so libdmdt_flush.so; do
    cmp -s "$OUT/build1/$f" "$OUT/build2/$f" || fail "$f differs between two builds"
    cp "$OUT/build1/$f" "$OUT/$f"
done
rm -rf "$OUT/build1" "$OUT/build2"
(cd "$OUT" && shasum -a 256 libgal_hook.so libdmdt_flush.so && wc -c libgal_hook.so libdmdt_flush.so)
