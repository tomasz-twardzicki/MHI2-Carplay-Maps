#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# MU1367 / 791 experimental integration. Install video first; full reboot after changes.
set -u
ACTION=${1:-status}
PAYLOAD=${2:-}
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && { [ ! -s /ifs/lsd.jxe ] || [ ! -d /mnt/app ]; }; then M=/net/mmx; fi
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367
RAM=$M/ramdisk/carplay-route-guidance
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
ROLLBACK=no
STAGES=no
BUILD=@BUILD@
# Generated, shell-quoted hashes and fixed payload names.
@HASHES@
path() {
    case "$1" in
        driver) echo "$APP/armle/lib/dll/ipod-drvr-iap2.so" ;;
        config) echo "$M/mnt/system/etc/mm/iap2.cfg" ;;
        boot) echo "$APP/eso/hmi/lsd/lsd.sh" ;;
        guidance) echo "$APP/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar" ;;
        audio) echo "$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar" ;;
        navignore) echo "$APP/eso/hmi/lsd/jars/CarPlayMU1367NavIgnore.jar" ;;
        *) return 1 ;;
    esac
}
regular() { [ -f "$1" ] && [ ! -L "$1" ]; }
absent() { [ ! -e "$1" ] && [ ! -L "$1" ]; }
native() {
    if [ -n "${CPMAP_TEST_ROOT:-}" ]; then case "$1" in mount) return 0 ;; esac; "$@"
    elif [ "$M" = /net/mmx ]; then
        C=$1; shift; case "$C" in /net/mmx/*) C=${C#/net/mmx} ;; esac
        on -f mmx "$C" "$@"
    else "$@"; fi
}
verify_file() {
    regular "$1" || return 1
    F=$1; if [ "$M" = /net/mmx ]; then F=${F#/net/mmx}; fi
    native "$VERIFY" "$F" "$2"
}
digest() {
    F=$1; if [ "$M" = /net/mmx ]; then F=${F#/net/mmx}; fi
    native "$VERIFY" "$F"
}
state() { echo "$1" > "$ROOT/STATE.new" && mv "$ROOT/STATE.new" "$ROOT/STATE" && sync; }
restore() {
    regular "$ROOT/BACKUPS_READY" || return 1
    # Validate ALL backups before restoring ANY of them.
    for K in driver config boot guidance audio navignore; do
        if regular "$ROOT/backup/$K.absent"; then :
        else verify_file "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || return 1; fi
        T=$(path "$K") || return 1
        [ ! -L "$T" ] && absent "$T.mu1367-new" || return 1
    done
    native mount -uw /mnt/app >/dev/null 2>&1 || return 1
    native mount -uw /mnt/system >/dev/null 2>&1 || return 1
    for K in boot guidance audio navignore driver config; do
        T=$(path "$K") || return 1
        if regular "$ROOT/backup/$K.absent"; then rm -f "$T" || return 1
        else
            cp -p "$ROOT/backup/$K" "$T.mu1367-new" && mv "$T.mu1367-new" "$T" || return 1
        fi
    done
    state removed || return 1
    echo MU1367_SNAPSHOT_RESTORED_REBOOT_REQUIRED
}
fail() {
    echo "MU1367_FAIL=$1"
    if [ "$ROLLBACK" = yes ]; then
        ROLLBACK=no
        for K in driver config boot guidance audio navignore; do T=$(path "$K"); rm -f "$T.mu1367-new"; done
        restore || echo MU1367_AUTOMATIC_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER
    fi
    exit 1
}
cleanup() {
    if [ "$OWN" = yes ]; then
        if [ "$STAGES" = yes ]; then
            for K in driver config boot guidance audio navignore; do T=$(path "$K"); rm -f "$T.mu1367-new"; done
        fi
        rm -rf "$LOCK" 2>/dev/null || :
    fi
}
trap cleanup EXIT
trap 'fail INTERRUPTED' HUP INT TERM
for T in ls cat awk cp mv rm mkdir chmod sync; do command -v "$T" >/dev/null 2>&1 || fail "MISSING_$T"; done
[ ! -L "$ROOT" ] && [ ! -L "$RAM" ] || fail RECOVERY_OR_RAM_SYMLINK
[ ! -L "$ROOT/backup" ] || fail BACKUP_SYMLINK
VERIFY=$ROOT/verify
if ! regular "$VERIFY"; then VERIFY=$PAYLOAD/verify; fi
case "$ACTION" in
    status)
        if regular "$ROOT/STATE"; then cat "$ROOT/STATE"; else echo MU1367_NOT_INSTALLED; fi
        for F in "$RAM/status.txt" "$RAM/adapter-status.txt" "$M/ramdisk/carplay-now-playing-n1.status"; do
            if regular "$F"; then cat "$F"; fi
        done
        exit 0 ;;
    disable)
        mkdir -p "$RAM" || fail RAM_DIRECTORY
        : > "$RAM/disabled" || fail DISABLE
        echo MU1367_GUIDANCE_DISABLED_UNTIL_REBOOT_AUDIO_UNCHANGED
        exit 0 ;;
    install|uninstall|recover|artwork-on|artwork-off) ;;
    *) fail INVALID_ACTION ;;
esac
regular "$VERIFY" || fail VERIFIER_MISSING
verify_file "$M/ifs/lsd.jxe" "$H_JXE" || fail EXACT_MU1367_FIRMWARE_REQUIRED
# Reject symlinked parent directories as well as files.
for D in "$APP" "$APP/armle" "$APP/armle/lib" "$APP/armle/lib/dll" "$APP/eso" "$APP/eso/hmi" "$APP/eso/hmi/lsd" "$APP/eso/hmi/lsd/jars" "$M/mnt/system" "$M/mnt/system/etc" "$M/mnt/system/etc/mm"; do
    [ -d "$D" ] && [ ! -L "$D" ] || fail TARGET_PARENT_NOT_DIRECTORY
done
mkdir "$LOCK" 2>/dev/null || fail OPERATION_LOCKED_DO_NOT_REMOVE_UNTIL_OWNER_EXITED
OWN=yes
for K in driver config boot guidance audio navignore; do
    T=$(path "$K")
    regular "$T" || absent "$T" || fail TARGET_NOT_REGULAR
    if [ "$ACTION" = recover ]; then
        regular "$T.mu1367-new" || absent "$T.mu1367-new" || fail RECOVERY_STAGE_SYMLINK
        rm -f "$T.mu1367-new" || fail RECOVERY_STAGE_REMOVE
    else absent "$T.mu1367-new" || fail STALE_STAGE_RUN_SAVED_RECOVER; fi
done
STAGES=yes
LSD=$(path boot)
if [ "$ACTION" = recover ]; then
    restore || fail RECOVERY_FAILED_KEEP_BACKUPS
    exit 0
fi
if [ "$ACTION" = install ]; then
    [ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail INSTALL_MU1367_791_VIDEO_FIRST
    [ "$(cat "$PAYLOAD/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_BUILD
    for K in driver config guidance audio navignore reader capture; do
        eval 'N=$N_'"$K" 'H=$H_'"$K"
        verify_file "$PAYLOAD/$N" "$H" || fail "PAYLOAD_HASH_$K"
    done
    if regular "$ROOT/STATE"; then
        [ "$(cat "$ROOT/STATE")" = installed ] || fail RECOVERY_RETAINED_ARCHIVE_BEFORE_NEW_INSTALL
        [ "$(cat "$ROOT/VERSION")" = "$BUILD" ] || fail DIFFERENT_BUILD_REMOVE_FIRST
        for K in driver config guidance audio navignore; do
            eval 'H=$H_'"$K"
            verify_file "$(path "$K")" "$H" || fail INSTALLED_FILES_CHANGED
        done
        [ "$(awk '/MU1367_AUTOSTART/{n++} END{print n+0}' "$LSD")" = 1 ] || fail INSTALLED_READER_BOOT_ENTRY
        for N in Guidance Audio NavIgnore; do
            [ "$(awk -v name="CarPlayMU1367$N.jar" 'index($0,name){n++} END{print n+0}' "$LSD")" = 1 ] || fail INSTALLED_HMI_BOOT_ENTRY
        done
        echo MU1367_ALREADY_INSTALLED
        exit 0
    fi
    absent "$ROOT" || fail RECOVERY_DIRECTORY_EXISTS_PRESERVE_IT
    verify_file "$(path driver)" "$H_STOCK_DRIVER" || fail EXACT_OEM_DRIVER_REQUIRED
    verify_file "$(path config)" "$H_STOCK_CONFIG" || fail EXACT_OEM_CONFIG_REQUIRED
    absent "$(path guidance)" && absent "$(path audio)" && absent "$(path navignore)" || fail ADAPTER_ALREADY_PRESENT
    absent "$APP/eso/hmi/lsd/jars/NavActiveIgnore.jar" || fail REMOVE_GENERIC_NAV_IGNORE_AND_REBOOT_FIRST
    # Known earlier HMI overrides must be removed with their own recovery first.
    [ "$(awk '/CarPlayRouteGuidance|CarPlayNowPlaying|CarPlayMU1367|CPMAP_GUIDANCE_AUTOSTART|MU1367_AUTOSTART/{n++} END{print n+0}' "$LSD")" = 0 ] || fail CONFLICTING_ADAPTER_BOOT_ENTRIES
    for F in "$APP/carplay-artwork-n2" "$APP/carplay-artwork-n3" "$APP/route-guidance-b1" "$APP/carplay-route-guidance"; do
        absent "$F" || fail OLD_FIRMWARE_RECOVERY_PRESENT_ARCHIVE_FIRST
    done
    [ "$(awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{n++} END{print n+0}' "$LSD")" = 1 ] || fail UNKNOWN_BOOT_LAYOUT
    [ "$(awk '/^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{n++} END{print n+0}' "$LSD")" -le 1 ] || fail MULTIPLE_PREPEND_LINES
    awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{launch=NR} /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{prepend=NR} END{exit (prepend && prepend>=launch)}' "$LSD" || fail PREPEND_AFTER_LAUNCH
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    native mount -uw /mnt/system >/dev/null 2>&1 || fail SYSTEM_REMOUNT
    mkdir -p "$ROOT/backup" || fail RECOVERY_DIRECTORY
    cp "$0" "$ROOT/control.sh" && cp "$VERIFY" "$ROOT/verify" || fail SAVE_RECOVERY
    VERIFY=$ROOT/verify
    chmod 755 "$VERIFY" || fail VERIFIER_MODE
    for K in driver config boot guidance audio navignore; do
        T=$(path "$K")
        if absent "$T"; then : > "$ROOT/backup/$K.absent" || fail ABSENT_MARKER
        else
            cp -p "$T" "$ROOT/backup/$K" || fail BACKUP_COPY
            digest "$T" > "$ROOT/backup/$K.sha256" || fail BACKUP_HASH
            verify_file "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || fail BACKUP_VERIFY
        fi
    done
    cp "$PAYLOAD/rgi-observer" "$ROOT/rgi-observer" && cp "$PAYLOAD/artwork-capture" "$ROOT/artwork-capture" || fail SAVE_HELPERS
    cp "$PAYLOAD/ipod-drvr-iap2-B4.so" "$ROOT/B4.so" && cp "$PAYLOAD/ipod-drvr-iap2-N3.so" "$ROOT/N3.so" || fail SAVE_VARIANTS
    verify_file "$ROOT/N3.so" "$H_N3" || fail ARTWORK_PAYLOAD
    chmod 755 "$ROOT/rgi-observer" "$ROOT/artwork-capture" || fail HELPER_MODE
    echo "$BUILD" > "$ROOT/VERSION" || fail BUILD_MARKER
    : > "$ROOT/BACKUPS_READY" || fail BACKUPS_READY
    state prepared || fail PREPARED_MARKER
    ROLLBACK=yes
    TARGET='$BASE_DIR/lsd/jars/CarPlayMU1367Guidance.jar:$BASE_DIR/lsd/jars/CarPlayMU1367Audio.jar:$BASE_DIR/lsd/jars/CarPlayMU1367NavIgnore.jar'
    BOOT='/mnt/app/carplay-mu1367/rgi-observer start-live /dev/ipod0/rgi-events /ramdisk/carplay-route-guidance >/dev/null 2>&1 || : # MU1367_AUTOSTART'
    awk -v target="$TARGET" -v boot="$BOOT" '
        /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{sub(/-Xbootclasspath\/p:/,"-Xbootclasspath/p:" target ":");done=1}
        /^\$J9 .*\$BOOTCLASSPATH .*-jxe/{if(!done) print "BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:" target "\""; print boot}
        {print}
    ' "$LSD" > "$ROOT/boot.new" || fail STAGE_BOOT
    /bin/ksh -n "$ROOT/boot.new" || fail BOOT_SYNTAX
    for K in guidance audio navignore driver config boot; do
        T=$(path "$K")
        if [ "$K" = boot ]; then
            cp -p "$LSD" "$T.mu1367-new" && cat "$ROOT/boot.new" > "$T.mu1367-new" || fail BOOT_STAGE
        else
            eval 'N=$N_'"$K" 'H=$H_'"$K"
            if regular "$T"; then cp -p "$T" "$T.mu1367-new" || fail STAGE_MODE
            else : > "$T.mu1367-new" && chmod 644 "$T.mu1367-new" || fail JAR_STAGE; fi
            cat "$PAYLOAD/$N" > "$T.mu1367-new" || fail STAGE_CONTENT
            verify_file "$T.mu1367-new" "$H" || fail STAGE_HASH
        fi
        mv "$T.mu1367-new" "$T" || fail FILE_COMMIT
    done
    state installed || fail COMMIT_MARKER
    ROLLBACK=no
    echo MU1367_INSTALLED_REBOOT_REQUIRED
elif [ "$ACTION" = artwork-on ] || [ "$ACTION" = artwork-off ]; then
    [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail INSTALL_INTEGRATION_FIRST
    # This optional swap changes no Java, boot or configuration files.
    if [ "$ACTION" = artwork-on ]; then FROM=$H_driver; TO=$H_N3; SRC=$ROOT/N3.so
    else FROM=$H_N3; TO=$H_driver; SRC=$ROOT/B4.so; fi
    verify_file "$(path driver)" "$FROM" || fail EXPECTED_DRIVER_REQUIRED
    verify_file "$SRC" "$TO" || fail SAVED_VARIANT_HASH
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    T=$(path driver)
    cp -p "$T" "$T.mu1367-new" && cat "$SRC" > "$T.mu1367-new" || fail VARIANT_STAGE
    verify_file "$T.mu1367-new" "$TO" && mv "$T.mu1367-new" "$T" || fail VARIANT_COMMIT
    sync
    echo MU1367_ARTWORK_VARIANT_CHANGED_REBOOT_REQUIRED
else
    [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail USE_RECOVER_FOR_INTERRUPTED_TRANSACTION
    verify_file "$(path driver)" "$H_driver" || verify_file "$(path driver)" "$H_N3" || fail DRIVER_CHANGED_PRESERVE_AND_INSPECT
    verify_file "$(path config)" "$H_config" || fail CONFIG_CHANGED_PRESERVE_AND_INSPECT
    verify_file "$(path guidance)" "$H_guidance" && verify_file "$(path audio)" "$H_audio" && verify_file "$(path navignore)" "$H_navignore" || fail ADAPTER_CHANGED_PRESERVE_AND_INSPECT
    for K in driver config boot; do verify_file "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || fail BACKUP_CORRUPT; done
    # Keep later unrelated boot entries by removing only this integration's tokens.
    awk '
        /MU1367_AUTOSTART/{if($0 !~ /^\/mnt\/app\/carplay-mu1367\/rgi-observer start-live / || ++boot>1) exit 7; next}
        /CarPlayMU1367/ {
            if($0 !~ /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/ || ++entry>1) exit 8
            gsub(/\$BASE_DIR\/lsd\/jars\/CarPlayMU1367Guidance.jar:/,"")
            gsub(/\$BASE_DIR\/lsd\/jars\/CarPlayMU1367Audio.jar:/,"")
            gsub(/\$BASE_DIR\/lsd\/jars\/CarPlayMU1367NavIgnore.jar:/,"")
            sub(/\/p:\$BASE_DIR\/lsd\/jars\/CarPlayMU1367NavIgnore.jar"$/,"/p:\"")
            sub(/:\$BASE_DIR\/lsd\/jars\/CarPlayMU1367NavIgnore.jar"$/,"\"")
            if($0=="BOOTCLASSPATH=\"$BOOTCLASSPATH -Xbootclasspath/p:\"") next
            if(index($0,"CarPlayMU1367")) exit 9
        }
        {print}
        END{if(entry!=1 || boot!=1) exit 10}
    ' "$LSD" > "$ROOT/boot.remove" || fail BOOT_CHANGED_PRESERVE_AND_INSPECT
    /bin/ksh -n "$ROOT/boot.remove" || fail REMOVE_BOOT_SYNTAX
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    native mount -uw /mnt/system >/dev/null 2>&1 || fail SYSTEM_REMOUNT
    mkdir -p "$RAM" && : > "$RAM/disabled" || fail DISABLE
    native "$ROOT/rgi-observer" stop /ramdisk/carplay-route-guidance >/dev/null 2>&1 || :
    cp -p "$LSD" "$LSD.mu1367-new" && cat "$ROOT/boot.remove" > "$LSD.mu1367-new" && mv "$LSD.mu1367-new" "$LSD" || fail REMOVE_BOOT
    for K in driver config; do
        T=$(path "$K")
        cp -p "$ROOT/backup/$K" "$T.mu1367-new" && mv "$T.mu1367-new" "$T" || fail RESTORE_PAIR_RUN_SAVED_RECOVER
    done
    rm -f "$(path guidance)" "$(path audio)" "$(path navignore)" || fail REMOVE_JARS
    state removed || fail REMOVE_STATE
    echo MU1367_REMOVED_REBOOT_REQUIRED_BACKUPS_RETAINED
fi
