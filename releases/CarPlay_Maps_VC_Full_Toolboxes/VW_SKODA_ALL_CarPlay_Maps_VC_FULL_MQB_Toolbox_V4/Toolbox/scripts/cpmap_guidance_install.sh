#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_guidance.sh
[ -s "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_guidance.sh
for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
    P=$V/Custom/carplay_native_guidance
    if [ -s "$P/VERSION" ]; then /bin/ksh "$S" install "$P"; exit $?; fi
done
echo "CPMAP_GUIDANCE_FAIL=SD_PAYLOAD_NOT_FOUND"
exit 1
