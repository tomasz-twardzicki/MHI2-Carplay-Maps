#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# N2 replaces only the B4 driver; N1 Java, boot script and config are preserved.
set -u
ACTION=${1:-status}
INPUT=${2:-}
BUILD=@BUILD@
DRIVER_SIZE=@DRIVER_SIZE@
READER_SIZE=@READER_SIZE@
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && { [ ! -s /ifs/lsd.jxe ] || [ ! -d /mnt/app ]; }; then M=/net/mmx; fi
APP=$M/mnt/app
ROOT=$APP/carplay-artwork-n2
DRIVER=$APP/armle/lib/dll/ipod-drvr-iap2.so
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
STAGED=no
size() { line=$(ls -ln "$1" 2>/dev/null) || return 1; set -- $line; [ "$#" -ge 5 ] || return 1; case "$1" in -*) ;; *) return 1 ;; esac; echo "$5"; }
regular() { [ -f "$1" ] && [ ! -L "$1" ]; }
absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail() { echo "CPMAP_AUDIO_N2_FAIL=$1"; exit 1; }
native() {
    if [ -n "${CPMAP_TEST_ROOT:-}" ]; then
        case "$1" in mount) return 0 ;; *) "$@" ;; esac
    elif [ "$M" = /net/mmx ]; then
        CMD=$1; shift
        case "$CMD" in /net/mmx/*) CMD=${CMD#/net/mmx} ;; esac
        on -f mmx "$CMD" "$@"
    else "$@"; fi
}
clean() { if [ "$OWN" = yes ]; then [ "$STAGED" = no ] || rm -f "$DRIVER.n2-new"; rm -rf "$LOCK"; fi; }
trap clean EXIT
trap 'fail INTERRUPTED_RETRY_SAVED_UNINSTALL' HUP INT TERM
for t in ls cat rm mkdir awk cp mv chmod sync; do command -v "$t" >/dev/null 2>&1 || fail "MISSING_$t"; done
[ ! -L "$ROOT" ] || fail RECOVERY_SYMLINK
status() {
    echo "N2 artwork transfer observer; N1 text unchanged; no image output"
    if regular "$ROOT/VERSION"; then cat "$ROOT/VERSION"; else echo N2_NOT_INSTALLED_OR_MARKER_MISSING; fi
    echo "driver_bytes=$(size "$DRIVER")"
}
case "$ACTION" in
    status) status; exit 0 ;;
    export)
        absent "$INPUT" && mkdir "$INPUT" || fail EXPORT_NEW_DIRECTORY_REQUIRED
        status > "$INPUT/install.txt" || fail EXPORT_STATUS
        regular "$ROOT/snapshot" && [ "$(size "$ROOT/snapshot")" = "$READER_SIZE" ] || fail HELPER_MISSING
        if [ -n "${CPMAP_TEST_ROOT:-}" ]; then
            DEVICE=$M/dev/ipod0/rgi-events
            READER_LOCK=$M/ramdisk/.carplay-artwork-n2-reader-lock
        else DEVICE=/dev/ipod0/rgi-events; READER_LOCK=/ramdisk/.carplay-artwork-n2-reader-lock; fi
        native "$ROOT/snapshot" "$DEVICE" "$READER_LOCK" > "$INPUT/native.txt"
        RC=$?
        # This is a diagnostic export: retain errors and allow user inspection.
        echo "snapshot_result=$RC" >> "$INPUT/install.txt"
        N1=$M/ramdisk/carplay-now-playing-n1.status
        if regular "$N1"; then [ "$(size "$N1")" -le 4096 ] || fail N1_STATUS_OVERSIZE; cp "$N1" "$INPUT/n1.txt" || fail EXPORT_N1; fi
        echo "CPMAP_AUDIO_N2_EXPORTED=$INPUT"; exit 0 ;;
    install|uninstall) ;;
    *) fail INVALID_ACTION ;;
esac
[ "$(size "$M/ifs/lsd.jxe")" = 52751492 ] || fail MU1427_ONLY
regular "$DRIVER" || fail DRIVER_NOT_REGULAR
mkdir "$LOCK" 2>/dev/null || fail ANOTHER_OPERATION_OR_STALE_LOCK
OWN=yes
absent "$DRIVER.n2-new" || fail STALE_DRIVER_STAGE
native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
if [ "$ACTION" = install ]; then
    [ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1427/791 ] || fail PROFILE_REQUIRED
    [ "$(cat "$APP/carplay-now-playing-n1/VERSION" 2>/dev/null)" = MU1427-AUDIO-N1-8bbacafe81af ] || fail TESTED_N1_REQUIRED
    [ "$(size "$APP/eso/hmi/lsd/jars/CarPlayNowPlayingTextN1.jar")" = 21300 ] || fail N1_JAR_REQUIRED
    [ "$(cat "$APP/route-guidance-b1/VERSION" 2>/dev/null)" = MU1427-iAP2-RGI-B4-3760797a ] || fail B4_MARKER_REQUIRED
    [ "$(size "$M/mnt/system/etc/mm/iap2.cfg")" = 6006 ] || fail TESTED_B4_CONFIG_REQUIRED
    [ "$(cat "$INPUT/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION
    regular "$INPUT/ipod-drvr-iap2.so" && [ "$(size "$INPUT/ipod-drvr-iap2.so")" = "$DRIVER_SIZE" ] || fail PAYLOAD_DRIVER
    regular "$INPUT/snapshot" && [ "$(size "$INPUT/snapshot")" = "$READER_SIZE" ] || fail PAYLOAD_HELPER
    if regular "$ROOT/VERSION"; then
        [ "$(cat "$ROOT/VERSION")" = "$BUILD" ] && [ "$(size "$DRIVER")" = "$DRIVER_SIZE" ] || fail DIFFERENT_BUILD
        [ "$(size "$ROOT/b4-driver.so")" = 743196 ] || fail B4_BACKUP_REQUIRED
        regular "$ROOT/snapshot" && [ "$(size "$ROOT/snapshot")" = "$READER_SIZE" ] || fail INSTALLED_HELPER
        echo CPMAP_AUDIO_N2_ALREADY_INSTALLED; exit 0
    fi
    [ "$(size "$DRIVER")" = 743196 ] || fail TESTED_B4_DRIVER_REQUIRED
    mkdir -p "$ROOT" || fail RECOVERY_DIRECTORY
    for f in control.sh b4-driver.so snapshot VERSION; do regular "$ROOT/$f" || absent "$ROOT/$f" || fail RECOVERY_FILE_NOT_REGULAR; done
    cp "$0" "$ROOT/control.sh" || fail SAVE_CONTROLLER
    cp -p "$DRIVER" "$ROOT/b4-driver.so" || fail SAVE_B4
    cp "$INPUT/snapshot" "$ROOT/snapshot" || fail SAVE_HELPER
    chmod 755 "$ROOT/snapshot" || fail HELPER_MODE
    [ "$(size "$ROOT/b4-driver.so")" = 743196 ] || fail SAVED_B4_SIZE
    sync
    STAGED=yes
    cp -p "$DRIVER" "$DRIVER.n2-new" || fail STAGE_MODE
    cat "$INPUT/ipod-drvr-iap2.so" > "$DRIVER.n2-new" || fail STAGE_DRIVER
    [ "$(size "$DRIVER.n2-new")" = "$DRIVER_SIZE" ] || fail STAGE_SIZE
    mv "$DRIVER.n2-new" "$DRIVER" || fail DRIVER_COMMIT_RETRY_UNINSTALL
    echo "$BUILD" > "$ROOT/VERSION" || fail MARKER_COMMIT_USE_SAVED_UNINSTALL
    sync
    echo CPMAP_AUDIO_N2_INSTALLED_REBOOT_REQUIRED
else
    regular "$ROOT/b4-driver.so" && [ "$(size "$ROOT/b4-driver.so")" = 743196 ] || fail B4_BACKUP_REQUIRED
    CURRENT=$(size "$DRIVER") || fail DRIVER_SIZE
    case "$CURRENT" in
        "$DRIVER_SIZE")
            STAGED=yes
            cp -p "$ROOT/b4-driver.so" "$DRIVER.n2-new" || fail RESTORE_STAGE
            mv "$DRIVER.n2-new" "$DRIVER" || fail RESTORE_COMMIT_KEEP_RECOVERY_RETRY ;;
        743196) ;; # already restored or failure before the driver commit
        *) fail UNRECOGNIZED_DRIVER_KEEP_RECOVERY ;;
    esac
    rm -f "$ROOT/VERSION" || fail REMOVE_MARKER
    sync
    echo CPMAP_AUDIO_N2_REMOVED_REBOOT_REQUIRED
fi
