#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Capture C2: bounded regular-file reads, newest numbered OEM error archive.
# /bin/dd and bs=/count= verified in the MU1427 MMX mifs-stage2 firmware.
# No driver install, restart, process signalling or on-unit hash tools.
set -u
REVISION=C2
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ -s /ifs/lsd.jxe ] && [ -d /mnt/app ]; then :
elif [ -s /net/mmx/ifs/lsd.jxe ]; then M=/net/mmx
else echo "CPMAP_RGI_CAPTURE_FAIL=MMX_NOT_FOUND"; exit 1
fi
VOL=""
for v in ${CPMAP_TEST_VOL:-/net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0}; do
    if [ -d "$v" ]; then VOL=$v; break; fi
done
[ -n "$VOL" ] || { echo "CPMAP_RGI_CAPTURE_FAIL=SD_NOT_FOUND"; exit 1; }
for tool in ls mkdir dd; do
    command -v "$tool" >/dev/null 2>&1 || { echo "CPMAP_RGI_CAPTURE_FAIL=MISSING_$tool"; exit 1; }
done
if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
    mount -uw "$VOL" >/dev/null 2>&1 || { echo "CPMAP_RGI_CAPTURE_FAIL=SD_REMOUNT"; exit 1; }
fi
mkdir -p "$VOL/Log" || exit 1
OUT=$VOL/Log/cpmap-navrecon-$REVISION-$$
n=0
while [ -d "$OUT" ]; do n=$((n+1)); OUT=$VOL/Log/cpmap-navrecon-$REVISION-$$-$n; done
mkdir "$OUT" || { echo "CPMAP_RGI_CAPTURE_FAIL=SD_WRITE"; exit 1; }
mkdir "$OUT/files" || exit 1
FAILED=0
OEM_FOUND=0

progress() { echo "$*"; echo "$*" >> "$OUT/progress.txt"; }
capture() { # source, destination, maximum bytes (regular files ONLY)
    src=$1; dst=$2; cap=$3
    progress "BEGIN $src"
    listing=$(ls -ln "$src" 2>/dev/null) || { progress "MISSING $src"; return 0; }
    set -- $listing
    if [ "$#" -lt 5 ]; then progress "SKIP invalid stat: $src"; return 0; fi
    case "$1" in -*) ;; *) progress "SKIP non-regular: $src"; return 0 ;; esac
    size=$5
    case "$size" in ''|*[!0-9]*) progress "SKIP invalid size: $src"; return 0 ;; esac
    if [ "$size" -gt "$cap" ]; then
        progress "SKIP oversized: $src bytes=$size limit=$cap"
        return 0
    fi
    blocks=0
    if [ "$size" -eq 0 ]; then
        : > "$dst" || { FAILED=$((FAILED+1)); progress "FAILED $src"; return 0; }
    else
        # Fixed count based on the starting size, even if a live log keeps growing.
        blocks=$(((size+4095)/4096))
        if ! dd "if=$src" "of=$dst" bs=4096 "count=$blocks" 2>> "$OUT/copy-errors.txt"; then
            FAILED=$((FAILED+1)); progress "FAILED $src"; return 0
        fi
    fi
    case "$dst" in "$OUT"/oem-error-*/*) OEM_FOUND=$((OEM_FOUND+1)) ;; esac
    progress "DONE $src initial_bytes=$size max_read=$((blocks*4096))"
}

progress "MU1427 route-guidance capture $REVISION"
progress "Output $OUT"
progress "No global mount listing, recursive search, pidin mem or PPS reads"
blocks=0

# Capture evidence FIRST; any later issue must not lose the iAP2 log again.
capture "$M/dev/shmem/iap2.log" "$OUT/iap2.log" 8388608
ls -ln "$M/mnt/ota/system/logs" > "$OUT/oem-log-directory.txt" 2>&1
OEM_ID=42
for candidate in "$M"/mnt/ota/system/logs/smartphone_integrator_error_*; do
    suffix=${candidate##*/smartphone_integrator_error_}
    id=${suffix%%.*}
    case "$id" in ''|*[!0-9]*) continue ;; esac
    [ "$id" -gt "$OEM_ID" ] && OEM_ID=$id
done
BASE=$M/mnt/ota/system/logs/smartphone_integrator_error_$OEM_ID
mkdir "$OUT/oem-error-$OEM_ID" || exit 1
for item in "$BASE" "$BASE".* "$BASE"_*; do
    [ -e "$item" ] || continue
    if [ -d "$item" ] && [ ! -L "$item" ]; then
        progress "DIRECTORY $item (one level only)"
        dest=$OUT/oem-error-$OEM_ID/${item##*/}
        mkdir -p "$dest" || exit 1
        ls -ln "$item" > "$dest/directory.txt" 2>&1
        for f in "$item"/*; do
            capture "$f" "$dest/${f##*/}" 67108864
        done
    else
        capture "$item" "$OUT/oem-error-$OEM_ID/${item##*/}" 67108864
    fi
done

# Actual files and backups: enough to verify installation/rollback on the host.
capture "$M/mnt/app/armle/lib/dll/ipod-drvr-iap2.so" "$OUT/files/ipod-drvr-iap2.so" 1048576
capture "$M/mnt/system/etc/mm/iap2.cfg" "$OUT/files/iap2.cfg" 65536
capture "$M/mnt/app/route-guidance-b1/stock-driver.so" "$OUT/files/stock-driver.so" 1048576
capture "$M/mnt/app/route-guidance-b1/stock-iap2.cfg" "$OUT/files/stock-iap2.cfg" 65536
for name in carplaymaps-video.log carplay-maps-session.log carplaymaps-launcher.log carplay-cluster-supervisor.log; do
    capture "$M/ramdisk/$name" "$OUT/$name" 8388608
done
{
    echo "Capture $REVISION"
    echo "Node prefix $M"
    echo "=== lsd.jxe / active iAP2 files / original backups"
    ls -ln "$M/ifs/lsd.jxe" "$M/mnt/app/armle/lib/dll/ipod-drvr-iap2.so" "$M/mnt/system/etc/mm/iap2.cfg" "$M/mnt/app/route-guidance-b1/stock-driver.so" "$M/mnt/app/route-guidance-b1/stock-iap2.cfg"
    echo "Read failures: $FAILED; OEM error $OEM_ID files captured: $OEM_FOUND"
    echo "Missing/oversized files are listed in progress.txt"
    echo "Newest numbered OEM error selected (minimum 42); 42 contains the B1 failure."
} > "$OUT/summary.txt" 2>&1
[ "$OEM_FOUND" -gt 0 ] || progress "OEM_ERROR_NOT_FOUND id=$OEM_ID: see oem-log-directory.txt"
if [ "$FAILED" -ne 0 ]; then
    progress "CPMAP_RGI_CAPTURE_PARTIAL=$FAILED"
    if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
        echo "Flushing SD card (explicit target only)"
        sync 2>/dev/null
        mount -ur "$VOL" >/dev/null 2>&1
    fi
    exit 1
fi
progress "CPMAP_RGI_CAPTURE_OK"
progress "CPMAP_NAVRECON_OK"
progress "Copy this directory privately; it can contain GPS and authentication data."
if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
    echo "Flushing SD card (explicit target only)"
    sync 2>/dev/null
    mount -ur "$VOL" >/dev/null 2>&1
fi
echo "Capture finished: $OUT"
