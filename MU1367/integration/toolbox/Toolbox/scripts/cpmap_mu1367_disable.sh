#!/bin/ksh
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
P=""
for V in /fs/sda0 /fs/sdb0 /net/mmx/fs/sda0 /net/mmx/fs/sdb0; do
    if [ -s "$V/Custom/carplay_mu1367/VERSION" ]; then P=$V/Custom/carplay_mu1367; break; fi
done
S=$M/mnt/app/carplay-mu1367/control.sh
/bin/ksh "$S" disable "$P"
