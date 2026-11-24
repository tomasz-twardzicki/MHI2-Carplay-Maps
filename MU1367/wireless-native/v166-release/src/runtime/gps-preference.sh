#!/bin/ksh
# SD-side GEM helper. Native preference writes require writable /mnt/app.
set -u
M=${CPMAP_TEST_ROOT:-}
TOOL="$M/mnt/app/carplaymaps/wireless-tune"
case "$#:${1:-}:${2:-}" in
 2:gps:on|2:gps:off|2:gps:status|2:gps-probe:on|2:gps-probe:off|2:gps-probe:status|2:road-label:next|2:road-label:current|2:road-label:off|2:road-label:status|2:bt-release:keep|2:bt-release:profiles|2:bt-release:status) ;;
 *) echo WIRELESS_GPS_INVALID_ACTION;exit 2;;
esac
[ -x "$TOOL" ] || { echo WIRELESS_GPS_TOOL_MISSING;exit 1; }
# Read-only layer check before any mount change. Status never remounts.
"$TOOL" "$1" status || exit 1
if [ "$2" != status ];then
 command -v mount >/dev/null 2>&1 || { echo WIRELESS_GPS_MISSING_mount;exit 1; }
 if [ -z "$M" ];then mount -uw /mnt/app || { echo WIRELESS_GPS_APP_REMOUNT_FAILED;exit 1; };fi
 exec "$TOOL" "$1" "$2"
fi
