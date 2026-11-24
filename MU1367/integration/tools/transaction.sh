#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-}
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then M=/net/mmx;fi
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367-lanes
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
STAGED=no
ROLLBACK=no
BUILD=@BUILD@
@TABLE@
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
native(){
 if [ -n "${CPMAP_TEST_ROOT:-}" ];then case "$1" in mount) return 0;;esac;"$@"
 elif [ "$M" = /net/mmx ];then C=$1;shift;case "$C" in /net/mmx/*) C=${C#/net/mmx};;esac;on -f mmx "$C" "$@"
 else "$@";fi
}
VERIFY=$ROOT/verify
regular "$VERIFY" || VERIFY=$P/verify
digest(){ F=$1;if [ "$M" = /net/mmx ];then F=${F#/net/mmx};fi;native "$VERIFY" "$F"; }
check(){ regular "$1" || return 1;F=$1;if [ "$M" = /net/mmx ];then F=${F#/net/mmx};fi;native "$VERIFY" "$F" "$2"; }
state(){ echo "$1" > "$ROOT/STATE.new" && mv "$ROOT/STATE.new" "$ROOT/STATE" && sync; }
drop_stages(){ for K in $KEYS;do T=$(target "$K");rm -f "$T.lanes-new";done; }
restore(){
 regular "$ROOT/BACKUPS_READY" || return 1
 # Validate the whole snapshot before changing any target.
 for K in $KEYS;do check "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || return 1;done
 native mount -uw /mnt/app >/dev/null 2>&1 || return 1
 for K in $KEYS;do
  T=$(target "$K") || return 1
  cp -p "$ROOT/backup/$K" "$T.lanes-new" &&
  check "$T.lanes-new" "$(cat "$ROOT/backup/$K.sha256")" &&
  mv "$T.lanes-new" "$T" || return 1
 done
 state removed || return 1
 echo MU1367_LANES_SNAPSHOT_RESTORED_REBOOT_REQUIRED_PREFERENCES_RETAINED
}
fail(){
 echo "MU1367_LANES_FAIL=$1"
 if [ "$ROLLBACK" = yes ];then ROLLBACK=no;drop_stages;restore || echo MU1367_LANES_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER;fi
 exit 1
}
cleanup(){ if [ "$OWN" = yes ];then [ "$STAGED" = no ] || drop_stages;rm -rf "$LOCK";fi; }
trap cleanup EXIT
trap 'fail INTERRUPTED' HUP INT TERM
for C in ls cat awk cp mv rm mkdir chmod sync;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
[ ! -L "$ROOT" ] && [ ! -L "$ROOT/backup" ] || fail RECOVERY_SYMLINK
case "$ACTION" in
 status)
  if regular "$ROOT/STATE";then cat "$ROOT/STATE";else echo MU1367_LANES_NOT_INSTALLED;fi
  if regular "$ROOT/VERSION";then cat "$ROOT/VERSION";fi
  if regular "$M/ramdisk/carplay-route-guidance/adapter-status.txt";then cat "$M/ramdisk/carplay-route-guidance/adapter-status.txt";fi
  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"
  exit 0;;
 install|uninstall|recover) ;;
 *) fail INVALID_ACTION;;
esac
regular "$VERIFY" || fail VERIFIER_MISSING
check "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_MU1367_REQUIRED
[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY
mkdir "$LOCK" 2>/dev/null || fail OPERATION_LOCKED
OWN=yes
for K in $KEYS;do
 T=$(target "$K") || fail UNKNOWN_TARGET
 regular "$T" || fail TARGET_NOT_REGULAR
 D=${T%/*}
 while [ "$D" != "$M" ] && [ "$D" != / ] && [ -n "$D" ];do
  [ -d "$D" ] && [ ! -L "$D" ] || fail TARGET_PARENT_SYMLINK
  D=${D%/*}
 done
 if [ "$ACTION" = recover ];then
  regular "$T.lanes-new" || absent "$T.lanes-new" || fail STAGE_SYMLINK
  rm -f "$T.lanes-new" || fail REMOVE_STALE_STAGE
 else absent "$T.lanes-new" || fail STALE_STAGE_RUN_RECOVER;fi
done
STAGED=yes
if [ "$ACTION" = recover ];then
 [ "$(cat "$ROOT/STATE" 2>/dev/null)" != removed ] || fail ALREADY_REMOVED
 restore || fail RECOVERY_FAILED_KEEP_BACKUPS
 exit 0
fi
if [ "$ACTION" = install ];then
 [ "$(cat "$APP/carplay-mu1367/STATE" 2>/dev/null)" = installed ] &&
 [ "$(cat "$APP/carplay-mu1367/VERSION" 2>/dev/null)" = "$PARENT_BUILD" ] || fail EXACT_NATIVE_PARENT_REQUIRED
 [ "$(cat "$APP/carplay-mu1367-settings/STATE" 2>/dev/null)" = installed ] &&
 [ "$(cat "$APP/carplay-mu1367-settings/VERSION" 2>/dev/null)" = "$SETTINGS_BUILD" ] || fail EXACT_V130_SETTINGS_REQUIRED
 [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION
 check "$P/guard" "$GUARD_SHA" || fail GUARD_HASH
 for K in $FILES;do check "$P/$(payload "$K")" "$(expected "$K")" || fail "PAYLOAD_HASH_$K";done
 if regular "$ROOT/STATE";then
  [ "$(cat "$ROOT/STATE")" = installed ] && [ "$(cat "$ROOT/VERSION")" = "$BUILD" ] || fail RECOVERY_RETAINED_ARCHIVE_BEFORE_REINSTALL
  for K in $FILES;do check "$(target "$K")" "$(expected "$K")" || fail "INSTALLED_FILE_CHANGED_$K";done
  for K in parent settings;do check "$(target "$K")" "$(cat "$ROOT/$K.sha256")" || fail "INSTALLED_GUARD_CHANGED_$K";done
  echo MU1367_LANES_ALREADY_INSTALLED;exit 0
 fi
 absent "$ROOT" || fail RECOVERY_DIRECTORY_EXISTS
 absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_CARPLAY_AND_REBOOT_FIRST
 for K in $KEYS;do check "$(target "$K")" "$(before "$K")" || fail "UNEXPECTED_BASE_$K";done
 native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
 mkdir -p "$ROOT/backup" || fail BACKUP_DIRECTORY
 cp "$0" "$ROOT/control.sh" && cp "$VERIFY" "$ROOT/verify" && chmod 755 "$ROOT/verify" || fail SAVE_RECOVERY
 VERIFY=$ROOT/verify
 for K in $KEYS;do
  T=$(target "$K")
  cp -p "$T" "$ROOT/backup/$K" && digest "$T" > "$ROOT/backup/$K.sha256" &&
  check "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || fail "BACKUP_$K"
 done
 cp "$P/guard" "$ROOT/guard" && echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_IDENTITY
 : > "$ROOT/BACKUPS_READY" || fail BACKUPS_READY
 state prepared || fail PREPARED_MARKER
 ROLLBACK=yes
 for K in $FILES;do
  T=$(target "$K")
  cp -p "$T" "$T.lanes-new" && cat "$P/$(payload "$K")" > "$T.lanes-new" &&
  check "$T.lanes-new" "$(expected "$K")" || fail STAGE_PAYLOAD
 done
 for K in parent settings;do
  T=$(target "$K")
  cp -p "$T" "$T.lanes-new" || fail STAGE_GUARD_MODE
  awk -v guard="$ROOT/guard" '{print} /^set -u$/{while((getline line < guard)>0)print line;close(guard);n++} END{if(n!=1)exit 1}' "$T" > "$ROOT/$K.new" || fail STAGE_GUARD
  cat "$ROOT/$K.new" > "$T.lanes-new" && /bin/ksh -n "$T.lanes-new" || fail GUARD_SYNTAX
  digest "$T.lanes-new" > "$ROOT/$K.sha256" || fail GUARD_HASH
 done
 for K in $KEYS;do T=$(target "$K");mv "$T.lanes-new" "$T" || fail COMMIT_FILE;done
 state installed || fail COMMIT_STATE
 ROLLBACK=no
 echo MU1367_LANES_INSTALLED_REBOOT_REQUIRED
else
 [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail USE_RECOVER_FOR_INTERRUPTED_INSTALL
 for K in $FILES;do check "$(target "$K")" "$(expected "$K")" || fail "FILE_CHANGED_$K";done
 for K in parent settings;do check "$(target "$K")" "$(cat "$ROOT/$K.sha256")" || fail "GUARD_CHANGED_$K";done
 restore || fail RESTORE_FAILED_RUN_SAVED_RECOVER
fi
