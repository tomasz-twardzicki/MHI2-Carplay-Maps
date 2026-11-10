#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# MU1367 v1.5.0-e Android Auto layer: factory gal snapshot, gal wrapper, hook runtime.
# The layer directory keeps the saved controller, the verified factory gal snapshot and the
# copy the wrapper runs (gal.real). It is not one of the OEM reset's archived layers, so the
# wrapper keeps a working factory gal even after an OEM reset archives /mnt/app/carplaymaps.
set -u
ACTION=${1:-status}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then M=/net/mmx;fi
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367-android-auto
AA=$APP/carplaymaps/aa
GAL=$APP/eso/bin/apps/gal
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
ROLLBACK=no
BUILD=mu1367-android-auto-c1f4833dac00
FACTORY_GAL=f84722179cbfb3c0bb92589e0fc58ffcfc3cc0860fabcdf426955e58d900daa0
WRAPPER=ebbefc53004888507dff32770dd2e2a762b3c7895b0c05250b5799e9c7a74034
RUNTIME='libgal_hook.so libdmdt_flush.so aa-most-feeder altscreen-most-bridge-aa gal-hook.conf feeder.conf'
expected(){ case "$1" in
 libgal_hook.so) echo bdd76a85f22319c9750f7c55849b4053d4ce365446559025195673677bc73b05;;
 libdmdt_flush.so) echo 4e3202f0f41b5ad5a96d86ff49adbe574ce550f7b168c9a5f385069ca0e5222f;;
 aa-most-feeder) echo e52e6c1a757905df991133dcd25fc4debd1ab575ccc5b7576be4284c46384370;;
 altscreen-most-bridge-aa) echo feb5c77c766965351ec376e9d3211d67f48e415e849fbbd4558bc233fab51b50;;
 gal-hook.conf) echo 716516eb36b50f7b7230ff36ad8057713ba2b1c97c2fd0b55afe2c8f17559173;;
 feeder.conf) echo ac7157dabd7ae3ec61e8b9c453451b5716154b2b068d552dd96a94a83852e75d;;
 *) return 1;;esac; }
mode(){ case "$1" in
 libgal_hook.so) echo 644;;
 libdmdt_flush.so) echo 644;;
 aa-most-feeder) echo 755;;
 altscreen-most-bridge-aa) echo 755;;
 gal-hook.conf) echo 644;;
 feeder.conf) echo 644;;
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
parents(){
 D=${1%/*}
 while [ "$D" != "$M" ] && [ "$D" != / ] && [ -n "$D" ];do
  [ -d "$D" ] && [ ! -L "$D" ] || return 1
  D=${D%/*}
 done
}
# Removes the runtime this layer created. Only the known names; the directory only when empty.
drop_runtime(){
 for N in $RUNTIME;do
  for F in "$AA/$N" "$AA/$N.aa-new";do
   if [ -L "$F" ] || [ -e "$F" ];then regular "$F" && rm -f "$F" || return 1;fi
  done
 done
 if [ -d "$AA" ] && [ ! -L "$AA" ];then
  # rmdir is not in the firmware inventory: check visible and hidden entries, then rm the empty directory.
  for E in "$AA"/* "$AA"/.[!.]* "$AA"/..?*;do absent "$E" || return 1;done
  rm -rf "$AA" || return 1
 fi
 absent "$AA" || return 1
 for F in "$ROOT/gal.real" "$ROOT/gal.real.aa-new" "$GAL.aa-new";do
  if [ -L "$F" ] || [ -e "$F" ];then regular "$F" && rm -f "$F" || return 1;fi
 done
}
# Puts the verified factory gal back first, then removes the runtime. The snapshot stays.
restore(){
 regular "$ROOT/BACKUPS_READY" || return 1
 check "$ROOT/backup/gal" "$FACTORY_GAL" || return 1
 native mount -uw /mnt/app >/dev/null 2>&1 || return 1
 if ! check "$GAL" "$FACTORY_GAL";then
  rm -f "$GAL.aa-new" &&
  cp -p "$ROOT/backup/gal" "$GAL.aa-new" && check "$GAL.aa-new" "$FACTORY_GAL" &&
  mv "$GAL.aa-new" "$GAL" && check "$GAL" "$FACTORY_GAL" || return 1
 fi
 sync
 drop_runtime || return 1
 state removed || return 1
 echo MU1367_ANDROID_AUTO_REMOVED_FACTORY_GAL_RESTORED_REBOOT_REQUIRED
}
fail(){
 echo "MU1367_ANDROID_AUTO_FAIL=$1"
 if [ "$ROLLBACK" = yes ];then ROLLBACK=no;restore >/dev/null || echo MU1367_ANDROID_AUTO_ROLLBACK_INCOMPLETE_RUN_RECOVER;fi
 exit 1
}
cleanup(){ if [ "$OWN" = yes ];then rm -rf "$LOCK";fi; }
trap cleanup EXIT
trap 'fail INTERRUPTED' HUP INT TERM
runtime_ok(){
 check "$GAL" "$WRAPPER" && check "$ROOT/gal.real" "$FACTORY_GAL" || return 1
 for N in $RUNTIME;do check "$AA/$N" "$(expected "$N")" || return 1;done
}
case "$ACTION" in
 status)
  if regular "$ROOT/STATE";then echo "ANDROID_AUTO_STATE=$(cat "$ROOT/STATE")";else echo MU1367_ANDROID_AUTO_NOT_INSTALLED;fi
  if regular "$ROOT/VERSION";then echo "ANDROID_AUTO_VERSION=$(cat "$ROOT/VERSION")";fi
  if [ -e "$ROOT/DISABLED" ];then echo ANDROID_AUTO_HOOK=disabled;fi
  for F in "$M/ramdisk/carplay-aa-last" "$M/ramdisk/pmcp-aa-rg.txt";do regular "$F" && cat "$F";done
  if regular "$M/ramdisk/pmcp-aa-feeder.txt";then awk 'NR<=12' "$M/ramdisk/pmcp-aa-feeder.txt";fi
  if regular "$M/ramdisk/pmcp-aa-rg/adapter-status.txt";then cat "$M/ramdisk/pmcp-aa-rg/adapter-status.txt";fi
  exit 0;;
 install|uninstall|recover|disable|enable) ;;
 *) fail INVALID_ACTION;;
esac
for C in cat cp mv rm mkdir chmod sync awk;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
regular "$VERIFY" || fail VERIFIER_MISSING
check "$M/ifs/lsd.jxe" 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a || fail EXACT_MU1367_REQUIRED
[ ! -L "$ROOT" ] && [ ! -L "$ROOT/backup" ] && [ ! -L "$AA" ] || fail LAYER_SYMLINK
# carplaymaps may be absent after an OEM reset archived it; when present it must not be a link.
parents "$GAL" && parents "$ROOT" && { absent "$APP/carplaymaps" || parents "$AA"; } || fail TARGET_PARENT_SYMLINK
regular "$GAL" || fail GAL_NOT_REGULAR
mkdir "$LOCK" 2>/dev/null || fail OPERATION_LOCKED
OWN=yes
case "$ACTION" in
 disable|enable)
  [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail NOT_INSTALLED
  native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
  if [ "$ACTION" = disable ];then : > "$ROOT/DISABLED" && sync || fail SAVE_DISABLED
   echo MU1367_ANDROID_AUTO_HOOK_DISABLED_FACTORY_ANDROID_AUTO_FROM_NEXT_CONNECTION
  else rm -f "$ROOT/DISABLED" && sync && absent "$ROOT/DISABLED" || fail REMOVE_DISABLED
   echo MU1367_ANDROID_AUTO_HOOK_ENABLED_FROM_NEXT_CONNECTION
  fi
  exit 0;;
 recover)
  [ -d "$ROOT" ] || { echo MU1367_ANDROID_AUTO_NOT_INSTALLED;exit 0; }
  [ "$(cat "$ROOT/STATE" 2>/dev/null)" != removed ] || { echo MU1367_ANDROID_AUTO_ALREADY_REMOVED;exit 0; }
  if regular "$ROOT/BACKUPS_READY";then restore || fail RECOVERY_FAILED_KEEP_BACKUP;exit 0;fi
  # Interrupted before the snapshot was complete: gal is only written after BACKUPS_READY.
  check "$GAL" "$FACTORY_GAL" || fail UNEXPECTED_GAL_WITHOUT_SNAPSHOT
  native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
  drop_runtime && state removed || fail RECOVERY_CLEANUP
  echo MU1367_ANDROID_AUTO_INCOMPLETE_INSTALL_CLEARED
  exit 0;;
 uninstall)
  [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail USE_RECOVER_FOR_INTERRUPTED_INSTALL
  check "$GAL" "$WRAPPER" || check "$GAL" "$FACTORY_GAL" || fail GAL_CHANGED_BY_SOMETHING_ELSE
  restore || fail RESTORE_FAILED_RUN_RECOVER
  exit 0;;
esac
# install
# Removal stays possible after an OEM reset archived /mnt/app/carplaymaps (and PROFILE with it).
[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY
case "$(cat "$APP/carplay-mu1367-guidance-v3/VERSION" 2>/dev/null)" in
 mu1367-guidance-v3-02dff707ddd2|mu1367-guidance-v3-6f2421b0eced|mu1367-guidance-v3-aed3f0d88907|mu1367-guidance-v3-2231214c28de) ;;
 *) fail EXACT_RELEASE_MAIN_LAYER_REQUIRED;;
esac
[ "$(cat "$APP/carplay-mu1367-guidance-v3/STATE" 2>/dev/null)" = installed ] || fail EXACT_RELEASE_MAIN_LAYER_REQUIRED
regular "$APP/carplaymaps/altscreen-most-bridge" || fail CARPLAY_MAPS_BRIDGE_REQUIRED
[ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION
check "$P/gal.wrapper.sh" "$WRAPPER" || fail PAYLOAD_HASH_wrapper
for N in $RUNTIME;do check "$P/$N" "$(expected "$N")" || fail "PAYLOAD_HASH_$N";done
if regular "$ROOT/STATE";then
 case "$(cat "$ROOT/STATE")" in
  installed)
   case "$(cat "$ROOT/VERSION" 2>/dev/null)" in
    "$BUILD") :;;
    # Earlier Android Auto builds of this release series: back to the factory gal, then install afresh.
    mu1367-android-auto-ee74f406dd94|mu1367-android-auto-e3e4e1ce3a73)
     restore >/dev/null || fail PREVIOUS_ANDROID_AUTO_RESTORE_FAILED_RUN_RECOVER
     echo MU1367_ANDROID_AUTO_PREVIOUS_BUILD_REMOVED_UPGRADING;;
    *) fail OTHER_ANDROID_AUTO_VERSION_UNINSTALL_FIRST;;
   esac
   if [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] && runtime_ok;then echo MU1367_ANDROID_AUTO_ALREADY_INSTALLED;exit 0;fi
   # e.g. after an OEM reset archived /mnt/app/carplaymaps: restore, then install afresh.
   if [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ];then
    restore >/dev/null || fail REPAIR_RESTORE_FAILED_RUN_RECOVER
    echo MU1367_ANDROID_AUTO_INCOMPLETE_RUNTIME_RESTORED_REINSTALLING
   fi;;
  removed) :;;
  *) fail INTERRUPTED_INSTALL_RUN_RECOVER;;
 esac
fi
if [ -d "$ROOT" ];then
 # A removed session is kept, never overwritten: its snapshot is the original factory gal.
 BACK=$ROOT.removed-$$
 absent "$BACK" || fail RETAINED_SESSION_EXISTS
 native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
 mv "$ROOT" "$BACK" && sync || fail RETAIN_REMOVED_SESSION
 VERIFY=$P/verify    # the saved verifier moved with the retained session
 echo "MU1367_ANDROID_AUTO_RETAINED_SESSION=$BACK"
fi
absent "$ROOT" || fail LAYER_DIRECTORY_EXISTS
absent "$AA" || fail ANDROID_AUTO_RUNTIME_DIRECTORY_EXISTS
absent "$GAL.aa-new" || fail STALE_STAGE_RUN_RECOVER
check "$GAL" "$FACTORY_GAL" || fail UNEXPECTED_FACTORY_GAL
native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT
mkdir -p "$ROOT/backup" || fail LAYER_DIRECTORY
cp "$0" "$ROOT/control.sh" && cp "$VERIFY" "$ROOT/verify" && chmod 755 "$ROOT/verify" || fail SAVE_RECOVERY
VERIFY=$ROOT/verify
echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_IDENTITY
state collecting || fail STATE_COLLECTING
cp -p "$GAL" "$ROOT/backup/gal" && digest "$GAL" > "$ROOT/backup/gal.sha256" &&
check "$ROOT/backup/gal" "$FACTORY_GAL" || fail BACKUP_GAL
: > "$ROOT/BACKUPS_READY" && sync || fail BACKUPS_READY
state prepared || fail PREPARED_MARKER
ROLLBACK=yes
cp -p "$ROOT/backup/gal" "$ROOT/gal.real.aa-new" && check "$ROOT/gal.real.aa-new" "$FACTORY_GAL" &&
mv "$ROOT/gal.real.aa-new" "$ROOT/gal.real" || fail STAGE_FACTORY_COPY
mkdir "$AA" || fail RUNTIME_DIRECTORY
for N in $RUNTIME;do
 cp "$P/$N" "$AA/$N.aa-new" && chmod "$(mode "$N")" "$AA/$N.aa-new" &&
 check "$AA/$N.aa-new" "$(expected "$N")" && mv "$AA/$N.aa-new" "$AA/$N" || fail "STAGE_$N"
done
sync
# gal is written last, from a copy of itself so its mode and owner stay factory.
cp -p "$GAL" "$GAL.aa-new" && cat "$P/gal.wrapper.sh" > "$GAL.aa-new" &&
check "$GAL.aa-new" "$WRAPPER" && /bin/ksh -n "$GAL.aa-new" || fail STAGE_WRAPPER
mv "$GAL.aa-new" "$GAL" && sync || fail COMMIT_WRAPPER
runtime_ok || fail POST_INSTALL_VERIFICATION
state installed || fail COMMIT_STATE
ROLLBACK=no
echo MU1367_ANDROID_AUTO_INSTALLED_REBOOT_REQUIRED
