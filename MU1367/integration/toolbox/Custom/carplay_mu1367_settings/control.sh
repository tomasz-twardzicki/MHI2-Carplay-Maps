#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-}
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367-settings
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
STAGED=no
ROLLBACK=no
BUILD=MU1367-settings-v2-2b9533e277a6
KEYS='menu controls core supervisor bridge tap query canvas wrapper launcher parent boot'
FILES='menu controls core supervisor bridge tap query canvas wrapper launcher'
PARENT_BUILD=MU1367-integration-7262b3242a11
GUARD_SHA=3ac4a58fd215c151f6963da6a8be5ab034ef85c9f57488d2f7acf31fc4b55e06
target(){ case "$1" in
 menu) echo "$APP/eso/hmi/lsd/jars/VCMenu.jar" ;;
 controls) echo "$APP/eso/hmi/lsd/jars/CarPlayClusterControls.jar" ;;
 core) echo "$APP/carplaymaps/core.so" ;;
 supervisor) echo "$APP/carplaymaps/carplay-cluster-supervisor" ;;
 bridge) echo "$APP/carplaymaps/altscreen-most-bridge" ;;
 tap) echo "$APP/carplaymaps/libcpvc-mirror-tap.so" ;;
 query) echo "$APP/carplaymaps/libcpvc-dmdt-query.so" ;;
 canvas) echo "$APP/carplaymaps/cpvc-mirror-canvas" ;;
 wrapper) echo "$APP/carplaymaps/dio_manager.wrapper.sh" ;;
 launcher) echo "$APP/eso/bin/apps/dio_manager" ;;
 parent) echo "$APP/carplay-mu1367/control.sh" ;;
 boot) echo "$APP/eso/hmi/lsd/lsd.sh" ;;
 *) return 1 ;; esac; }
payload(){ case "$1" in
 menu) echo VCMenu.jar ;;
 controls) echo CarPlayClusterControls.jar ;;
 core) echo core.so ;;
 supervisor) echo carplay-cluster-supervisor ;;
 bridge) echo altscreen-most-bridge ;;
 tap) echo libcpvc-mirror-tap.so ;;
 query) echo libcpvc-dmdt-query.so ;;
 canvas) echo cpvc-mirror-canvas-791 ;;
 wrapper) echo dio_manager.wrapper.sh ;;
 launcher) echo dio_manager.wrapper.sh ;;
 *) return 1 ;; esac; }
mode(){ case "$1" in
 menu) echo 644 ;;
 controls) echo 644 ;;
 core) echo 644 ;;
 supervisor) echo 755 ;;
 bridge) echo 755 ;;
 tap) echo 644 ;;
 query) echo 644 ;;
 canvas) echo 755 ;;
 wrapper) echo 755 ;;
 launcher) echo 755 ;;
 parent) echo 755 ;;
 boot) echo 755 ;;
 *) return 1 ;; esac; }
expected(){ case "$1" in
 menu) echo 7ab271624c3999edee58c5502a8d645f22db206297032fffad32ce8f53e625ee ;;
 controls) echo 91d3cf2cf7d5fb19fe1042ea4985c9929b61955f90b7217800ea3904d3cb63c8 ;;
 core) echo 28b32ff2076281c7dc7b2931cbd08ec0916f2ffceeeff4462b46d218265938af ;;
 supervisor) echo 350f617c5618046cef806d38c66a422fe5ac7d34ded50b70393d72f8582c4794 ;;
 bridge) echo 6c5210cac43699caf027b1f217dc39f4fe87c8b2aee3fa6366c20856772f9c35 ;;
 tap) echo 647f3dbdd51245e16785c2ddc46afc2158fc2c06292f9d1e9e4077b17de0c69c ;;
 query) echo 9b72ea95c21a9ad2170a0b855a4c691f3b2629c590b85b0e85f7fd177236f729 ;;
 canvas) echo 618b6bda53a2ee635be594734874dc5d20b2d92505ae24027b0876d33e75abc0 ;;
 wrapper) echo 1e2cecd872d864db9404d1d89e0f6ba5ba64fb1d162263b3f4e9ee010225863f ;;
 launcher) echo 1e2cecd872d864db9404d1d89e0f6ba5ba64fb1d162263b3f4e9ee010225863f ;;
 *) return 1 ;; esac; }
before(){ case "$1" in
 menu) absent "$2" ;;
 controls) check "$2" c8ceaad026c2efa20ec190260cb0ba7c982ccf7f1b3754c31c1930fa461ac032 ;;
 core) check "$2" 53c6b094867fecf72caf890a694cba4833f645543dcfe43ba54afb8ac50de562 || check "$2" 36fcc12b8aa7eeda6c3a9256d2c6a00984f01cbd2ca4d839c4f2efefef5b2e1b || check "$2" 7737c75068e1dbefd61a97b6f06f1bff26a2d4529daf48aa123bc550d9e73519 || check "$2" 00b48a8fe876e6ff405124b87ed9eace1bcb079220ff7f02b866f42676477a4a ;;
 supervisor) check "$2" cdc2f9c64eae15ecfc57eafcd497a9a19582d04c7068b0a48e0b84c5d6546b24 ;;
 bridge) check "$2" c846e505da704f101815a4658f1b815930d0b6f779d435349b864ef96056c8f3 ;;
 tap) absent "$2" ;;
 query) absent "$2" ;;
 canvas) absent "$2" ;;
 wrapper) check "$2" c7889641338663fc9575834307f6d170a363644a85e5e66bb5b59fa1cfd358fc ;;
 launcher) check "$2" c7889641338663fc9575834307f6d170a363644a85e5e66bb5b59fa1cfd358fc ;;
 parent) check "$2" c44123309f867ac4b6d3b2bb085dd84e119b77fb3d8a56db61f85dfa8b16264f ;;
 *) return 1 ;; esac; }

regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
native(){
    if [ -n "${CPMAP_TEST_ROOT:-}" ]; then case "$1" in mount) return 0 ;; esac; "$@"
    elif [ "$M" = /net/mmx ]; then C=$1;shift;case "$C" in /net/mmx/*) C=${C#/net/mmx} ;; esac;on -f mmx "$C" "$@"
    else "$@";fi
}
VERIFY=$ROOT/verify
regular "$VERIFY" || VERIFY=$P/verify
digest(){ F=$1;if [ "$M" = /net/mmx ]; then F=${F#/net/mmx};fi;native "$VERIFY" "$F"; }
check(){ regular "$1" || return 1;F=$1;if [ "$M" = /net/mmx ]; then F=${F#/net/mmx};fi;native "$VERIFY" "$F" "$2"; }
state(){ echo "$1" > "$ROOT/STATE.new" && mv "$ROOT/STATE.new" "$ROOT/STATE" && sync; }
restore(){
    regular "$ROOT/BACKUPS_READY" || return 1
    for K in $KEYS;do
        if regular "$ROOT/backup/$K.absent";then :
        else check "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || return 1;fi
    done
    native mount -uw /mnt/app >/dev/null 2>&1 || return 1
    # Boot remains the final commit in both installation and restoration.
    for K in $KEYS;do
        T=$(target "$K") || return 1
        if regular "$ROOT/backup/$K.absent";then rm -f "$T" || return 1
        else cp -p "$ROOT/backup/$K" "$T.settings-new" && mv "$T.settings-new" "$T" || return 1;fi
    done
    state removed || return 1
    echo MU1367_SETTINGS_SNAPSHOT_RESTORED_REBOOT_REQUIRED
}
drop_stages(){ for K in $KEYS;do T=$(target "$K");rm -f "$T.settings-new";done; }
fail(){
    echo "MU1367_SETTINGS_FAIL=$1"
    if [ "$ROLLBACK" = yes ];then ROLLBACK=no;drop_stages;restore || echo MU1367_SETTINGS_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER;fi
    exit 1
}
cleanup(){ if [ "$OWN" = yes ];then [ "$STAGED" = no ] || drop_stages;rm -rf "$LOCK";fi; }
trap cleanup EXIT
trap 'fail INTERRUPTED' HUP INT TERM
for T in ls cat awk cp mv rm mkdir chmod sync;do command -v "$T" >/dev/null 2>&1 || fail "MISSING_$T";done
[ ! -L "$ROOT" ] && [ ! -L "$ROOT/backup" ] || fail RECOVERY_SYMLINK
case "$ACTION" in
    status)
        if regular "$ROOT/STATE";then cat "$ROOT/STATE";else echo MU1367_SETTINGS_NOT_INSTALLED;fi
        if regular "$ROOT/VERSION";then cat "$ROOT/VERSION";fi
        echo "Settings: App-Connect > Virtual Cockpit settings; stream/layout apply after reconnect"
        exit 0 ;;
    install|uninstall|recover) ;;
    *) fail INVALID_ACTION ;;
esac
regular "$VERIFY" || fail VERIFIER_MISSING
check "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_MU1367_REQUIRED
[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY
mkdir "$LOCK" 2>/dev/null || fail OPERATION_LOCKED
OWN=yes
for K in $KEYS;do
    T=$(target "$K") || fail UNKNOWN_TARGET
    regular "$T" || absent "$T" || fail TARGET_SYMLINK
    D=${T%/*}
    while [ "$D" != "$M" ] && [ "$D" != / ] && [ -n "$D" ];do
        [ -d "$D" ] && [ ! -L "$D" ] || fail TARGET_PARENT_SYMLINK
        D=${D%/*}
    done
    if [ "$ACTION" = recover ];then regular "$T.settings-new" || absent "$T.settings-new" || fail STAGE_SYMLINK;rm -f "$T.settings-new"
    else absent "$T.settings-new" || fail STALE_STAGE_RUN_RECOVER;fi
done
STAGED=yes
if [ "$ACTION" = recover ];then restore || fail RECOVERY_FAILED_KEEP_BACKUPS;exit 0;fi
if [ "$ACTION" = install ];then
    [ "$(cat "$APP/carplay-mu1367/STATE" 2>/dev/null)" = installed ] || fail INSTALL_NATIVE_AUDIO_INTEGRATION_FIRST
    [ "$(cat "$APP/carplay-mu1367/VERSION" 2>/dev/null)" = "$PARENT_BUILD" ] || fail DIFFERENT_PARENT_BUILD
    [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION
    check "$P/guard" "$GUARD_SHA" || fail GUARD_HASH
    for K in $FILES;do N=$(payload "$K");check "$P/$N" "$(expected "$K")" || fail "PAYLOAD_HASH_$K";done
    if regular "$ROOT/STATE";then
        [ "$(cat "$ROOT/STATE")" = installed ] && [ "$(cat "$ROOT/VERSION")" = "$BUILD" ] || fail RECOVERY_RETAINED_ARCHIVE_BEFORE_REINSTALL
        for K in $FILES;do check "$(target "$K")" "$(expected "$K")" || fail INSTALLED_FILE_CHANGED;done
        check "$(target parent)" "$(cat "$ROOT/parent.sha256")" || fail INSTALLED_PARENT_CHANGED
        [ "$(awk '/VCMenu.jar/{n++} END{print n+0}' "$(target boot)")" = 1 ] || fail INSTALLED_BOOT_CHANGED
        echo MU1367_SETTINGS_ALREADY_INSTALLED;exit 0
    fi
    absent "$ROOT" || fail RECOVERY_DIRECTORY_EXISTS
    absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_CARPLAY_AND_REBOOT_FIRST
    for K in $KEYS;do
        T=$(target "$K")
        if [ "$K" = boot ];then :
        else before "$K" "$T" || fail "UNEXPECTED_BASE_$K";fi
    done
    LSD=$(target boot)
    [ "$(awk '/VCMenu.jar|VCMirrorRate.jar|CarPlayNavigationPatch.jar/{n++} END{print n+0}' "$LSD")" = 0 ] || fail REMOVE_OTHER_V2_HMI_FIRST
    [ "$(awk '/^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{n++} END{print n+0}' "$LSD")" = 1 ] || fail UNKNOWN_PREPEND_LAYOUT
    [ "$(awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{n++} END{print n+0}' "$LSD")" = 1 ] || fail UNKNOWN_LAUNCH_LAYOUT
    awk '/^\$J9 .*\$BOOTCLASSPATH .*-jxe/{launch=NR} /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{prepend=NR} END{exit (!prepend || prepend>=launch)}' "$LSD" || fail PREPEND_AFTER_LAUNCH
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    mkdir -p "$ROOT/backup" || fail BACKUP_DIRECTORY
    cp "$0" "$ROOT/control.sh" && cp "$VERIFY" "$ROOT/verify" || fail SAVE_RECOVERY
    VERIFY=$ROOT/verify;chmod 755 "$VERIFY" || fail VERIFIER_MODE
    for K in $KEYS;do
        T=$(target "$K")
        if absent "$T";then : > "$ROOT/backup/$K.absent" || fail BACKUP_ABSENCE
        else cp -p "$T" "$ROOT/backup/$K" && digest "$T" > "$ROOT/backup/$K.sha256" || fail BACKUP_COPY
            check "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || fail BACKUP_VERIFY;fi
    done
    cp "$P/guard" "$ROOT/guard" || fail SAVE_GUARD
    echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_VERSION
    : > "$ROOT/BACKUPS_READY" || fail BACKUPS_READY
    state prepared || fail PREPARED_MARKER
    ROLLBACK=yes
    for K in $FILES;do
        T=$(target "$K");N=$(payload "$K")
        cp "$P/$N" "$T.settings-new" && chmod "$(mode "$K")" "$T.settings-new" || fail STAGE_PAYLOAD
        check "$T.settings-new" "$(expected "$K")" || fail STAGE_HASH
    done
    T=$(target parent)
    cp -p "$T" "$T.settings-new" || fail STAGE_PARENT_MODE
    awk -v guard="$ROOT/guard" '{print} /^set -u$/{while((getline line < guard)>0)print line;close(guard);n++} END{if(n!=1)exit 1}' "$T" > "$ROOT/parent.new" || fail STAGE_PARENT_GUARD
    cat "$ROOT/parent.new" > "$T.settings-new" || fail STAGE_PARENT_CONTENT
    /bin/ksh -n "$T.settings-new" || fail PARENT_SYNTAX
    T=$(target boot);cp -p "$T" "$T.settings-new" || fail STAGE_BOOT_MODE
    awk '/^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/{sub(/-Xbootclasspath\/p:/,"-Xbootclasspath/p:$BASE_DIR/lsd/jars/VCMenu.jar:");n++}{print}END{if(n!=1)exit 1}' "$T" > "$ROOT/boot.new" || fail STAGE_BOOT
    cat "$ROOT/boot.new" > "$T.settings-new" || fail STAGE_BOOT_CONTENT
    /bin/ksh -n "$T.settings-new" || fail BOOT_SYNTAX
    for K in $KEYS;do T=$(target "$K");mv "$T.settings-new" "$T" || fail COMMIT_FILE;done
    digest "$(target parent)" > "$ROOT/parent.sha256" || fail PARENT_COMMIT_HASH
    state installed || fail COMMIT_STATE
    ROLLBACK=no
    echo MU1367_SETTINGS_INSTALLED_REBOOT_REQUIRED
else
    [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail USE_RECOVER_FOR_INTERRUPTED_INSTALL
    for K in $FILES;do check "$(target "$K")" "$(expected "$K")" || fail "FILE_CHANGED_$K";done
    check "$(target parent)" "$(cat "$ROOT/parent.sha256")" || fail PARENT_CHANGED_USE_RECOVER_AFTER_REVIEW
    for K in $KEYS;do
        regular "$ROOT/backup/$K.absent" || check "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || fail BACKUP_CORRUPT
    done
    LSD=$(target boot)
    awk '/VCMenu.jar/{if($0 !~ /^BOOTCLASSPATH="\$BOOTCLASSPATH -Xbootclasspath\/p:/ || ++n>1)exit 1;gsub(/\$BASE_DIR\/lsd\/jars\/VCMenu.jar:/,"");if(index($0,"VCMenu.jar"))exit 2}{print}END{if(n!=1)exit 3}' "$LSD" > "$ROOT/boot.remove" || fail BOOT_CHANGED_USE_RECOVER_AFTER_REVIEW
    /bin/ksh -n "$ROOT/boot.remove" || fail REMOVE_BOOT_SYNTAX
    native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
    # Keep the latest unrelated boot entries on ordinary removal. Snapshot
    # recovery instead restores the complete original boot file.
    for K in $KEYS;do
        T=$(target "$K")
        if [ "$K" = boot ];then cp -p "$T" "$T.settings-new" && cat "$ROOT/boot.remove" > "$T.settings-new" && mv "$T.settings-new" "$T" || fail REMOVE_BOOT
        elif regular "$ROOT/backup/$K.absent";then rm -f "$T" || fail REMOVE_FILE
        else cp -p "$ROOT/backup/$K" "$T.settings-new" && mv "$T.settings-new" "$T" || fail RESTORE_FILE_RUN_SAVED_RECOVER;fi
    done
    state removed || fail REMOVE_STATE
    echo MU1367_SETTINGS_REMOVED_REBOOT_REQUIRED_PREFERENCES_RETAINED
fi
