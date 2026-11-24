#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
set -u
ACTION=${1:-status}
P=${2:-}
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then M=/net/mmx;fi
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367-artwork
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
STAGED=no
ROLLBACK=no
BUILD=MU1367-artwork-f353117dbe5c
KEYS='driver audio parent'
FILES='driver audio'
GUARD_SHA=e4facfcc28dc7307728a11882828c5bb126d21c0f6974f8e2605cae9cd12efeb
FETCH_SHA=acbf7f676e3c2690b1ee8c5185c3bbb378962b3a8f9d4dbf56d778cd4813f11e
PARENT_BUILD=MU1367-integration-7262b3242a11
SETTINGS_BUILD=MU1367-settings-v2-2b9533e277a6
LANES_BUILD=MU1367-lanes-ac765ddeb391
RECOVERY_BUILD=MU1367-recovery-a162c85d6365
target(){ case "$1" in
 driver) echo "$APP/armle/lib/dll/ipod-drvr-iap2.so";;
 audio) echo "$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar";;
 parent) echo "$APP/carplay-mu1367-wireless/control.sh";;
 *) return 1;;esac; }
payload(){ case "$1" in
 driver) echo ipod-drvr-iap2.so;;
 audio) echo CarPlayMU1367Audio.jar;;
 *) return 1;;esac; }
expected(){ case "$1" in
 driver) echo 0ca39135a9f2326d9781ae7b010b96ad0355a97562d133d6dec8a1633921ee85;;
 audio) echo c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3;;
 *) return 1;;esac; }
before(){ case "$1" in
 driver) echo 76926bde9bdf1e06fdfe57fd324bbd8772bcb2a98a58ac444b4822e25a331b48;;
 audio) echo fb670fb6c5a824eb656eb69b3e2e9774f2469db6755088078f95f53364f2b3ab;;
 parent) echo b9f2ec61ba7aff5bd8f9a43366543eb62dbfd958711a6cd6a6e5ae130763c123;;
 *) return 1;;esac; }

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
drop_stages(){ for K in $KEYS;do T=$(target "$K");rm -f "$T.artwork-new";done; }
restore(){
 regular "$ROOT/BACKUPS_READY" || return 1
 # Validate the whole snapshot before changing any target.
 for K in $KEYS;do check "$ROOT/backup/$K" "$(cat "$ROOT/backup/$K.sha256")" || return 1;done
 native mount -uw /mnt/app >/dev/null 2>&1 || return 1
 : > "$ROOT/disabled" || return 1
 for K in $KEYS;do
  T=$(target "$K") || return 1
  cp -p "$ROOT/backup/$K" "$T.artwork-new" &&
  check "$T.artwork-new" "$(cat "$ROOT/backup/$K.sha256")" &&
  mv "$T.artwork-new" "$T" || return 1
 done
 state removed || return 1
 echo MU1367_ARTWORK_SNAPSHOT_RESTORED_REBOOT_REQUIRED_PREFERENCES_RETAINED
}
fail(){
 echo "MU1367_ARTWORK_FAIL=$1"
 if [ "$ROLLBACK" = yes ];then ROLLBACK=no;drop_stages;restore || echo MU1367_ARTWORK_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER;fi
 exit 1
}
cleanup(){ if [ "$OWN" = yes ];then [ "$STAGED" = no ] || drop_stages;rm -rf "$LOCK";fi; }
trap cleanup EXIT
trap 'fail INTERRUPTED' HUP INT TERM
for C in ls cat awk cp mv rm mkdir chmod sync;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
[ ! -L "$ROOT" ] && [ ! -L "$ROOT/backup" ] || fail RECOVERY_SYMLINK
case "$ACTION" in
 status)
  if regular "$ROOT/STATE";then cat "$ROOT/STATE";else echo MU1367_ARTWORK_NOT_INSTALLED;fi
  if regular "$ROOT/VERSION";then cat "$ROOT/VERSION";fi
  if regular "$M/ramdisk/carplay-route-guidance/adapter-status.txt";then cat "$M/ramdisk/carplay-route-guidance/adapter-status.txt";fi
  if regular "$M/ramdisk/cpmap-artwork.status";then cat "$M/ramdisk/cpmap-artwork.status";fi
  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"
  exit 0;;
 disable|enable)
  [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail ARTWORK_NOT_INSTALLED
  native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
  if [ "$ACTION" = disable ];then : > "$ROOT/disabled" || fail DISABLE;else rm -f "$ROOT/disabled" || fail ENABLE;fi
  echo MU1367_ARTWORK_SWITCHED_NEXT_WORKER_CYCLE;exit 0;;
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
  regular "$T.artwork-new" || absent "$T.artwork-new" || fail STAGE_SYMLINK
  rm -f "$T.artwork-new" || fail REMOVE_STALE_STAGE
 else absent "$T.artwork-new" || fail STALE_STAGE_RUN_RECOVER;fi
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
 [ "$(cat "$APP/carplay-mu1367-lanes/STATE" 2>/dev/null)" = installed ] && [ "$(cat "$APP/carplay-mu1367-lanes/VERSION" 2>/dev/null)" = "$LANES_BUILD" ] || fail EXACT_LANES_PARENT_REQUIRED
 [ "$(cat "$APP/carplay-mu1367-wireless/STATE" 2>/dev/null)" = installed ] && [ "$(cat "$APP/carplay-mu1367-wireless/VERSION" 2>/dev/null)" = "$RECOVERY_BUILD" ] || fail EXACT_RECOVERY_PARENT_REQUIRED
 check "$APP/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar" be458ca5336b32255bbc3827bdb7e137950fa3efbf3eefff14729085247d7748 || fail UNEXPECTED_PARENT_RUNTIME
 check "$APP/carplaymaps/core.so" eb824f9520c6c03b1295776e3ca3986cccd89c46907eb1dd746b80d6b82360a3 || fail UNEXPECTED_PARENT_RUNTIME
 check "$APP/eso/hmi/lsd/jars/VCMenu.jar" e3a33efc3fa579a6228cbf53908bfd739b0ec9a005e96948c16de94776d93287 || fail UNEXPECTED_PARENT_RUNTIME
 [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION
 check "$P/artwork-fetch" "$FETCH_SHA" || fail FETCH_HASH
 check "$P/guard" "$GUARD_SHA" || fail GUARD_HASH
 for K in $FILES;do check "$P/$(payload "$K")" "$(expected "$K")" || fail "PAYLOAD_HASH_$K";done
 if regular "$ROOT/STATE";then
  check "$ROOT/artwork-fetch" "$FETCH_SHA" || fail INSTALLED_FETCH_CHANGED
  [ "$(cat "$ROOT/STATE")" = installed ] && [ "$(cat "$ROOT/VERSION")" = "$BUILD" ] || fail RECOVERY_RETAINED_ARCHIVE_BEFORE_REINSTALL
  for K in $FILES;do check "$(target "$K")" "$(expected "$K")" || fail "INSTALLED_FILE_CHANGED_$K";done
  for K in parent;do check "$(target "$K")" "$(cat "$ROOT/$K.sha256")" || fail "INSTALLED_GUARD_CHANGED_$K";done
  echo MU1367_ARTWORK_ALREADY_INSTALLED;exit 0
 fi
 absent "$ROOT" || fail RECOVERY_DIRECTORY_EXISTS
 absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_CARPLAY_AND_REBOOT_FIRST
 for K in $KEYS;do check "$(target "$K")" "$(before "$K")" || fail "UNEXPECTED_BASE_$K";done
 native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
 mkdir -p "$ROOT/backup" || fail BACKUP_DIRECTORY
 cp "$0" "$ROOT/control.sh" && cp "$VERIFY" "$ROOT/verify" && chmod 755 "$ROOT/verify" || fail SAVE_RECOVERY
 VERIFY=$ROOT/verify
 cp "$P/artwork-fetch" "$ROOT/artwork-fetch" && chmod 755 "$ROOT/artwork-fetch" && check "$ROOT/artwork-fetch" "$FETCH_SHA" || fail SAVE_FETCH
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
  cp -p "$T" "$T.artwork-new" && cat "$P/$(payload "$K")" > "$T.artwork-new" &&
  check "$T.artwork-new" "$(expected "$K")" || fail STAGE_PAYLOAD
 done
 for K in parent;do
  T=$(target "$K")
  cp -p "$T" "$T.artwork-new" || fail STAGE_GUARD_MODE
  awk -v guard="$ROOT/guard" '{print} /^set -u$/{while((getline line < guard)>0)print line;close(guard);n++} END{if(n!=1)exit 1}' "$T" > "$ROOT/$K.new" || fail STAGE_GUARD
  cat "$ROOT/$K.new" > "$T.artwork-new" && /bin/ksh -n "$T.artwork-new" || fail GUARD_SYNTAX
  digest "$T.artwork-new" > "$ROOT/$K.sha256" || fail GUARD_HASH
 done
 for K in $KEYS;do T=$(target "$K");mv "$T.artwork-new" "$T" || fail COMMIT_FILE;done
 state installed || fail COMMIT_STATE
 ROLLBACK=no
 echo MU1367_ARTWORK_INSTALLED_REBOOT_REQUIRED
else
 [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail USE_RECOVER_FOR_INTERRUPTED_INSTALL
 for K in $FILES;do check "$(target "$K")" "$(expected "$K")" || fail "FILE_CHANGED_$K";done
 for K in parent;do check "$(target "$K")" "$(cat "$ROOT/$K.sha256")" || fail "GUARD_CHANGED_$K";done
 restore || fail RESTORE_FAILED_RUN_SAVED_RECOVER
fi
