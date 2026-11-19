#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Checked additive wireless layer for the pinned v1.5.4 baseline.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367-wireless-native-v161t2
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
WRITING=no
BUILD=@BUILD@
@TABLE@
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
parents(){
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ ! -L "$D" ] || return 1
  if [ -e "$D" ];then [ -d "$D" ] || return 1;fi
  D=${D%/*}
 done
}
VERIFY=$P/verify
if regular "$ROOT/verify";then VERIFY=$ROOT/verify;fi
digest(){ "$VERIFY" "$1"; }
check(){ regular "$1" && "$VERIFY" "$1" "$2"; }
load_index(){
 # Validate keys and values before using shell variables. No metadata is code.
 PREFIX=$1
 for IK in $KEYS;do eval "${PREFIX}${IK}=";done
 while read IK IV EXTRA;do
  case " $KEYS " in *" $IK "*) ;; *) return 1;;esac
  [ -z "$EXTRA" ] || return 1
  if [ "$IV" != MISSING ];then
   [ "${#IV}" = 64 ] || return 1
   case "$IV" in *[!0123456789abcdef]*) return 1;;esac
  fi
  eval "HAVE=\${${PREFIX}${IK}:-}"
  [ -z "$HAVE" ] || return 1
  eval "${PREFIX}${IK}=$IV"
 done < "$2"
 for IK in $KEYS;do eval "HAVE=\${${PREFIX}${IK}:-}";[ -n "$HAVE" ] || return 1;done
}
original(){ eval "echo \${B_$1:-INVALID}"; }
receipt(){ eval "echo \${I_$1:-INVALID}"; }
state(){ echo "$1" > "$ROOT/STATE.new" && mv "$ROOT/STATE.new" "$ROOT/STATE" && sync; }
native_mount(){ if [ -z "${CPMAP_TEST_ROOT:-}" ];then mount -uw "$1";fi; }
mounts(){ for FS in /mnt/app /mnt/system /mnt/ota /mnt/persist;do native_mount "$FS" || return 1;done; }
drop_stages(){
 for K in $KEYS;do
  T=$(target "$K") || return 1
  parents "$T" && { regular "$T.wcpn-new" || absent "$T.wcpn-new"; } || return 1
  rm -f "$T.wcpn-new" || return 1
 done
}
snapshot_ok(){
 regular "$ROOT/BACKUPS_READY" && regular "$ROOT/backup.index.sha256" || return 1
 check "$ROOT/backup.index" "$(cat "$ROOT/backup.index.sha256")" || return 1
 load_index B_ "$ROOT/backup.index" || return 1
 for K in $KEYS;do
  H=$(original "$K") || return 1
  case "$H" in
   MISSING) absent "$ROOT/backup/$K" || return 1;;
   *) [ "${#H}" = 64 ] && check "$ROOT/backup/$K" "$H" || return 1;;
  esac
 done
}
targets_match(){
 INDEX=$1
 if [ "$INDEX" = installed ];then
  regular "$ROOT/installed.index.sha256" && check "$ROOT/installed.index" "$(cat "$ROOT/installed.index.sha256")" || return 1
  load_index I_ "$ROOT/installed.index" || return 1
 fi
 for K in $KEYS;do
  T=$(target "$K") || return 1
  parents "$T" || return 1
  if [ "$INDEX" = original ];then H=$(original "$K") || return 1
  else H=$(receipt "$K") || return 1;fi
  if [ "$H" = MISSING ];then absent "$T" || return 1
  else check "$T" "$H" || return 1;fi
 done
}
restore(){
 snapshot_ok && mounts || return 1
 for K in $REVERSE_KEYS;do
  T=$(target "$K") && H=$(original "$K") && parents "$T" || return 1
  regular "$T" || absent "$T" || return 1
  if [ "$H" = MISSING ];then rm -f "$T" || return 1
  else
   cp -p "$ROOT/backup/$K" "$T.wcpn-new" && check "$T.wcpn-new" "$H" &&
    mv "$T.wcpn-new" "$T" || return 1
  fi
 done
 drop_stages && targets_match original && state removed || return 1
 echo MU1367_WIRELESS_SNAPSHOT_RESTORED_FULL_REBOOT_REQUIRED
}
fail(){
 echo "MU1367_WIRELESS_FAIL=$1"
 if [ "$WRITING" = yes ];then
  WRITING=no
  restore || echo MU1367_WIRELESS_ROLLBACK_INCOMPLETE_RUN_SAVED_RECOVER
 fi
 exit 1
}
cleanup(){
 if [ "$OWN" = yes ];then
  for ENTRY in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$ENTRY" || return;done
  rm -rf "$LOCK" || :
 fi
}
trap cleanup EXIT
trap 'fail INTERRUPTED_KEEP_SNAPSHOT' HUP INT TERM
for C in cat cp mv rm mkdir chmod sync mount ls awk grep;do
 command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C"
done
parents "$ROOT" && [ ! -L "$ROOT" ] && [ ! -L "$ROOT/backup" ] && [ ! -L "$ROOT/stage" ] || fail UNSAFE_RECOVERY_DIRECTORY
case "$ACTION" in
 status)
  if regular "$ROOT/STATE";then echo "WIRELESS_STATE=$(cat "$ROOT/STATE")";else echo WIRELESS_STATE=absent;fi
  if regular "$ROOT/VERSION";then cat "$ROOT/VERSION";fi
  if regular "$M/mnt/persist/btwcp_off";then echo WIRELESS_SWITCH=off;else echo WIRELESS_SWITCH=on_if_installed;fi
  echo 'Wireless native guidance is enabled; media text/artwork are not integrated.'
  exit 0;;
 install|uninstall|recover) ;;
 *) fail INVALID_ACTION;;
esac
regular "$VERIFY" || fail VERIFIER_MISSING
check "$M/ifs/lsd.jxe" "$JXE_SHA" || fail EXACT_MU1367_FIRMWARE_REQUIRED
[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY
absent "$M/ramdisk/carplay-altstream.ready" && absent "$M/dev/shmem/wcp_cp_session" && absent "$M/dev/ipod0" || fail DISCONNECT_PHONES_AND_REBOOT_FIRST
for K in $KEYS;do
 T=$(target "$K") || fail UNKNOWN_TARGET
 parents "$T" && { regular "$T" || absent "$T"; } || fail TARGET_SYMLINK_OR_TYPE
 regular "$T.wcpn-new" || absent "$T.wcpn-new" || fail STAGE_SYMLINK_OR_TYPE
done
parents "$LOCK" && absent "$LOCK" || fail INSTALLER_LOCKED_REBOOT_DISCONNECTED
mkdir "$LOCK" || fail LOCK_FAILED
OWN=yes
if [ "$ACTION" != install ];then
 [ "$(cat "$ROOT/VERSION" 2>/dev/null)" = "$BUILD" ] || fail WRONG_OR_MISSING_RECOVERY_BUILD
 snapshot_ok || fail SNAPSHOT_CORRUPT_NO_FILES_CHANGED
 regular "$ROOT/installed.index.sha256" && check "$ROOT/installed.index" "$(cat "$ROOT/installed.index.sha256")" || fail INSTALLED_RECEIPT_CORRUPT
 load_index I_ "$ROOT/installed.index" || fail INSTALLED_RECEIPT_INVALID
 if [ "$ACTION" = uninstall ];then
  [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] && targets_match installed || fail INSTALLED_FILES_CHANGED_USE_RECOVER
 fi
 # A recovery may see a mix of before/after files, never an unknown third-party edit.
 for K in $KEYS;do
  T=$(target "$K");H=$(original "$K") || fail SNAPSHOT_RECORD
  NEW=$(receipt "$K") || fail INSTALLED_RECEIPT
  if [ "$H" = MISSING ] && absent "$T";then :
  elif [ "$H" != MISSING ] && check "$T" "$H";then :
  elif [ "$NEW" = MISSING ] && absent "$T";then :
  elif [ "$NEW" != MISSING ] && check "$T" "$NEW";then :
  else fail UNKNOWN_CHANGED_TARGET_PRESERVED;fi
 done
 restore || fail RESTORE_INCOMPLETE_RETRY_SAVED_RECOVER
 exit 0
fi
[ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail WRONG_SD_BUILD
. "$P/payload-check.sh" || fail SD_PAYLOAD_HASH
if regular "$ROOT/STATE";then
 [ "$(cat "$ROOT/VERSION")" = "$BUILD" ] && snapshot_ok || fail KEEP_DIFFERENT_OR_DAMAGED_RECOVERY
 case "$(cat "$ROOT/STATE")" in
  installed) targets_match installed || fail INSTALLED_FILES_CHANGED;echo MU1367_WIRELESS_ALREADY_INSTALLED;exit 0;;
  removed|prepared) targets_match original || fail PREVIOUS_BASELINE_CHANGED;;
  *) fail INTERRUPTED_INSTALL_RUN_SAVED_RECOVER;;
 esac
else absent "$ROOT" || fail UNKNOWN_RECOVERY_DIRECTORY;fi
if regular "$APP/carplay-mu1367-wireless-native/STATE";then
 [ "$(cat "$APP/carplay-mu1367-wireless-native/STATE")" = removed ] || fail REMOVE_TEST1_AND_REBOOT_FIRST
fi
if regular "$APP/carplay-mu1367-wireless-native-v161/STATE";then
 [ "$(cat "$APP/carplay-mu1367-wireless-native-v161/STATE")" = removed ] || fail REMOVE_V161_AND_REBOOT_FIRST
fi
baseline_ok || fail EXACT_V154_BASELINE_REQUIRED
for K in $KEYS;do
 T=$(target "$K");before_ok "$K" "$T" || fail "UNEXPECTED_PREIMAGE_$K"
done
mounts || fail PARTITION_REMOUNT
if absent "$ROOT";then
 mkdir -p "$ROOT/backup" || fail CREATE_RECOVERY
 cp "$P/control.sh" "$ROOT/control.sh" && cp "$P/verify" "$ROOT/verify" &&
  chmod 755 "$ROOT/control.sh" "$ROOT/verify" || fail SAVE_RECOVERY
 VERIFY=$ROOT/verify
 echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_VERSION
 : > "$ROOT/backup.index" || fail SNAPSHOT_INDEX
 for K in $KEYS;do
  T=$(target "$K")
  if absent "$T";then H=MISSING
  else
   H=$(digest "$T") && cp -p "$T" "$ROOT/backup/$K" && check "$ROOT/backup/$K" "$H" || fail SNAPSHOT_COPY
  fi
  echo "$K $H" >> "$ROOT/backup.index" || fail SNAPSHOT_INDEX
 done
 digest "$ROOT/backup.index" > "$ROOT/backup.index.sha256" && : > "$ROOT/BACKUPS_READY" || fail SNAPSHOT_SEAL
 state prepared || fail PREPARE_TRANSACTION
fi
snapshot_ok && targets_match original || fail BASELINE_CHANGED_DURING_STAGING
if [ -d "$ROOT/stage" ];then rm -rf "$ROOT/stage" || fail OLD_STAGE;fi
mkdir "$ROOT/stage" || fail CREATE_STAGE
for K in $KEYS;do stage_payload "$K" "$ROOT/stage/$K" || fail "GENERATE_$K";done
: > "$ROOT/installed.index" || fail RECEIPT
for K in $KEYS;do
 if regular "$ROOT/stage/$K";then H=$(digest "$ROOT/stage/$K") || fail STAGE_HASH
 else H=MISSING;fi
 echo "$K $H" >> "$ROOT/installed.index" || fail RECEIPT
done
digest "$ROOT/installed.index" > "$ROOT/installed.index.sha256" || fail RECEIPT_SEAL
load_index I_ "$ROOT/installed.index" || fail RECEIPT_INVALID
state installing || fail START_TRANSACTION
WRITING=yes
for K in $KEYS;do
 T=$(target "$K");parents "$T" || fail TARGET_PARENT_CHANGED
 H=$(original "$K") || fail SNAPSHOT_RECORD
 if [ "$H" = MISSING ];then absent "$T" || fail PREIMAGE_CHANGED
 else check "$T" "$H" || fail PREIMAGE_CHANGED;fi
 if regular "$ROOT/stage/$K";then
  mkdir -p "${T%/*}" || fail TARGET_DIRECTORY
  if regular "$T";then
   cp -p "$T" "$T.wcpn-new" && cat "$ROOT/stage/$K" > "$T.wcpn-new" || fail STAGE_WRITE
  else cp "$ROOT/stage/$K" "$T.wcpn-new" && chmod "$(mode "$K")" "$T.wcpn-new" || fail STAGE_WRITE;fi
  check "$T.wcpn-new" "$(receipt "$K")" && mv "$T.wcpn-new" "$T" || fail COMMIT_FILE
 else rm -f "$T" || fail COMMIT_ABSENCE;fi
 # Fault injection is available only in an explicitly isolated filesystem fixture.
 if [ -n "${CPMAP_TEST_ROOT:-}" ];then
  [ "${CPMAP_TEST_FAIL_AFTER_KEY:-}" != "$K" ] || fail INJECTED_COMMIT_FAILURE
  if [ "${CPMAP_TEST_INTERRUPT_AFTER_KEY:-}" = "$K" ];then WRITING=no;echo SIMULATED_POWER_INTERRUPTION;exit 99;fi
 fi
done
targets_match installed || fail READBACK
state installed || fail COMPLETE_TRANSACTION
WRITING=no
echo MU1367_WIRELESS_V160E_TEST1_INSTALLED_FULL_REBOOT_REQUIRED
