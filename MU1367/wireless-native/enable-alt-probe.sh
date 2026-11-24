#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Diagnostic activation for the exact receiver; only /dev/shmem is written.
set -u
M=${CPMAP_TEST_ROOT:-}
APP=$M/mnt/app
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
fail(){ echo "MU1367_WIRELESS_ALT_PROBE_FAIL=$1";exit 1; }
command -v cat >/dev/null 2>&1 || fail MISSING_cat
[ "$(cat "$APP/carplay-mu1367-wireless-native/STATE" 2>/dev/null)" = installed ] || fail WIRELESS_LAYER_NOT_INSTALLED
[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY
absent "$M/mnt/persist/btwcp_off" || fail WIRELESS_SWITCH_OFF
absent "$M/mnt/persist/wcp_alt_off" || fail ALT_DISPLAY_EXPLICITLY_OFF
VERIFY=$APP/carplay-mu1367-wireless-native/verify
regular "$VERIFY" && regular "$M/dev/shmem/wcp_receiver" || fail RECEIVER_OR_VERIFIER_MISSING
"$VERIFY" "$M/dev/shmem/wcp_receiver" f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1 || fail UNKNOWN_RECEIVER
FLAG=$M/dev/shmem/wcp_alt_probe
if ! absent "$FLAG";then
 regular "$FLAG" || fail PROBE_PATH_UNSAFE
else
 echo 1 > "$FLAG" || fail RAM_PROBE_WRITE
fi
echo MU1367_WIRELESS_ALT_PROBE_ENABLED_UNTIL_FULL_REBOOT
echo 'Disconnect and reconnect wireless CarPlay with USB unplugged; do not reboot before testing.'
echo 'Open navigation, check the AID, then collect wireless diagnostics to SD.'
