#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# MU1427 B2. The existing route-guidance-b1 backup directory is retained.
# Use the base map installer's ls -ln size checks and staged renames.
# cp -p is also used by the stock toolbox's sshd_install.sh; preserve OEM modes.
# Disconnect the phone before install/restore, and fully reboot afterwards.
set -u
INSTALLER_REVISION=B2-install-r1
BUILD_ID=MU1427-iAP2-RGI-B2-0763b7aa
ACTION=${1:-status}
PAYLOAD=${2:-}
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ -s /ifs/lsd.jxe ] && [ -d /mnt/app ]; then :
elif [ -s /net/mmx/ifs/lsd.jxe ] && [ -d /net/mmx/mnt/app ]; then M=/net/mmx
else echo "CPMAP_RGI_FAIL=MMX_NOT_FOUND"; exit 1
fi
APP=$M/mnt/app
ROOT=$APP/route-guidance-b1
DRIVER=$APP/armle/lib/dll/ipod-drvr-iap2.so
CONFIG=$M/mnt/system/etc/mm/iap2.cfg
LOCK=$M/ramdisk/.route-guidance-b1-lock
TD=$APP/armle/lib/dll/.ipod-drvr-iap2.b1-$$
TC=$M/mnt/system/etc/mm/.iap2.cfg.b1-$$
BS=$APP/.route-guidance-b1-backup-$$
OWN_LOCK=no
STOCK_DRIVER_SIZE=739925
STOCK_CONFIG_SIZE=5905
PATCHED_DRIVER_SIZE=741944
PATCHED_CONFIG_SIZE=6006

fail() { echo "CPMAP_RGI_FAIL=$1"; exit 1; }
clean() {
    if [ "$OWN_LOCK" = yes ]; then
        rm -f "$TD" "$TC" "$BS.script"
        rm -rf "$BS" "$LOCK"
    fi
}
trap clean EXIT
trap 'exit 1' HUP INT TERM

file_size() {
    # Same fifth field as install-carplay-maps.sh and restore-carplay-maps.sh.
    line=$(ls -ln "$1" 2>/dev/null) || return 1
    set -- $line
    [ "$#" -ge 5 ] || return 1
    echo "$5"
}
has_size() { [ "$(file_size "$1")" = "$2" ]; }
native() {
    if [ -n "${CPMAP_TEST_ROOT:-}" ]; then return 0
    elif [ "$M" = /net/mmx ]; then on -f mmx "$@"
    else "$@"
    fi
}
check_backups() {
    B=${1:-$ROOT}
    has_size "$B/stock-driver.so" "$STOCK_DRIVER_SIZE" || fail STOCK_DRIVER_BACKUP_INVALID
    has_size "$B/stock-iap2.cfg" "$STOCK_CONFIG_SIZE" || fail STOCK_CONFIG_BACKUP_INVALID
}
check_current_for_install() {
    D=$(file_size "$DRIVER") || fail CURRENT_DRIVER_MISSING
    C=$(file_size "$CONFIG") || fail CURRENT_CONFIG_MISSING
    case "$D" in "$STOCK_DRIVER_SIZE"|"$PATCHED_DRIVER_SIZE") ;; *) fail CURRENT_DRIVER_SIZE_UNSUPPORTED ;; esac
    case "$C" in "$STOCK_CONFIG_SIZE"|"$PATCHED_CONFIG_SIZE") ;; *) fail CURRENT_CONFIG_SIZE_UNSUPPORTED ;; esac
    # A patched or partially installed pair always needs its original backups.
    if [ "$D" != "$STOCK_DRIVER_SIZE" ] || [ "$C" != "$STOCK_CONFIG_SIZE" ]; then
        check_backups
    fi
}
restore_stock() {
    # Independent of current-file sizes/existence, SD files and build markers.
    # Stage BOTH originals before either rename.
    cp -p "$ROOT/stock-driver.so" "$TD" || return 1
    cp -p "$ROOT/stock-iap2.cfg" "$TC" || return 1
    has_size "$TD" "$STOCK_DRIVER_SIZE" || return 1
    has_size "$TC" "$STOCK_CONFIG_SIZE" || return 1
    mv "$TD" "$DRIVER" || return 1
    mv "$TC" "$CONFIG" || return 1
    has_size "$DRIVER" "$STOCK_DRIVER_SIZE" || return 1
    has_size "$CONFIG" "$STOCK_CONFIG_SIZE" || return 1
    sync 2>/dev/null || true
}

echo "MU1427 route guidance installer: $INSTALLER_REVISION"
# Only utilities already used by the base map installer / toolbox.
for tool in ls cp cat mv mkdir rm sync; do
    command -v "$tool" >/dev/null 2>&1 || fail "MISSING_COMMAND_$tool"
done
case "$ACTION" in
    status)
        echo "Driver bytes: $(file_size "$DRIVER") (stock $STOCK_DRIVER_SIZE; B2 $PATCHED_DRIVER_SIZE)"
        echo "Config bytes: $(file_size "$CONFIG") (stock $STOCK_CONFIG_SIZE; B2 $PATCHED_CONFIG_SIZE)"
        if [ -d "$ROOT" ]; then
            echo "Backup driver bytes: $(file_size "$ROOT/stock-driver.so")"
            echo "Backup config bytes: $(file_size "$ROOT/stock-iap2.cfg")"
            echo "Backup directory: $ROOT"
        else echo "No B1 backup recorded"; fi
        exit 0 ;;
    install|restore) ;;
    *) fail INVALID_ACTION ;;
esac
JXE_SIZE=$(file_size "$M/ifs/lsd.jxe") || fail FIRMWARE_STAT_FAILED
echo "Firmware check: lsd.jxe $JXE_SIZE bytes (MU1427 requires 52751492)"
[ "$JXE_SIZE" = 52751492 ] || fail WRONG_FIRMWARE

if [ "$ACTION" = install ]; then
    [ -s "$PAYLOAD/VERSION" ] || fail PAYLOAD_VERSION_MISSING
    [ "$(cat "$PAYLOAD/VERSION")" = "$BUILD_ID" ] || fail PAYLOAD_BUILD_UNSUPPORTED
    has_size "$PAYLOAD/ipod-drvr-iap2.so" "$PATCHED_DRIVER_SIZE" || fail PAYLOAD_DRIVER_SIZE_INVALID
    has_size "$PAYLOAD/iap2.cfg" "$PATCHED_CONFIG_SIZE" || fail PAYLOAD_CONFIG_SIZE_INVALID
    check_current_for_install
    if [ -d "$ROOT" ]; then
        check_backups
        # C1 verified rollback to OEM. Retain those originals while adopting
        # B2; a previous build marker must not force another restore of OEM.
        if [ "$D" != "$STOCK_DRIVER_SIZE" ] || [ "$C" != "$STOCK_CONFIG_SIZE" ]; then
            [ -s "$ROOT/VERSION" ] && [ "$(cat "$ROOT/VERSION")" = "$BUILD_ID" ] || fail DIFFERENT_BUILD_RESTORE_FIRST
        fi
    fi
else
    check_backups
fi

native mount -uw /mnt/app >/dev/null 2>&1 || fail APP_REMOUNT_FAILED
native mount -uw /mnt/system >/dev/null 2>&1 || fail SYSTEM_REMOUNT_FAILED
mkdir "$LOCK" 2>/dev/null || fail ANOTHER_OPERATION_OR_STALE_LOCK
OWN_LOCK=yes
if [ "$ACTION" = install ]; then
    check_current_for_install
    if [ -d "$ROOT" ]; then
        check_backups
    else
        has_size "$DRIVER" "$STOCK_DRIVER_SIZE" && has_size "$CONFIG" "$STOCK_CONFIG_SIZE" || fail STOCK_FILES_REQUIRED
        mkdir "$BS" || fail BACKUP_CREATE_FAILED
        cp -p "$DRIVER" "$BS/stock-driver.so" || fail DRIVER_BACKUP_FAILED
        cp -p "$CONFIG" "$BS/stock-iap2.cfg" || fail CONFIG_BACKUP_FAILED
        check_backups "$BS"
        echo "$BUILD_ID" > "$BS/VERSION" || fail BACKUP_VERSION_FAILED
        cp "$0" "$BS/rg-b1.sh" || fail RESTORE_SCRIPT_COPY_FAILED
        sync 2>/dev/null || true
        mv "$BS" "$ROOT" || fail BACKUP_PROMOTE_FAILED
        sync 2>/dev/null || true
    fi
    echo "$BUILD_ID" > "$ROOT/VERSION" || fail BACKUP_VERSION_FAILED
    # Refresh the local recovery entry when upgrading an existing backup set.
    if [ "$0" != "$ROOT/rg-b1.sh" ]; then
        cp "$0" "$BS.script" || fail RESTORE_SCRIPT_COPY_FAILED
        mv "$BS.script" "$ROOT/rg-b1.sh" || fail RESTORE_SCRIPT_COPY_FAILED
    fi
    # Preserve OEM modes while staging; check BOTH before changing active files.
    cp -p "$ROOT/stock-driver.so" "$TD" || fail DRIVER_STAGE_FAILED
    cat "$PAYLOAD/ipod-drvr-iap2.so" > "$TD" || fail DRIVER_STAGE_FAILED
    cp -p "$ROOT/stock-iap2.cfg" "$TC" || fail CONFIG_STAGE_FAILED
    cat "$PAYLOAD/iap2.cfg" > "$TC" || fail CONFIG_STAGE_FAILED
    has_size "$TD" "$PATCHED_DRIVER_SIZE" || fail DRIVER_STAGE_SIZE_INVALID
    has_size "$TC" "$PATCHED_CONFIG_SIZE" || fail CONFIG_STAGE_SIZE_INVALID
    mv "$TD" "$DRIVER" || fail DRIVER_REPLACE_FAILED
    if ! mv "$TC" "$CONFIG"; then
        restore_stock || fail CONFIG_REPLACE_FAILED_STOCK_ROLLBACK_FAILED_RETRY_RESTORE
        fail CONFIG_REPLACE_FAILED_STOCK_RESTORED
    fi
    if ! has_size "$DRIVER" "$PATCHED_DRIVER_SIZE" || ! has_size "$CONFIG" "$PATCHED_CONFIG_SIZE"; then
        restore_stock || fail INSTALL_VERIFY_FAILED_STOCK_ROLLBACK_FAILED_RETRY_RESTORE
        fail INSTALL_VERIFY_FAILED_STOCK_RESTORED
    fi
    sync 2>/dev/null || true
    echo "CPMAP_RGI_INSTALL_OK"
else
    check_backups
    restore_stock || fail STOCK_RESTORE_FAILED_RETRY_RESTORE
    # An older B1 backup set can be restored without its obsolete manifest.
    echo "$BUILD_ID" > "$ROOT/VERSION" || fail BACKUP_VERSION_FAILED
    if [ "$0" != "$ROOT/rg-b1.sh" ]; then
        cp "$0" "$BS.script" || fail RESTORE_SCRIPT_COPY_FAILED
        mv "$BS.script" "$ROOT/rg-b1.sh" || fail RESTORE_SCRIPT_COPY_FAILED
    fi
    echo "CPMAP_RGI_RESTORE_OK"
fi
echo "Disconnect iPhone, exit toolbox and do one full unit reboot."
echo "Original backups retained at $ROOT; no process was restarted."
