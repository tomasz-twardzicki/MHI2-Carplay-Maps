#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Standalone forward recovery. Never invoke a layer's old controller.
set -u
ACTION=${1:-inspect}
P=${2:-${0%/*}}
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
ROOT=$APP/carplay-mu1367-oem-reset
LOCK=$M/ramdisk/.carplay-guidance-install-lock
OWN=no
REQUIRED_TOOLS='cat cp mv rm mkdir chmod sync mount'
BUILD=MU1367-oem-reset-4000ba50437c
JXE_SHA=09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a
KEYS='boot driver config dio guidance audio navignore menu controls generic_navignore'
OEM_KEYS='boot driver config dio'
REMOVE_KEYS='guidance audio navignore menu controls generic_navignore'
LAYERS='carplaymaps carplay-mu1367 carplay-mu1367-settings carplay-mu1367-lanes carplay-mu1367-wireless carplay-mu1367-artwork carplay-mu1367-card-scene carplay-mu1367-road-name carplay-mu1367-refinements carplay-mu1367-map-only carplay-mu1367-turn-cards carplay-mu1367-guidance-v3'
OLD_SUFFIXES='mu1367-new settings-new lanes-new wireless-new artwork-new card-scene-new road-name-new refinements-new map-only-new turn-cards-new guidance-v3-new cpmap-new restore new'
target(){ case "$1" in
 boot) echo "$M/mnt/app/eso/hmi/lsd/lsd.sh";;
 driver) echo "$M/mnt/app/armle/lib/dll/ipod-drvr-iap2.so";;
 config) echo "$M/mnt/system/etc/mm/iap2.cfg";;
 dio) echo "$M/mnt/app/eso/bin/apps/dio_manager";;
 guidance) echo "$M/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar";;
 audio) echo "$M/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar";;
 navignore) echo "$M/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367NavIgnore.jar";;
 menu) echo "$M/mnt/app/eso/hmi/lsd/jars/VCMenu.jar";;
 controls) echo "$M/mnt/app/eso/hmi/lsd/jars/CarPlayClusterControls.jar";;
 generic_navignore) echo "$M/mnt/app/eso/hmi/lsd/jars/NavActiveIgnore.jar";;
 *) return 1;;esac; }
expected(){ case "$1" in
 boot) echo fe4f9cc8bd68282238546605c53b36ca0add985eafc8a100a477a7f827f4a731;;
 driver) echo 7149a3e75b1b19e89021841759f420a6eced456b6c697a3dd1f0e436abea0b8c;;
 config) echo 88a4d24f5c50b181d73429fb585ad6b38d10daca67c5b5a9798ef17f84208bbe;;
 dio) echo ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae;;
 *) return 1;;esac; }
mode(){ case "$1" in
 boot) echo 755;;
 driver) echo 755;;
 config) echo 644;;
 dio) echo 755;;
 *) return 1;;esac; }

regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){
 echo "MU1367_OEM_RESET_FAIL=$1"
 echo 'Keep the SD and backups. Correct the reported error and run restore again; do not run old layer controllers.'
 exit 1
}
cleanup(){
 if [ "$OWN" = yes ] && [ -d "$LOCK" ] && [ ! -L "$LOCK" ];then
  # Use the existing rm command only after checking visible and hidden entries.
  # Preserve any unexpected lock contents rather than deleting them recursively.
  for ENTRY in "$LOCK"/* "$LOCK"/.[!.]* "$LOCK"/..?*;do
   absent "$ENTRY" || { echo MU1367_OEM_RESET_LOCK_RETAINED_NONEMPTY;return; }
  done
  rm -rf "$LOCK" 2>/dev/null || :
 fi
}
trap cleanup EXIT
trap 'fail INTERRUPTED_RESUME_RESTORE' HUP INT TERM
parents(){
 case "$1" in /*) ;; *) return 1;;esac
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ -d "$D" ] && [ ! -L "$D" ] || return 1
  D=${D%/*}
 done
}
safe_file(){ parents "$1" && { regular "$1" || absent "$1"; }; }
safe_dir(){ parents "$1" && { { [ -d "$1" ] && [ ! -L "$1" ]; } || absent "$1"; }; }
VERIFY=$P/verify
check(){ regular "$1" && "$VERIFY" "$1" "$2"; }
digest(){ regular "$1" && "$VERIFY" "$1"; }
check_tools(){
 MISSING=no
 for C in $REQUIRED_TOOLS;do
  if command -v "$C" >/dev/null 2>&1;then
   echo "MU1367_OEM_RESET_TOOL=$C PATH=$(command -v "$C")"
  else echo "MU1367_OEM_RESET_TOOL_MISSING=$C";MISSING=yes;fi
 done
 for C in df slay;do
  if command -v "$C" >/dev/null 2>&1;then echo "MU1367_OEM_RESET_OPTIONAL_TOOL=$C PATH=$(command -v "$C")"
  else echo "MU1367_OEM_RESET_OPTIONAL_TOOL_UNAVAILABLE=$C";fi
 done
 [ "$MISSING" = no ]
}
state(){ echo "$1" > "$ROOT/STATE.new" && mv "$ROOT/STATE.new" "$ROOT/STATE" && sync; }
payload_ok(){
 for K in $OEM_KEYS;do check "$P/payload/$K" "$(expected "$K")" || return 1;done
 /bin/ksh -n "$P/payload/boot" || return 1
}
snapshot_ok(){
 regular "$ROOT/BACKUPS_READY" || return 1
 for K in $KEYS;do
  if regular "$ROOT/pre-reset/$K.absent";then
   absent "$ROOT/pre-reset/$K" && absent "$ROOT/pre-reset/$K.sha256" || return 1
  else
   regular "$ROOT/pre-reset/$K.sha256" && check "$ROOT/pre-reset/$K" "$(cat "$ROOT/pre-reset/$K.sha256")" || return 1
  fi
 done
}
oem_files_ok(){
 for K in $OEM_KEYS;do check "$(target "$K")" "$(expected "$K")" || return 1;done
 for K in $REMOVE_KEYS;do absent "$(target "$K")" || return 1;done
}
archive_preflight(){
 for N in $LAYERS;do
  safe_dir "$APP/$N" || return 1
  if [ -d "$ROOT/archive" ];then
   safe_dir "$ROOT/archive/$N" || return 1
   # A rename interrupted by power loss leaves precisely one of these names.
   if [ -d "$APP/$N" ] && [ -d "$ROOT/archive/$N" ];then return 1;fi
  fi
 done
}
case "$ACTION" in inspect|restore|verify|check-tools) ;; *) fail INVALID_ACTION;;esac
if [ -z "$M" ] && { [ ! -s /ifs/lsd.jxe ] || [ ! -d /mnt/app ]; };then
 fail RUN_ON_MMX_USE_THE_BUNDLED_RUN_SCRIPT
fi
if [ "$ACTION" = check-tools ];then
 check_tools || fail REQUIRED_COMMAND_UNAVAILABLE_NO_FILES_CHANGED
 echo MU1367_OEM_RESET_REQUIRED_TOOLS_AVAILABLE_NO_FILES_CHANGED
 exit 0
fi
# Do not make inspection/verification depend on unused write commands.
command -v cat >/dev/null 2>&1 || fail MISSING_cat
if [ "$ACTION" = restore ];then
 for C in $REQUIRED_TOOLS;do command -v "$C" >/dev/null 2>&1 || fail "MISSING_$C";done
fi
safe_dir "$P" && regular "$VERIFY" || fail UNSAFE_PAYLOAD_OR_VERIFIER_MISSING
parents "$M/ifs/lsd.jxe" || fail UNSAFE_IFS_PATH
check "$M/ifs/lsd.jxe" "$JXE_SHA" || fail EXACT_K4525_MU1367_REQUIRED
safe_dir "$ROOT" || fail UNSAFE_RECOVERY_DIRECTORY
for K in $KEYS;do safe_file "$(target "$K")" || fail "UNSAFE_TARGET_$K";done
for N in $LAYERS;do safe_dir "$APP/$N" || fail "UNSAFE_LAYER_$N";done
if [ "$ACTION" = inspect ];then
 echo "MU1367_OEM_RESET_INSPECT=$BUILD"
 for K in $KEYS;do
  T=$(target "$K")
  if regular "$T";then echo "FILE=$K SHA256=$(digest "$T")";else echo "FILE=$K ABSENT";fi
 done
 for N in $LAYERS;do
  if regular "$APP/$N/STATE";then echo "LAYER=$N STATE=$(cat "$APP/$N/STATE")"
  elif [ -d "$APP/$N" ];then echo "LAYER=$N PRESENT_NO_STATE";else echo "LAYER=$N ABSENT";fi
 done
 if regular "$ROOT/STATE";then echo "RESET_STATE=$(cat "$ROOT/STATE")";fi
 check_tools || :
 if command -v mount >/dev/null 2>&1;then mount;fi
 if command -v df >/dev/null 2>&1;then df -k "$APP" "$M/mnt/system" "$M/ramdisk" 2>/dev/null || :;fi
 echo MU1367_OEM_RESET_INSPECTION_ONLY_NO_FILES_CHANGED
 exit 0
fi
if [ "$ACTION" = verify ];then
 oem_files_ok || fail OEM_FILE_VERIFICATION
 for N in $LAYERS;do absent "$APP/$N" || fail "LAYER_STILL_PRESENT_$N";done
 echo MU1367_OEM_RESET_VERIFIED_REBOOT_IF_NOT_ALREADY_DONE
 exit 0
fi
payload_ok || fail OEM_PAYLOAD_CORRUPT
absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST
safe_dir "$LOCK" && mkdir "$LOCK" 2>/dev/null || fail OPERATION_LOCKED_REBOOT_DISCONNECTED_AND_RETRY
OWN=yes
for D in "$ROOT/payload" "$ROOT/pre-reset" "$ROOT/archive" "$ROOT/stale-files";do
 if [ -d "$ROOT" ];then safe_dir "$D" || fail UNSAFE_SAVED_DIRECTORY;fi
done
if [ -d "$ROOT" ];then
 for N in STATE STATE.new VERSION control.sh verify BACKUPS_READY;do safe_file "$ROOT/$N" || fail UNSAFE_RECOVERY_FILE;done
 [ "$(cat "$ROOT/VERSION" 2>/dev/null)" = "$BUILD" ] || fail DIFFERENT_OR_INCOMPLETE_RESET_KEEP_DIRECTORY
 case "$(cat "$ROOT/STATE" 2>/dev/null)" in
  ''|collecting) ;;
  *) regular "$ROOT/BACKUPS_READY" || fail SAVED_SNAPSHOT_MARKER_MISSING_DO_NOT_RECOLLECT;;
 esac
 if [ "$(cat "$ROOT/STATE" 2>/dev/null)" = complete ];then
  oem_files_ok || fail OEM_CHANGED_AFTER_RESET_DO_NOT_OVERWRITE_NEW_INSTALL
  for N in $LAYERS;do absent "$APP/$N" || fail NEW_INSTALLATION_PRESENT_DO_NOT_OVERWRITE;done
  echo MU1367_OEM_RESET_ALREADY_COMPLETE_REBOOT_IF_NEEDED
  exit 0
 fi
fi
archive_preflight || fail ARCHIVE_PATH_CONFLICT_PRESERVE_BOTH
# Validate staging paths before remounting or changing any persistent file.
for K in $KEYS;do
 T=$(target "$K")
 safe_file "$T.oem-reset-new" || fail STAGE_SYMLINK
 if ! regular "$ROOT/BACKUPS_READY";then absent "$T.oem-reset-new" || fail UNOWNED_RESET_STAGE;fi
 for S in $OLD_SUFFIXES;do
  safe_file "$T.$S" || fail UNSAFE_OLD_STAGE
  if [ -d "$ROOT/stale-files" ];then
   safe_file "$ROOT/stale-files/$K.$S" || fail UNSAFE_ARCHIVED_STAGE
   if regular "$T.$S" && regular "$ROOT/stale-files/$K.$S";then fail OLD_STAGE_ARCHIVE_CONFLICT;fi
  fi
 done
done
if regular "$ROOT/BACKUPS_READY";then snapshot_ok || fail SAVED_SNAPSHOT_CORRUPT_NO_TARGETS_CHANGED;fi
# Remount BEFORE snapshot, boot.remove, STATE or staging writes; old uninstall
# paths could write into /mnt/app while Toolbox had already remounted it RO.
mount -uw /mnt/app || fail APP_REMOUNT_FAILED_NO_TARGETS_CHANGED
mount -uw /mnt/system || fail SYSTEM_REMOUNT_FAILED_NO_TARGETS_CHANGED
for D in "$APP" "$M/mnt/system/etc/mm";do
 PROBE=$D/.mu1367-oem-write-test-$$
 absent "$PROBE" || fail WRITE_PROBE_EXISTS
 (umask 077;set -C;: > "$PROBE") && rm "$PROBE" || fail FILESYSTEM_STILL_READONLY_OR_FULL
done
if absent "$ROOT";then
 mkdir "$ROOT" || fail CREATE_RECOVERY
 # VERSION is written first so interrupted preparation can safely resume.
 echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_VERSION
fi
mkdir -p "$ROOT/payload" "$ROOT/pre-reset" "$ROOT/archive" "$ROOT/stale-files" || fail CREATE_SNAPSHOT_DIRS
# Refuse links inside the saved area before copying anything into it.
for K in $OEM_KEYS;do safe_file "$ROOT/payload/$K" || fail UNSAFE_SAVED_PAYLOAD;done
for K in $KEYS;do
 for N in "$K" "$K.sha256" "$K.absent";do safe_file "$ROOT/pre-reset/$N" || fail UNSAFE_SNAPSHOT_FILE;done
done
if ! regular "$ROOT/BACKUPS_READY";then
 state collecting || fail SAVE_COLLECTING
 for K in $KEYS;do
  T=$(target "$K")
  rm -f "$ROOT/pre-reset/$K" "$ROOT/pre-reset/$K.sha256" "$ROOT/pre-reset/$K.absent" || fail CLEAR_INCOMPLETE_SNAPSHOT
  if absent "$T";then : > "$ROOT/pre-reset/$K.absent" || fail SAVE_ABSENCE
  else
   cp -p "$T" "$ROOT/pre-reset/$K" && digest "$T" > "$ROOT/pre-reset/$K.sha256" &&
   check "$ROOT/pre-reset/$K" "$(cat "$ROOT/pre-reset/$K.sha256")" || fail SAVE_SNAPSHOT
  fi
 done
 # Copy only when running from SD, never truncate a saved script onto itself.
 if [ "$P" != "$ROOT" ];then
  cp "$P/control.sh" "$ROOT/control.sh" && cp "$VERIFY" "$ROOT/verify" && chmod 755 "$ROOT/verify" "$ROOT/control.sh" || fail SAVE_CONTROLLER
 fi
 for K in $OEM_KEYS;do
  if [ "$P" != "$ROOT" ];then cp "$P/payload/$K" "$ROOT/payload/$K" || fail SAVE_OEM_PAYLOAD;fi
  check "$ROOT/payload/$K" "$(expected "$K")" || fail SAVE_OEM_VERIFY
 done
 : > "$ROOT/BACKUPS_READY" || fail SAVE_BACKUPS_READY
 sync
fi
# All pre-reset files and all OEM payloads validate before the first replacement.
snapshot_ok || fail SNAPSHOT_VERIFICATION
P=$ROOT
VERIFY=$ROOT/verify
payload_ok || fail SAVED_OEM_PAYLOAD_CORRUPT
state prepared || fail SAVE_PREPARED
for K in $OEM_KEYS;do
 T=$(target "$K")
 cp "$P/payload/$K" "$T.oem-reset-new" && chmod "$(mode "$K")" "$T.oem-reset-new" &&
 check "$T.oem-reset-new" "$(expected "$K")" || fail "STAGE_OEM_$K"
done
sync
# Stop only helper processes. Do not kill HMI, io-media or dio_manager.
if [ -z "$M" ] && command -v slay >/dev/null 2>&1;then
 for N in cpmap-guard carplay-cluster-supervisor altscreen-most-bridge carplay-pairing-helper cpvc-mirror-canvas rgi-observer artwork-fetch;do
  slay -f "$N" >/dev/null 2>&1 || :
 done
fi
state restoring || fail SAVE_RESTORING
# OEM boot FIRST: a power loss must not leave an override loading deleted JARs.
for K in $OEM_KEYS;do
 T=$(target "$K")
 mv "$T.oem-reset-new" "$T" && check "$T" "$(expected "$K")" || fail "COMMIT_$K_RESUME_RESTORE"
 sync
done
for K in $REMOVE_KEYS;do rm -f "$(target "$K")" || fail "REMOVE_$K_RESUME_RESTORE";done
oem_files_ok || fail OEM_POST_WRITE_VERIFICATION
state archiving || fail SAVE_ARCHIVING
# Same-volume renames retain every old recovery snapshot, regardless of STATE.
for N in $LAYERS;do
 if [ -d "$APP/$N" ];then mv "$APP/$N" "$ROOT/archive/$N" || fail "ARCHIVE_$N_RESUME_RESTORE";fi
done
for K in $KEYS;do
 T=$(target "$K")
 for S in $OLD_SUFFIXES;do
  if regular "$T.$S";then mv "$T.$S" "$ROOT/stale-files/$K.$S" || fail ARCHIVE_OLD_STAGE_RESUME_RESTORE;fi
 done
done
oem_files_ok || fail FINAL_OEM_VERIFICATION
for N in $LAYERS;do absent "$APP/$N" || fail FINAL_LAYER_ARCHIVE;done
state complete || fail SAVE_COMPLETE_RESUME_RESTORE
echo MU1367_OEM_RESET_COMPLETE_FULL_REBOOT_REQUIRED
echo 'OEM files verified. All old recovery directories retained under /mnt/app/carplay-mu1367-oem-reset/archive.'
echo 'Fully reboot with the phone/adapter absent. Verify OEM operation before starting step 1.'
