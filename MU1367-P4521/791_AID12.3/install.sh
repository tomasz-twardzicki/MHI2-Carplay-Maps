#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# P4521 / 791 entry point. Run from the matching extracted SD bundle.
set -u
P=${1:-}
fail() { echo "MU1367_P4521_FAIL=$1"; exit 1; }
[ -n "$P" ] || fail PAYLOAD_ARGUMENT_REQUIRED
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
V=$P/../carplay_mu1367/verify
[ -f "$V" ] && [ ! -L "$V" ] || fail VERIFIER_MISSING
check() {
    F=$M/$1
    [ -f "$F" ] && [ ! -L "$F" ] || fail "ORIGINAL_REQUIRED_$1"
    if [ "$M" = /net/mmx ]; then
        on -f mmx "${V#/net/mmx}" "/$1" "$2" || fail "ORIGINAL_HASH_$1"
    else
        "$V" "$F" "$2" || fail "ORIGINAL_HASH_$1"
    fi
}
# No remount, backup or write occurs before every original passes SHA-256.
check ifs/lsd.jxe 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a
check mnt/app/armle/lib/dll/ipod-drvr-iap2.so 7149a3e75b1b19e89021841759f420a6eced456b6c697a3dd1f0e436abea0b8c
check mnt/app/eso/lib/libairplay.so 193a4fd9101ec2aa05e7159cfa307b96500810d379ca74a194f172adc13a46b5
check mnt/app/eso/hmi/lsd/lsd.sh fe4f9cc8bd68282238546605c53b36ca0add985eafc8a100a477a7f827f4a731
check mnt/app/eso/bin/apps/dio_manager ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae
check mnt/system/etc/mm/iap2.cfg 88a4d24f5c50b181d73429fb585ad6b38d10daca67c5b5a9798ef17f84208bbe
for S in carplaymaps carplay-mu1367 carplay-mu1367-settings carplay-mu1367-lanes; do
    [ ! -e "$M/mnt/app/$S" ] && [ ! -L "$M/mnt/app/$S" ] || fail EXISTING_INSTALLATION_OR_RECOVERY_USE_SAVED_CONTROLLERS
done
exec /bin/ksh "$P/payload/common/install-carplay-maps.sh" "$P/payload" MU1367 791
