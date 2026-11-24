#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Opt in to the adapter's existing, phone-addressed A2DP/HFP release request.
# Off by default when no prior preference exists. No live profile changes here.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}/790}
M=${CPMAP_TEST_ROOT:-}
ROOT=$M/mnt/app/carplay-mu1367-profile-790-v166
FLAG=$M/mnt/persist/wcp_btaudio_release
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "CALL_HANDOFF_FAIL=$1";exit 1; }
known(){ absent "$FLAG" || { regular "$FLAG" && { "$P/verify" "$FLAG" @EMPTY_SHA@ || "$P/verify" "$FLAG" @ON_SHA@; }; }; }
cleanup(){
 if [ "$OWN" = yes ];then
  for E in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do absent "$E" || return;done
  rm -rf "$LOCK"
 fi
}
trap cleanup EXIT
for C in cat cp mv rm mkdir chmod mount sync;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
for D in "$ROOT" "$M/mnt/persist" "$M/ramdisk";do
 while [ -n "$D" ] && [ "$D" != / ];do [ -d "$D" ] && [ ! -L "$D" ] || fail UNSAFE_PARENT;D=${D%/*};done
done
regular "$P/verify" && regular "$ROOT/control.sh" && "$P/verify" "$ROOT/control.sh" @CONTROLLER_SHA@ || fail UNKNOWN_PROFILE
[ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail INSTALL_TEST3_FIRST
known || fail UNKNOWN_PREFERENCE_PRESERVED
if [ "$ACTION" = status ];then
 if absent "$FLAG";then echo CALL_HANDOFF_PREFERENCE=keep_bluetooth;else echo CALL_HANDOFF_PREFERENCE=request_carplay;fi
 echo CALL_HANDOFF_ACTUAL_ROUTE=check_call_test_and_diagnostics
 exit 0
fi
case "$ACTION" in on|off) :;;*) fail INVALID_ACTION;;esac
for F in "$M/dev/ipod0" "$M/dev/shmem/wcp_cp_session" "$M/ramdisk/carplay-altstream.ready";do absent "$F" || fail DISCONNECT_AND_FULL_REBOOT_FIRST;done
/bin/ksh "$ROOT/control.sh" install "$P" || fail INSTALLED_FILES_CHANGED
absent "$LOCK" && mkdir "$LOCK" || fail INSTALLER_LOCKED
OWN=yes
known || fail PREFERENCE_CHANGED
if [ -z "$M" ];then mount -uw /mnt/persist || fail PERSIST_REMOUNT;fi
if [ "$ACTION" = on ];then
 NEW=$FLAG.cpmap-call-new-$$
 absent "$NEW" || fail STAGE_EXISTS
 echo 1 > "$NEW" && chmod 644 "$NEW" && "$P/verify" "$NEW" @ON_SHA@ && mv "$NEW" "$FLAG" && sync || fail COMMIT
 echo CALL_HANDOFF_REQUESTED_FOR_NEXT_ACCEPTED_SESSION_FULL_REBOOT_REQUIRED
 echo 'The adapter will ask the OEM phone module to release this CarPlay phone Bluetooth media and phone profiles.'
else
 rm -f "$FLAG" && sync || fail COMMIT
 echo CALL_HANDOFF_DEFAULT_RESTORED_FULL_REBOOT_REQUIRED
fi
