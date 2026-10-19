#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# MU1427 native guidance release. Same factory-size checks and staged renames
# as the tested base/B4/D3 installers; no hash utilities required on the unit.
set -u
ACTION=${1:-status}
PAYLOAD=${2:-}
BUILD_ID=@BUILD_ID@
JAR_SIZE=@JAR_SIZE@
READER_SIZE=@READER_SIZE@
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ -s /ifs/lsd.jxe ] && [ -d /mnt/app ]; then :
elif [ -s /net/mmx/ifs/lsd.jxe ]; then M=/net/mmx
else echo "CPMAP_GUIDANCE_FAIL=MMX_NOT_FOUND"; exit 1; fi
APP=$M/mnt/app
ROOT=$APP/carplay-route-guidance
RAM=$M/ramdisk/carplay-route-guidance
LSD=$APP/eso/hmi/lsd/lsd.sh
JAR=$APP/eso/hmi/lsd/jars/CarPlayRouteGuidanceD1.jar
TARGET='$BASE_DIR/lsd/jars/CarPlayRouteGuidanceD1.jar'
BOOT='/mnt/app/carplay-route-guidance/rgi-observer start-live /dev/ipod0/rgi-events /ramdisk/carplay-route-guidance >/dev/null 2>&1 || : # CPMAP_GUIDANCE_AUTOSTART'
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN_LOCK=no
DRIVER_CHANGED=no
BOOT_COMMITTED=no
JAR_CREATED=no
native() {
    if [ -n "${CPMAP_TEST_ROOT:-}" ]; then return 0
    elif [ "$M" = /net/mmx ]; then on -f mmx "$@"
    else "$@"; fi
}
size() {
    line=$(ls -ln "$1" 2>/dev/null) || return 1
    set -- $line
    [ "$#" -ge 5 ] || return 1
    case "$1" in -*) ;; *) return 1 ;; esac
    case "$5" in ''|*[!0-9]*) return 1 ;; esac
    echo "$5"
}
regular() { [ -f "$1" ] && [ ! -L "$1" ]; }
clean() {
    if [ "$OWN_LOCK" = yes ]; then
        rm -f "$JAR.new" "$LSD.rgi-new" "$ROOT/reader.new" "$ROOT/VERSION.new"
        rm -rf "$LOCK"
    fi
}
fail() {
    if [ "$BOOT_COMMITTED" = no ]; then
        [ "$JAR_CREATED" = no ] || rm -f "$JAR"
        if [ "$DRIVER_CHANGED" = yes ]; then
            /bin/ksh "$ROOT/driver-control.sh" restore || echo "CPMAP_GUIDANCE_DRIVER_ROLLBACK_FAILED_RETRY_REMOVE"
        fi
    fi
    echo "CPMAP_GUIDANCE_FAIL=$1"; exit 1
}
trap clean EXIT
trap 'fail INTERRUPTED' HUP INT TERM
check_ram() { [ ! -L "$RAM" ] || fail RAM_SYMLINK; }
disable() {
    check_ram
    mkdir -p "$RAM" || fail RAM_DIRECTORY
    : > "$RAM/disabled" || fail DISABLE_FAILED
    echo "CPMAP_GUIDANCE_DISABLED_UNTIL_REBOOT"
}
for tool in ls cat rm mkdir; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
case "$ACTION" in
    disable) disable; exit 0 ;;
    status)
        check_ram
        if [ -f "$ROOT/VERSION" ]; then cat "$ROOT/VERSION"; else echo "Native guidance is not installed"; fi
        [ ! -f "$RAM/disabled" ] || echo "Native guidance disabled until reboot"
        [ ! -f "$RAM/adapter-status.txt" ] || cat "$RAM/adapter-status.txt"
        [ ! -f "$RAM/status.txt" ] || cat "$RAM/status.txt"
        exit 0 ;;
    install|uninstall) ;;
    *) fail INVALID_ACTION ;;
esac
for tool in awk cp mv chmod sync; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
[ "$(size "$M/ifs/lsd.jxe")" = 52751492 ] || fail MU1427_ONLY
regular "$LSD" || fail LSD_NOT_REGULAR
[ ! -L "$ROOT" ] || fail BACKUP_SYMLINK
mkdir "$LOCK" 2>/dev/null || fail ANOTHER_OPERATION_OR_STALE_LOCK
OWN_LOCK=yes
if [ "$ACTION" = install ]; then
    [ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1427/791 ] || fail INSTALL_791_AUTO_MU_FIRST
    [ "$(cat "$PAYLOAD/VERSION" 2>/dev/null)" = "$BUILD_ID" ] || fail PAYLOAD_VERSION
    [ "$(size "$PAYLOAD/CarPlayRouteGuidanceD1.jar")" = "$JAR_SIZE" ] || fail PAYLOAD_JAR
    [ "$(size "$PAYLOAD/rgi-observer")" = "$READER_SIZE" ] || fail PAYLOAD_READER
    [ "$(size "$PAYLOAD/driver/ipod-drvr-iap2.so")" = 743196 ] || fail PAYLOAD_DRIVER
    [ "$(size "$PAYLOAD/driver/iap2.cfg")" = 6006 ] || fail PAYLOAD_CONFIG
    [ "$(cat "$PAYLOAD/driver/VERSION" 2>/dev/null)" = MU1427-iAP2-RGI-B4-3760797a ] || fail PAYLOAD_DRIVER_VERSION
    regular "$PAYLOAD/driver-control.sh" || fail PAYLOAD_DRIVER_CONTROLLER
    if [ -f "$ROOT/VERSION" ]; then
        [ "$(cat "$ROOT/VERSION")" = "$BUILD_ID" ] || fail DIFFERENT_RELEASE_REMOVE_AND_REBOOT_FIRST
        [ "$(size "$JAR")" = "$JAR_SIZE" ] && [ "$(size "$ROOT/rgi-observer")" = "$READER_SIZE" ] || fail INSTALLED_PAYLOAD_SIZE
        [ "$(awk '/CarPlayRouteGuidanceD1.jar/{n++} END{print n+0}' "$LSD")" = 1 ] || fail INSTALLED_BOOT_ENTRY
        [ "$(awk '/CPMAP_GUIDANCE_AUTOSTART/{n++} END{print n+0}' "$LSD")" = 1 ] || fail INSTALLED_READER_ENTRY
        [ "$(size "$APP/armle/lib/dll/ipod-drvr-iap2.so")" = 743196 ] && [ "$(size "$M/mnt/system/etc/mm/iap2.cfg")" = 6006 ] || fail INSTALLED_DRIVER_CONFIG
        [ "$(size "$APP/route-guidance-b1/stock-driver.so")" = 739925 ] && [ "$(size "$APP/route-guidance-b1/stock-iap2.cfg")" = 5905 ] || fail DRIVER_OEM_BACKUPS_REQUIRED
        echo "CPMAP_GUIDANCE_ALREADY_INSTALLED"; exit 0
    fi
    [ ! -e "$JAR" ] && [ ! -L "$JAR" ] || fail REMOVE_TEST_HMI_ADAPTER_AND_REBOOT_FIRST
    [ "$(awk '/CarPlayRouteGuidanceD1.jar|CPMAP_GUIDANCE_AUTOSTART/{n++} END{print n+0}' "$LSD")" = 0 ] || fail PREVIOUS_GUIDANCE_BOOT_ENTRY
    [ "$(awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{n++} END{print n+0}' "$LSD")" = 1 ] || fail UNKNOWN_LSD_LAYOUT
    [ "$(awk '/^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{n++} END{print n+0}' "$LSD")" -le 1 ] || fail MULTIPLE_PREPEND_LINES
    awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{launch=NR} /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{prepend=NR} END{exit (prepend && prepend>=launch)}' "$LSD" || fail PREPEND_AFTER_LAUNCH
    D=$(size "$APP/armle/lib/dll/ipod-drvr-iap2.so") || fail DRIVER_MISSING
    C=$(size "$M/mnt/system/etc/mm/iap2.cfg") || fail CONFIG_MISSING
    case "$D/$C" in 739925/5905|743196/6006) ;; *) fail OEM_OR_TESTED_DRIVER_PAIR_REQUIRED ;; esac
    if [ "$D" = 743196 ]; then
        [ "$(cat "$APP/route-guidance-b1/VERSION" 2>/dev/null)" = MU1427-iAP2-RGI-B4-3760797a ] || fail DRIVER_MARKER_REQUIRED
        [ "$(size "$APP/route-guidance-b1/stock-driver.so")" = 739925 ] && [ "$(size "$APP/route-guidance-b1/stock-iap2.cfg")" = 5905 ] || fail DRIVER_OEM_BACKUPS_REQUIRED
    fi
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    mkdir -p "$ROOT" || fail BACKUP_DIRECTORY
    cp "$LSD" "$ROOT/original-lsd.sh" || fail BACKUP_SCRIPT
    cp "$0" "$ROOT/control.sh" || fail BACKUP_CONTROLLER
    cp "$PAYLOAD/driver-control.sh" "$ROOT/driver-control.sh" || fail BACKUP_DRIVER_CONTROLLER
    awk -v target="$TARGET" -v boot="$BOOT" '
        BEGIN{done=0}
        /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{sub(/-Xbootclasspath\/p:/,"-Xbootclasspath/p:" target ":");done=1}
        /^\$J9 .*\$BOOTCLASSPATH .*-jxe/{
            if(!done) print "BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\""
            print boot
        }
        {print}
    ' "$LSD" > "$ROOT/lsd.new" || fail STAGE_SCRIPT
    /bin/ksh -n "$ROOT/lsd.new" || fail STAGED_SYNTAX
    cp "$PAYLOAD/CarPlayRouteGuidanceD1.jar" "$JAR.new" || fail STAGE_JAR
    cp "$PAYLOAD/rgi-observer" "$ROOT/reader.new" || fail STAGE_READER
    [ "$(size "$JAR.new")" = "$JAR_SIZE" ] && [ "$(size "$ROOT/reader.new")" = "$READER_SIZE" ] || fail STAGED_SIZE
    chmod 644 "$JAR.new" || fail JAR_MODE
    chmod 755 "$ROOT/reader.new" || fail READER_MODE
    echo "$BUILD_ID" > "$ROOT/VERSION.new" || fail STAGE_MARKER
    cp -p "$LSD" "$LSD.rgi-new" || fail STAGE_SCRIPT_MODE
    cat "$ROOT/lsd.new" > "$LSD.rgi-new" || fail STAGE_SCRIPT_CONTENT
    if [ "$D" = 739925 ]; then
        /bin/ksh "$ROOT/driver-control.sh" install "$PAYLOAD/driver" || fail DRIVER_INSTALL
        DRIVER_CHANGED=yes
    fi
    mv "$ROOT/reader.new" "$ROOT/rgi-observer" || fail READER_REPLACE
    mv "$JAR.new" "$JAR" || fail JAR_REPLACE
    JAR_CREATED=yes
    mv "$LSD.rgi-new" "$LSD" || fail BOOT_REPLACE_OLD_SCRIPT_RETAINED
    BOOT_COMMITTED=yes
    mv "$ROOT/VERSION.new" "$ROOT/VERSION" || fail MARKER_COMMIT_USE_SAVED_REMOVE
    sync
    echo "CPMAP_GUIDANCE_INSTALLED_REBOOT_REQUIRED"
else
    disable
    if [ -f "$RAM/status.txt" ] && [ "$(size "$ROOT/rgi-observer")" = "$READER_SIZE" ]; then
        native /mnt/app/carplay-route-guidance/rgi-observer stop /ramdisk/carplay-route-guidance || echo "Reader stop unconfirmed; output disabled, reboot after removal"
    fi
    [ -d "$ROOT" ] || fail RECOVERY_DIRECTORY_MISSING
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    # Preserve unrelated HMI entries, including changes installed after us.
    awk -v target="$TARGET" -v boot="$BOOT" '
        /CPMAP_GUIDANCE_AUTOSTART/{if($0!=boot || ++boots>1) exit 7;next}
        index($0,"CarPlayRouteGuidanceD1.jar") {
            count++;p=index($0,target)
            if(!p || $0 !~ /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/) exit 4
            if($0=="BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\"") next
            before=substr($0,1,p-1);after=substr($0,p+length(target))
            if(substr(after,1,1)==":") $0=before substr(after,2)
            else if(after=="\"" && substr(before,length(before),1)==":") $0=substr(before,1,length(before)-1) after
            else exit 5
        }
        {print}
        END{if(count>1) exit 6}
    ' "$LSD" > "$ROOT/lsd.restore" || fail REMOVE_SCRIPT_STRUCTURE
    /bin/ksh -n "$ROOT/lsd.restore" || fail RESTORE_SYNTAX
    cp -p "$LSD" "$LSD.rgi-new" || fail RESTORE_MODE
    cat "$ROOT/lsd.restore" > "$LSD.rgi-new" || fail RESTORE_CONTENT
    mv "$LSD.rgi-new" "$LSD" || fail RESTORE_RENAME_KEEP_JAR_RETRY_REMOVE
    rm -f "$JAR" || fail REMOVE_JAR
    if [ "$(size "$APP/armle/lib/dll/ipod-drvr-iap2.so")" != 739925 ] || [ "$(size "$M/mnt/system/etc/mm/iap2.cfg")" != 5905 ]; then
        /bin/ksh "$ROOT/driver-control.sh" restore || fail DRIVER_RESTORE_RETRY_REMOVE
    fi
    rm -f "$ROOT/VERSION" || fail REMOVE_MARKER
    sync
    echo "CPMAP_GUIDANCE_REMOVED_REBOOT_REQUIRED"
fi
