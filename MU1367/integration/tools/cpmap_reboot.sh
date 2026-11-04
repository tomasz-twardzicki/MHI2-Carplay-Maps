#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
# Reboot unit from the CarPlay Maps VC menu. Refuses while the install action
# runs, then hands over to the Toolbox's own reboot helper (same as its menus).
set -u
M=${CPMAP_TEST_ROOT:-}
RAM=$M/ramdisk
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then RAM=/net/mmx/ramdisk;fi
if [ -e "$RAM/.cpmap-install-running" ] || [ -e "$RAM/.carplay-guidance-install-lock" ];then
 echo MU1367_REBOOT_REFUSED_INSTALL_STILL_RUNNING
 echo "Wait for the final install message. If no install is running, use Toolbox Coding > Reboot unit."
 exit 1
fi
HELPER=${CPMAP_REBOOT_HELPER:-${0%/*}/util_reboot.sh}
[ -f "$HELPER" ] || { echo MU1367_REBOOT_HELPER_MISSING_REFRESH_TOOLBOX_SCRIPTS;exit 1; }
echo MU1367_REBOOT_REQUESTED_DISCONNECT_PHONE_AND_ADAPTER
exec /bin/ksh "$HELPER"
