#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# D1 manual Java bridge. Uses only utilities already verified for MU1427.
set -u
ACTION=${1:-status}
PAYLOAD=${2:-}
BUILD_ID=@BUILD_ID@
JAR_SIZE=@JAR_SIZE@
SOURCE_ID=@SOURCE_ID@
ALLOW_LIVE=@ALLOW_LIVE@
BINARY_SIZE=16333
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ -s /ifs/lsd.jxe ] && [ -d /mnt/app ]; then :
elif [ -s /net/mmx/ifs/lsd.jxe ]; then M=/net/mmx
else echo "CPMAP_RGI_D1_FAIL=MMX_NOT_FOUND"; exit 1; fi
N=""
[ -z "${CPMAP_TEST_ROOT:-}" ] || N=$M
RAM=$M/ramdisk/cpmap-rgi-D1
NR=$N/ramdisk/cpmap-rgi-D1
APP=$M/mnt/app
BACKUP=$APP/route-guidance-D1
LSD=$APP/eso/hmi/lsd/lsd.sh
JAR=$APP/eso/hmi/lsd/jars/CarPlayRouteGuidanceD1.jar
TARGET='$BASE_DIR/lsd/jars/CarPlayRouteGuidanceD1.jar'
fail() { echo "CPMAP_RGI_D1_FAIL=$1"; exit 1; }
native() { if [ "$M" = /net/mmx ]; then on -f mmx "$@"; else "$@"; fi; }
size() {
    line=$(ls -ln "$1" 2>/dev/null) || return 1
    set -- $line
    [ "$#" -ge 5 ] || return 1
    case "$1" in -*) ;; *) return 1 ;; esac
    case "$5" in ''|*[!0-9]*) return 1 ;; esac
    echo "$5"
}
regular() { [ -f "$1" ] && [ ! -L "$1" ]; }
check_ram() { [ ! -L "$RAM" ] && [ ! -L "$RAM/capture" ] || fail RAM_SYMLINK; }
status_copy() {
    # The Java writer replaces complete regular RAM status files atomically.
    # Copy before removing the request: that removal resets per-run counters.
    regular "$1" || return 1
    bytes=$(size "$1") || return 1
    [ "$bytes" -gt 0 ] && [ "$bytes" -le "$3" ] || return 1
    cp "$1" "$2.new" || return 1
    bytes=$(size "$2.new") || return 1
    [ "$bytes" -gt 0 ] && [ "$bytes" -le "$3" ] || return 1
    mv "$2.new" "$2" || return 1
}
save_requested_status() {
    regular "$RAM/request" || return 0
    [ -f "$RAM/adapter-status.txt" ] || return 0
    status_copy "$RAM/adapter-status.txt" "$RAM/adapter-status-$1.txt" 2048 || return 1
    status_copy "$RAM/request" "$RAM/request-$1.txt" 64 || return 1
}
disable() {
    check_ram
    # The disable path needs neither a phone, payload, valid driver nor jar.
    rm -f "$RAM/request" "$RAM/request.new" || fail DISABLE_FAILED
    echo "CPMAP_RGI_D1_DISABLED"
}
stop_reader() {
    [ -d "$RAM/capture" ] || return 0
    [ "$(size "$RAM/rgi-observer")" = "$BINARY_SIZE" ] || fail RECORDER_BINARY_INVALID
    native "$NR/rgi-observer" stop "$NR/capture" || fail RECORDER_STOP_FAILED_BRIDGE_DISABLED
}
firmware() {
    [ "$(size "$M/ifs/lsd.jxe")" = 52751492 ] || fail WRONG_FIRMWARE
    [ "$(size "$APP/armle/lib/dll/ipod-drvr-iap2.so")" = 743196 ] || fail B4_DRIVER_REQUIRED
    [ "$(size "$M/mnt/system/etc/mm/iap2.cfg")" = 6006 ] || fail B4_CONFIG_REQUIRED
    [ "$(cat "$APP/route-guidance-b1/VERSION" 2>/dev/null)" = MU1427-iAP2-RGI-B4-3760797a ] || fail B4_MARKER_REQUIRED
}
installed() {
    [ "$(cat "$BACKUP/VERSION" 2>/dev/null)" = "$BUILD_ID" ] || fail D1_NOT_INSTALLED
    [ "$(size "$JAR")" = "$JAR_SIZE" ] || fail INSTALLED_JAR_SIZE
    [ "$(awk '/CarPlayRouteGuidanceD1.jar/{n++} END{print n+0}' "$LSD")" = 1 ] || fail BOOTCLASSPATH_ENTRY
}
for tool in ls cat rm; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
case "$ACTION" in
    disable) disable; exit 0 ;;
    status)
        check_ram
        # Status remains readable when snapshot utilities are unavailable;
        # the independent disable action below still needs only rm/ls/cat.
        if command -v cp >/dev/null 2>&1 && command -v mv >/dev/null 2>&1; then
            save_requested_status observed || echo "CPMAP_RGI_D1_STATUS_SNAPSHOT_FAILED"
        fi
        if [ -f "$RAM/adapter-status.txt" ]; then cat "$RAM/adapter-status.txt"
        else echo "D1 adapter has not reported; install/reboot first"; fi
        [ ! -f "$RAM/capture/status.txt" ] || cat "$RAM/capture/status.txt"
        exit 0 ;;
    stop) disable; stop_reader; exit 0 ;;
    clear)
        disable; stop_reader
        rm -rf "$RAM/capture" || fail CLEAR_CAPTURE
        rm -f "$RAM/rgi-observer" || fail CLEAR_BINARY
        echo "CPMAP_RGI_D1_CAPTURE_CLEARED"; exit 0 ;;
    install|uninstall|shadow|live|verify|export) ;;
    *) fail INVALID_ACTION ;;
esac
for tool in awk cp mv mkdir chmod sync; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
check_ram
case "$ACTION" in
    install)
        firmware
        [ "$(cat "$PAYLOAD/VERSION" 2>/dev/null)" = "$BUILD_ID" ] || fail PAYLOAD_VERSION
        [ "$(size "$PAYLOAD/CarPlayRouteGuidanceD1.jar")" = "$JAR_SIZE" ] || fail PAYLOAD_JAR_SIZE
        regular "$LSD" || fail LSD_NOT_REGULAR
        if [ -f "$BACKUP/VERSION" ]; then installed; echo "CPMAP_RGI_D1_ALREADY_INSTALLED"; exit 0; fi
        [ ! -L "$BACKUP" ] && [ ! -e "$JAR" ] && [ ! -L "$JAR" ] || fail PREVIOUS_D1_FILES
        [ "$(awk '/CarPlayRouteGuidanceD1.jar/{n++} END{print n+0}' "$LSD")" = 0 ] || fail PREVIOUS_D1_BOOT_ENTRY
        [ "$(awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{n++} END{print n+0}' "$LSD")" = 1 ] || fail UNKNOWN_LSD_LAYOUT
        [ "$(awk '/^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{n++} END{print n+0}' "$LSD")" -le 1 ] || fail MULTIPLE_PREPEND_LINES
        awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{launch=NR} /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{prepend=NR} END{exit (prepend && prepend>=launch)}' "$LSD" || fail PREPEND_AFTER_LAUNCH
        [ -n "${CPMAP_TEST_ROOT:-}" ] || native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
        [ -d "$BACKUP" ] || mkdir "$BACKUP" || fail BACKUP_DIRECTORY
        cp "$LSD" "$BACKUP/original-lsd.sh" || fail BACKUP_SCRIPT
        cp "$0" "$BACKUP/control.sh" || fail BACKUP_CONTROLLER
        # Merge into the existing prepend path so NavActiveIgnore/control jars
        # stay effective. Factory /a: JXE and every other line remain intact.
        awk -v target="$TARGET" '
            BEGIN{done=0}
            /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{
                sub(/-Xbootclasspath\/p:/,"-Xbootclasspath/p:" target ":"); done=1
            }
            /^\$J9 .*\$BOOTCLASSPATH .*-jxe/{
                if(!done) print "BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\""
            }
            {print}
        ' "$LSD" > "$BACKUP/lsd.new" || fail STAGE_LSD
        [ "$(awk '/CarPlayRouteGuidanceD1.jar/{n++} END{print n+0}' "$BACKUP/lsd.new")" = 1 ] || fail STAGED_BOOT_ENTRY
        /bin/ksh -n "$BACKUP/lsd.new" || fail STAGED_LSD_SYNTAX
        cp "$PAYLOAD/CarPlayRouteGuidanceD1.jar" "$JAR.new" || fail STAGE_JAR
        [ "$(size "$JAR.new")" = "$JAR_SIZE" ] || fail STAGED_JAR_SIZE
        chmod 644 "$JAR.new" || fail STAGED_JAR_MODE
        # Keep the script's original executable mode (new contents only).
        cp -p "$LSD" "$LSD.rgi-new" || fail STAGE_SCRIPT_MODE
        cat "$BACKUP/lsd.new" > "$LSD.rgi-new" || fail STAGE_SCRIPT_CONTENT
        mv "$JAR.new" "$JAR" || fail JAR_REPLACE
        if ! mv "$LSD.rgi-new" "$LSD"; then
            rm -f "$JAR"; fail LSD_REPLACE_OLD_SCRIPT_RETAINED
        fi
        echo "$BUILD_ID" > "$BACKUP/VERSION" || fail INSTALL_MARKER
        sync
        echo "CPMAP_RGI_D1_INSTALLED_REBOOT_REQUIRED"
        exit 0 ;;
    uninstall)
        disable
        # Stop is best effort: a missing binary must never block HMI removal.
        if [ -d "$RAM/capture" ] && [ "$(size "$RAM/rgi-observer")" = "$BINARY_SIZE" ]; then
            native "$NR/rgi-observer" stop "$NR/capture" || echo "D1 recorder stop unconfirmed; reboot will stop it"
        fi
        regular "$LSD" || fail LSD_NOT_REGULAR
        [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] || fail BACKUP_MISSING
        [ -n "${CPMAP_TEST_ROOT:-}" ] || native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
        # Surgical removal retains unrelated jars installed AFTER D1 too.
        awk -v target="$TARGET" '
            index($0,"CarPlayRouteGuidanceD1.jar") {
                count++; p=index($0,target)
                if(!p || $0 !~ /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/) exit 4
                if($0=="BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\"") next
                before=substr($0,1,p-1); after=substr($0,p+length(target))
                if(substr(after,1,1)==":") $0=before substr(after,2)
                else if(after=="\"" && substr(before,length(before),1)==":") $0=substr(before,1,length(before)-1) after
                else exit 5
            }
            {print}
            END{if(count>1) exit 6}
        ' "$LSD" > "$BACKUP/lsd.restore" || fail REMOVE_BOOT_ENTRY
        /bin/ksh -n "$BACKUP/lsd.restore" || fail RESTORE_SCRIPT_SYNTAX
        [ "$(awk '/CarPlayRouteGuidanceD1.jar/{n++} END{print n+0}' "$BACKUP/lsd.restore")" = 0 ] || fail RESTORE_ENTRY_REMAINS
        cp -p "$LSD" "$LSD.rgi-new" || fail STAGE_RESTORE_MODE
        cat "$BACKUP/lsd.restore" > "$LSD.rgi-new" || fail STAGE_RESTORE
        mv "$LSD.rgi-new" "$LSD" || fail RESTORE_RENAME_RETRY_UNINSTALL
        rm -f "$JAR" "$JAR.new" "$BACKUP/VERSION" || fail REMOVE_JAR
        sync
        echo "CPMAP_RGI_D1_UNINSTALLED_REBOOT_REQUIRED"
        exit 0 ;;
    shadow|live)
        if [ "$ACTION" = live ] && [ "$ALLOW_LIVE" != 1 ]; then fail LIVE_DISABLED_STARTUP_SHADOW_RETEST; fi
        firmware; installed
        [ ! -e "$RAM/capture" ] && [ ! -L "$RAM/capture" ] || fail EXPORT_AND_CLEAR_PREVIOUS_CAPTURE
        [ "$(cat "$PAYLOAD/VERSION" 2>/dev/null)" = "$BUILD_ID" ] || fail PAYLOAD_VERSION
        [ "$(size "$PAYLOAD/rgi-observer")" = "$BINARY_SIZE" ] || fail PAYLOAD_READER_SIZE
        if [ "$ACTION" = live ]; then
            [ "$(cat "$RAM/shadow-verified" 2>/dev/null)" = "$BUILD_ID" ] || fail RUN_SHADOW_AND_VERIFY_FIRST
        fi
        rm -f "$RAM/adapter-status-before-disable.txt" "$RAM/request-before-disable.txt" \
              "$RAM/adapter-status-observed.txt" "$RAM/request-observed.txt" || fail CLEAR_OLD_STATUS_SNAPSHOTS
        mkdir -p "$RAM" || fail RAM_DIRECTORY
        cp "$PAYLOAD/rgi-observer" "$RAM/rgi-observer" || fail READER_COPY
        [ "$(size "$RAM/rgi-observer")" = "$BINARY_SIZE" ] || fail RAM_READER_SIZE
        chmod 755 "$RAM/rgi-observer" || fail READER_MODE
        native "$NR/rgi-observer" start "$N/dev/ipod0/rgi-events" "$NR/capture" 300 || fail READER_START
        echo "$ACTION $$" > "$RAM/request.new" || fail REQUEST_WRITE
        if [ "$ACTION" = shadow ]; then
            rm -f "$RAM/shadow-verified" "$RAM/shadow-verification.txt" || fail CLEAR_OLD_PROOF
        fi
        mv "$RAM/request.new" "$RAM/request" || fail REQUEST_COMMIT
        echo "$BUILD_ID" > "$RAM/VERSION" || fail RUN_MARKER
        echo "CPMAP_RGI_D1_STARTED_$ACTION (5-minute maximum)"; exit 0 ;;
    verify)
        installed
        regular "$RAM/adapter-status.txt" || fail ADAPTER_STATUS_MISSING_REBOOT_REQUIRED
        regular "$RAM/request" || fail NO_ACTIVE_SHADOW_REQUEST
        requested=$(cat "$RAM/request")
        case "$requested" in 'shadow '*) run_id=${requested#shadow } ;; *) fail SHADOW_REQUEST_REQUIRED ;; esac
        status_copy "$RAM/adapter-status.txt" "$RAM/shadow-verification" 2048 || fail SHADOW_STATUS_SNAPSHOT_FAILED
        awk -v build="$SOURCE_ID" -v run="$run_id" '
            {for(i=1;i<=NF;i++){split($i,a,"="); v[a[1]]=a[2]}}
            END{exit !(v["build"]==build && v["run"]==run && v["mode"]==1 && v["context"]==0 && v["ticks"]>0 && v["proposals"]>0 && v["writes"]==0 && v["failures"]==0 && v["error"]==0)}
        ' "$RAM/shadow-verification" || fail SHADOW_NOT_HEALTHY_USE_STATUS_AND_EXPORT
        mv "$RAM/shadow-verification" "$RAM/shadow-verification.txt" || fail VERIFY_STATUS_COMMIT
        echo "$BUILD_ID" > "$RAM/shadow-verified" || fail VERIFY_MARKER
        echo "CPMAP_RGI_D1_SHADOW_VERIFIED"; exit 0 ;;
    export)
        if ! save_requested_status before-disable; then
            disable; stop_reader; fail STATUS_SNAPSHOT_FAILED_BRIDGE_DISABLED_RETRY_EXPORT
        fi
        disable; stop_reader ;;
esac
command -v dd >/dev/null 2>&1 || fail MISSING_dd
VOL=""
for v in ${CPMAP_TEST_VOL:-/net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0}; do
    if [ -d "$v" ]; then VOL=$v; break; fi
done
[ -n "$VOL" ] || fail SD_NOT_FOUND
[ -n "${CPMAP_TEST_ROOT:-}" ] || mount -uw "$VOL" >/dev/null 2>&1 || fail SD_REMOUNT
mkdir -p "$VOL/Log" || fail SD_DIRECTORY
OUT=$VOL/Log/cpmap-rgi-D1-$$
mkdir "$OUT" || fail SD_DIRECTORY
copy_file() {
    count=$(size "$1") || fail EXPORT_SOURCE_STAT
    [ "$count" -le "$3" ] || fail EXPORT_SOURCE_OVERSIZED
    blocks=$(((count+4095)/4096))
    dd "if=$1" "of=$2" bs=4096 "count=$blocks" 2>> "$OUT/copy-errors.txt" || fail EXPORT_COPY
    [ "$(size "$2")" = "$count" ] || fail EXPORT_COPY_SIZE
}
copy_file "$RAM/capture/events.rgj" "$OUT/events.rgj" 8388608
copy_file "$RAM/capture/status.txt" "$OUT/recorder-status.txt" 1024
[ ! -f "$RAM/adapter-status.txt" ] || copy_file "$RAM/adapter-status.txt" "$OUT/adapter-status.txt" 2048
for name in adapter-status-before-disable.txt adapter-status-observed.txt shadow-verification.txt; do
    [ ! -f "$RAM/$name" ] || copy_file "$RAM/$name" "$OUT/$name" 2048
done
for name in request-before-disable.txt request-observed.txt; do
    [ ! -f "$RAM/$name" ] || copy_file "$RAM/$name" "$OUT/$name" 64
done
[ ! -f "$RAM/VERSION" ] || copy_file "$RAM/VERSION" "$OUT/VERSION" 128
echo "CPMAP_RGI_D1_EXPORT_OK" > "$OUT/progress.txt"
if [ -z "${CPMAP_TEST_ROOT:-}" ]; then sync; mount -ur "$VOL" >/dev/null 2>&1 || fail SD_READONLY; fi
echo "CPMAP_RGI_D1_EXPORT_OK $OUT"
