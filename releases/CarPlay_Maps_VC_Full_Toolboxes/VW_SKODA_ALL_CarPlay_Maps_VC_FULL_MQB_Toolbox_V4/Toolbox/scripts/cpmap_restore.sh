#!/bin/ksh
# Restore the native guidance add-on before the base video patch, when present.
M=""
if [ -n "${CPMAP_TEST_ROOT:-}" ]; then M=$CPMAP_TEST_ROOT
elif [ ! -s /ifs/lsd.jxe ] && [ -s /net/mmx/ifs/lsd.jxe ]; then M=/net/mmx
fi
G=$M/mnt/app/carplay-route-guidance
if [ -s "$G/control.sh" ] && { [ -s "$G/VERSION" ] || [ -f "$M/mnt/app/eso/hmi/lsd/jars/CarPlayRouteGuidanceD1.jar" ]; }; then
    /bin/ksh "$G/control.sh" uninstall || exit $?
fi
SCRIPTS=$M/mnt/app/eso/hmi/engdefs/scripts/mqb
[ -s "$SCRIPTS/cpmap_restore_core.sh" ] || SCRIPTS=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb
/bin/ksh "$SCRIPTS/cpmap_restore_core.sh"
exit $?
