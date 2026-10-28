#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# N0 research only: no driver, media source or navigation changes.
set -u
ACTION=${1:-status}
INPUT=${2:-}
BUILD_ID=@BUILD_ID@
JAR_SIZE=@JAR_SIZE@
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ -s /ifs/lsd.jxe ] && [ -d /mnt/app ]; then :
elif [ -s /net/mmx/ifs/lsd.jxe ]; then M=/net/mmx
else echo "CPMAP_AUDIO_N0_FAIL=MMX_NOT_FOUND"; exit 1; fi
APP=$M/mnt/app
ROOT=$APP/carplay-now-playing-n0
RAM=$M/ramdisk/carplay-now-playing-n0.status
LSD=$APP/eso/hmi/lsd/lsd.sh
JAR=$APP/eso/hmi/lsd/jars/CarPlayNowPlayingObserverN0.jar
TARGET='$BASE_DIR/lsd/jars/CarPlayNowPlayingObserverN0.jar'
# Share the native-guidance lock: both controllers edit lsd.sh.
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN_LOCK=no
JAR_CREATED=no
BOOT_COMMITTED=no
size() {
    line=$(ls -ln "$1" 2>/dev/null) || return 1
    set -- $line
    [ "$#" -ge 5 ] || return 1
    case "$1" in -*) ;; *) return 1 ;; esac
    case "$5" in ''|*[!0-9]*) return 1 ;; esac
    echo "$5"
}
regular() { [ -f "$1" ] && [ ! -L "$1" ]; }
absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
clean() {
    if [ "$OWN_LOCK" = yes ]; then
        rm -f "$JAR.new" "$LSD.audio-new" "$ROOT/VERSION.new"
        rm -rf "$LOCK"
    fi
}
fail() {
    if [ "$JAR_CREATED" = yes ] && [ "$BOOT_COMMITTED" = no ]; then rm -f "$JAR"; fi
    echo "CPMAP_AUDIO_N0_FAIL=$1"; exit 1
}
trap clean EXIT
trap 'fail INTERRUPTED' HUP INT TERM
native() {
    if [ -n "${CPMAP_TEST_ROOT:-}" ]; then return 0
    elif [ "$M" = /net/mmx ]; then on -f mmx "$@"
    else "$@"; fi
}
status() {
    echo "N0 observation only; no cluster text/artwork output"
    if regular "$ROOT/VERSION"; then cat "$ROOT/VERSION"; else echo "N0_NOT_INSTALLED_OR_MARKER_MISSING"; fi
    if regular "$RAM"; then
        N=$(size "$RAM") || fail STATUS_SIZE
        [ "$N" -le 4096 ] || fail STATUS_OVERSIZE
        cat "$RAM" || fail STATUS_READ
    elif [ -L "$RAM" ]; then fail STATUS_SYMLINK
    else echo "N0_STATUS_NOT_AVAILABLE_YET"; fi
}
for tool in ls cat rm mkdir; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
case "$ACTION" in
    status) status; exit 0 ;;
    export)
        [ -n "$INPUT" ] && absent "$INPUT" || fail EXPORT_NEW_DIRECTORY_REQUIRED
        mkdir "$INPUT" || fail EXPORT_DIRECTORY
        status > "$INPUT/status.txt" || fail EXPORT_STATUS
        echo "CPMAP_AUDIO_N0_EXPORTED=$INPUT"
        exit 0 ;;
    install|uninstall) ;;
    *) fail INVALID_ACTION ;;
esac
for tool in awk cp mv chmod sync; do command -v "$tool" >/dev/null 2>&1 || fail "MISSING_$tool"; done
[ "$(size "$M/ifs/lsd.jxe")" = 52751492 ] || fail MU1427_ONLY
regular "$LSD" || fail LSD_NOT_REGULAR
[ ! -L "$ROOT" ] || fail RECOVERY_SYMLINK
mkdir "$LOCK" 2>/dev/null || fail ANOTHER_OPERATION_OR_STALE_LOCK
OWN_LOCK=yes
absent "$JAR.new" && absent "$LSD.audio-new" || fail STALE_STAGING_FILE
if [ "$ACTION" = install ]; then
    [ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1427/791 ] || fail INSTALL_791_AUTO_MU_FIRST
    regular "$INPUT/CarPlayNowPlayingObserverN0.jar" || fail PAYLOAD_JAR_NOT_REGULAR
    [ "$(cat "$INPUT/VERSION" 2>/dev/null)" = "$BUILD_ID" ] || fail PAYLOAD_VERSION
    [ "$(size "$INPUT/CarPlayNowPlayingObserverN0.jar")" = "$JAR_SIZE" ] || fail PAYLOAD_JAR_SIZE
    if regular "$ROOT/VERSION"; then
        [ "$(cat "$ROOT/VERSION")" = "$BUILD_ID" ] || fail DIFFERENT_BUILD_REMOVE_AND_REBOOT_FIRST
        regular "$JAR" && [ "$(size "$JAR")" = "$JAR_SIZE" ] || fail INSTALLED_JAR
        awk -v target="$TARGET" '
            index($0,"CarPlayNowPlayingObserverN0.jar") {
                n++;p=index($0,target)
                if(!p || $0 !~ /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/) bad=1
                if(p && index(substr($0,p+length(target)),"CarPlayNowPlayingObserverN0.jar")) bad=1
            }
            END{exit (n!=1 || bad)}
        ' "$LSD" || fail INSTALLED_BOOT_ENTRY
        echo "CPMAP_AUDIO_N0_ALREADY_INSTALLED"; exit 0
    fi
    absent "$JAR" || fail EXISTING_JAR_REMOVE_AND_REBOOT_FIRST
    [ "$(awk '/CarPlayNowPlayingObserverN0.jar/{n++} END{print n+0}' "$LSD")" = 0 ] || fail EXISTING_BOOT_ENTRY
    [ "$(awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{n++} END{print n+0}' "$LSD")" = 1 ] || fail UNKNOWN_LSD_LAYOUT
    [ "$(awk '/^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{n++} END{print n+0}' "$LSD")" -le 1 ] || fail MULTIPLE_PREPEND_LINES
    awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{launch=NR} /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{prepend=NR} END{exit (prepend && prepend>=launch)}' "$LSD" || fail PREPEND_AFTER_LAUNCH
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    mkdir -p "$ROOT" || fail RECOVERY_DIRECTORY
    for f in original-lsd.sh control.sh VERSION VERSION.new lsd.new; do [ ! -L "$ROOT/$f" ] || fail RECOVERY_FILE_SYMLINK; done
    cp "$LSD" "$ROOT/original-lsd.sh" || fail BACKUP_SCRIPT
    cp "$0" "$ROOT/control.sh" || fail BACKUP_CONTROLLER
    awk -v target="$TARGET" '
        BEGIN{done=0}
        /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{sub(/-Xbootclasspath\/p:/,"-Xbootclasspath/p:" target ":");done=1}
        /^\$J9 .*\$BOOTCLASSPATH .*-jxe/{if(!done) print "BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\""}
        {print}
    ' "$LSD" > "$ROOT/lsd.new" || fail STAGE_SCRIPT
    /bin/ksh -n "$ROOT/lsd.new" || fail STAGED_SYNTAX
    cp "$INPUT/CarPlayNowPlayingObserverN0.jar" "$JAR.new" || fail STAGE_JAR
    [ "$(size "$JAR.new")" = "$JAR_SIZE" ] || fail STAGED_JAR_SIZE
    chmod 644 "$JAR.new" || fail JAR_MODE
    echo "$BUILD_ID" > "$ROOT/VERSION.new" || fail STAGE_MARKER
    cp -p "$LSD" "$LSD.audio-new" || fail STAGE_SCRIPT_MODE
    cat "$ROOT/lsd.new" > "$LSD.audio-new" || fail STAGE_SCRIPT_CONTENT
    mv "$JAR.new" "$JAR" || fail JAR_COMMIT
    JAR_CREATED=yes
    mv "$LSD.audio-new" "$LSD" || fail BOOT_COMMIT_OLD_SCRIPT_RETAINED
    BOOT_COMMITTED=yes
    mv "$ROOT/VERSION.new" "$ROOT/VERSION" || fail MARKER_COMMIT_USE_SAVED_REMOVE
    sync
    echo "CPMAP_AUDIO_N0_INSTALLED_REBOOT_REQUIRED"
else
    [ -d "$ROOT" ] || fail RECOVERY_DIRECTORY_MISSING
    [ ! -L "$ROOT/lsd.restore" ] || fail RECOVERY_FILE_SYMLINK
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    awk -v target="$TARGET" '
        index($0,"CarPlayNowPlayingObserverN0.jar") {
            count++;p=index($0,target)
            if(!p || $0 !~ /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/) exit 4
            if($0=="BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\"") next
            before=substr($0,1,p-1);after=substr($0,p+length(target))
            if(substr(after,1,1)==":") $0=before substr(after,2)
            else if(after=="\"" && substr(before,length(before),1)==":") $0=substr(before,1,length(before)-1) after
            else exit 5
            if(index($0,"CarPlayNowPlayingObserverN0.jar")) exit 6
        }
        {print}
        END{if(count>1) exit 7}
    ' "$LSD" > "$ROOT/lsd.restore" || fail REMOVE_SCRIPT_STRUCTURE_KEEP_JAR
    /bin/ksh -n "$ROOT/lsd.restore" || fail RESTORE_SYNTAX
    cp -p "$LSD" "$LSD.audio-new" || fail RESTORE_MODE
    cat "$ROOT/lsd.restore" > "$LSD.audio-new" || fail RESTORE_CONTENT
    mv "$LSD.audio-new" "$LSD" || fail RESTORE_RENAME_KEEP_JAR_RETRY_REMOVE
    BOOT_COMMITTED=yes
    rm -f "$JAR" || fail REMOVE_JAR
    rm -f "$ROOT/VERSION" || fail REMOVE_MARKER
    sync
    echo "CPMAP_AUDIO_N0_REMOVED_REBOOT_REQUIRED"
fi
