#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# C4: manual RAM-only recorder. B4 driver/config and OEM backups are read-only.
set -u
ACTION=${1:-status}
PAYLOAD=${2:-}
BUILD_ID=@BUILD_ID@
BINARY_SIZE=@BINARY_SIZE@
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ -s /ifs/lsd.jxe ] && [ -d /mnt/app ]; then :
elif [ -s /net/mmx/ifs/lsd.jxe ]; then M=/net/mmx
else echo "CPMAP_RGI_C4_FAIL=MMX_NOT_FOUND"; exit 1
fi
N=""
[ -z "${CPMAP_TEST_ROOT:-}" ] || N=$M
ROOT=$M/ramdisk/cpmap-rgi-C4
BIN=$M/ramdisk/cpmap-rgi-observer-C4
NR=$N/ramdisk/cpmap-rgi-C4
NB=$N/ramdisk/cpmap-rgi-observer-C4
fail() { echo "CPMAP_RGI_C4_FAIL=$1"; exit 1; }
size() {
    line=$(ls -ln "$1" 2>/dev/null) || return 1
    set -- $line
    [ "$#" -ge 5 ] || return 1
    case "$1" in -*) ;; *) return 1 ;; esac
    case "$5" in ''|*[!0-9]*) return 1 ;; esac
    echo "$5"
}
native() {
    if [ "$M" = /net/mmx ]; then on -f mmx "$@"
    else "$@"; fi
}
stop_reader() {
    [ -d "$ROOT" ] && [ ! -L "$ROOT" ] || fail RECORDER_NOT_FOUND
    [ "$(size "$BIN")" = "$BINARY_SIZE" ] || fail RAM_BINARY_INVALID_REBOOT_TO_STOP
    native "$NB" stop "$NR" || fail STOP_NOT_CONFIRMED
}
for tool in ls cat; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
case "$ACTION" in
    status)
        if [ -f "$ROOT/status.txt" ]; then cat "$ROOT/status.txt"
        else echo "C4 recorder not started"; fi
        exit 0 ;;
    stop) stop_reader; exit $? ;;
    remove)
        if [ -d "$ROOT" ]; then stop_reader; fi
        rm -rf "$ROOT" || fail REMOVE_FAILED
        rm -f "$BIN" || fail REMOVE_FAILED
        echo "CPMAP_RGI_C4_REMOVED"; exit 0 ;;
    start)
        for tool in cp chmod; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
        [ ! -e "$ROOT" ] && [ ! -L "$ROOT" ] || fail PREVIOUS_RUN_EXPORT_AND_REMOVE_FIRST
        [ "$(size "$M/ifs/lsd.jxe")" = 52751492 ] || fail WRONG_FIRMWARE
        [ "$(size "$M/mnt/app/armle/lib/dll/ipod-drvr-iap2.so")" = 743196 ] || fail B4_DRIVER_REQUIRED
        [ "$(size "$M/mnt/system/etc/mm/iap2.cfg")" = 6006 ] || fail B4_CONFIG_REQUIRED
        [ "$(cat "$M/mnt/app/route-guidance-b1/VERSION" 2>/dev/null)" = MU1427-iAP2-RGI-B4-3760797a ] || fail B4_MARKER_REQUIRED
        [ "$(cat "$PAYLOAD/VERSION" 2>/dev/null)" = "$BUILD_ID" ] || fail PAYLOAD_VERSION
        [ "$(size "$PAYLOAD/rgi-observer")" = "$BINARY_SIZE" ] || fail PAYLOAD_SIZE
        cp "$PAYLOAD/rgi-observer" "$BIN" || fail RAM_COPY
        [ "$(size "$BIN")" = "$BINARY_SIZE" ] || fail RAM_COPY_SIZE
        chmod 755 "$BIN" || fail RAM_MODE
        # chmod exists in the exact MMX stage2 firmware; no shell sleep/kill,
        # hash command or shell background-job handling is needed.
        native "$NB" start "$N/dev/ipod0/rgi-events" "$NR" 300 || fail START_FAILED
        echo "$BUILD_ID" > "$ROOT/VERSION" || fail MARKER_WRITE
        echo "C4 runs for at most 5 minutes; stop/export before reboot."
        exit 0 ;;
    export) stop_reader ;;
    *) fail INVALID_ACTION ;;
esac
for tool in mkdir dd sync; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
VOL=""
for v in ${CPMAP_TEST_VOL:-/net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0}; do
    if [ -d "$v" ]; then VOL=$v; break; fi
done
[ -n "$VOL" ] || fail SD_NOT_FOUND
if [ -z "${CPMAP_TEST_ROOT:-}" ]; then mount -uw "$VOL" >/dev/null 2>&1 || fail SD_REMOUNT; fi
mkdir -p "$VOL/Log" || fail SD_DIRECTORY
OUT=$VOL/Log/cpmap-rgi-C4-$$
mkdir "$OUT" || fail SD_DIRECTORY
copy_file() {
    count=$(size "$1") || fail EXPORT_SOURCE_STAT
    [ "$count" -le "$3" ] || fail EXPORT_SOURCE_OVERSIZED
    blocks=$(((count+4095)/4096))
    dd "if=$1" "of=$2" bs=4096 "count=$blocks" 2>> "$OUT/copy-errors.txt" || fail EXPORT_COPY
    [ "$(size "$2")" = "$count" ] || fail EXPORT_COPY_SIZE
}
copy_file "$ROOT/events.rgj" "$OUT/events.rgj" 8388608
copy_file "$ROOT/status.txt" "$OUT/status.txt" 1024
copy_file "$ROOT/VERSION" "$OUT/VERSION" 128
copy_file "$M/mnt/app/armle/lib/dll/ipod-drvr-iap2.so" "$OUT/ipod-drvr-iap2.so" 1048576
copy_file "$M/mnt/system/etc/mm/iap2.cfg" "$OUT/iap2.cfg" 65536
echo "CPMAP_RGI_C4_EXPORT_OK" > "$OUT/progress.txt"
if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
    sync 2>/dev/null
    mount -ur "$VOL" >/dev/null 2>&1 || fail SD_READONLY
fi
echo "CPMAP_RGI_C4_EXPORT_OK $OUT"
echo "RAM capture retained. Export again if needed; remove recorder before another run."
