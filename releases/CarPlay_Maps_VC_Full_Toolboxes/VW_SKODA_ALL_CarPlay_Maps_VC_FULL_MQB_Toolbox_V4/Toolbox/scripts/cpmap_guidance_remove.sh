#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_guidance.sh
[ -s "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_guidance.sh
/bin/ksh "$S" uninstall
