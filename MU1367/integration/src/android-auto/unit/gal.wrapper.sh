#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# MU1367 v1.5.0-e: replaces /mnt/app/eso/bin/apps/gal, the receiver smartphone_integrator starts
# for every Android Auto phone. Runs the factory gal with the cluster-map hook only while the
# layer is installed, all runtime files and the CarPlay Maps bridge exist and nothing disabled it;
# otherwise exactly the factory gal with its environment untouched. No hashing here: the layer
# controller verified every file, and gal must start within smartphone_integrator's timeout.
L=/mnt/app/carplay-mu1367-android-auto
AA=/mnt/app/carplaymaps/aa
REAL=$L/gal.real
test -x "$REAL" || REAL=$L/backup/gal
if test ! -x "$REAL"; then
    echo "hook=none fatal=factory-gal-missing" > /ramdisk/carplay-aa-last 2>/dev/null
    exit 127
fi
USE=no
STATE=
test -r $L/STATE && read STATE < $L/STATE
if test "$STATE" = installed && test ! -e $L/DISABLED && test ! -e /mnt/app/carplaymaps/stock_first/DISABLED \
    && test -r $AA/libgal_hook.so && test -r $AA/libdmdt_flush.so && test -r $AA/gal-hook.conf \
    && test -r $AA/feeder.conf && test -x $AA/aa-most-feeder && test -x $AA/altscreen-most-bridge-aa; then
    USE=yes
fi
echo "hook=$USE state=$STATE" > /ramdisk/carplay-aa-last 2>/dev/null
if test $USE = yes; then
    # The hook reads only this file and starts only this player (no SD card or /tmp settings).
    export GAL_HOOK_CONF=$AA/gal-hook.conf
    export GAL_PLAYER_PATH=$AA/aa-most-feeder
    export GAL_HOOK_LOG=/ramdisk/carplay-aa-gal-hook.log
    export GAL_HOOK_LOG_MAX_KB=128
    export LD_PRELOAD=$AA/libgal_hook.so${LD_PRELOAD:+:$LD_PRELOAD}
fi
exec "$REAL" "$@"
