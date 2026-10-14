#!/bin/ksh
# CarPlay Maps VC - collect iAP2 / route-guidance research data to the SD card.
# Phase A of the CarPlay turn-by-turn research (MU1427/route-guidance/README.md).
# Read-only on the unit: everything is written to <SD>/Log/cpmap-navrecon-<time>/.
# Run it with the iPhone connected, CarPlay on screen and a route active in Apple Maps.

M=/net/mmx
[ -d "$M/mnt/app" ] || M=""
[ -n "${CPMAP_TEST_ROOT:-}" ] && M="$CPMAP_TEST_ROOT"

echo "CarPlay Maps VC - collect navigation research data"

VOL=""
for v in ${CPMAP_TEST_VOL:-/net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0}; do
    if [ -d "$v" ]; then VOL="$v"; break; fi
done
if [ -z "$VOL" ]; then
    echo "FAIL: no SD card found"
    exit 1
fi
mount -uw "$VOL" >/dev/null 2>&1

STAMP=`date +%Y%m%d-%H%M%S 2>/dev/null`
[ -n "$STAMP" ] || STAMP=$$
OUT="$VOL/Log/cpmap-navrecon-$STAMP"
mkdir -p "$OUT/files" "$OUT/pps" || { echo "FAIL: cannot write to $VOL"; exit 1; }

# Copy one file into $OUT/<dir>/, flattening its path (/a/b/c -> a_b_c).
grab() {   # $1 = source file, $2 = target dir under $OUT
    [ -f "$1" ] || return 0
    name=`echo "$1" | sed 's#^/##; s#/#_#g'`
    cp "$1" "$OUT/$2/$name" 2>/dev/null || cat "$1" > "$OUT/$2/$name" 2>/dev/null
}

# Search roots stay on the MMX's own filesystems (never /net, /fs or /dev).
ROOTS=""
for r in /proc/boot /lib /usr /etc /mnt/app/armle /mnt/app/usr /mnt/app/eso /mnt/app/root /mnt/efs-system /mnt/efs-persist /etc/mm; do
    [ -d "$M$r" ] && ROOTS="$ROOTS $M$r"
done

echo "Writing $OUT"
{
    echo "=== date";            date
    echo "=== uname";           uname -a
    echo "=== node";            echo "M=$M"
    echo "=== lsd.jxe";         ls -ln "$M/ifs/lsd.jxe"
    echo "=== CarPlay Maps VC"; cat "$M/mnt/app/carplaymaps/VERSION" "$M/mnt/app/carplaymaps/PROFILE"
    ls "$M/mnt/app/carplaymaps" | grep CORE_VARIANT
    echo "=== search roots";    echo "$ROOTS"
    echo "=== mounts";          mount 2>&1
} > "$OUT/summary.txt" 2>&1

# 1. Processes: full command lines (config= paths) and mapped libraries.
pidin arg > "$OUT/proc-args.txt" 2>&1
pidin mem > "$OUT/proc-mem.txt" 2>&1
# Keep each process header line plus its iAP2 / iPod / media mappings.
awk '/^ *[0-9]+ +[0-9]+ / { hdr = $0; shown = 0; next }
     /iap|ipod|mm-|io-media|mme|dio_manager|carplay/ {
         if (!shown) { print hdr; shown = 1 }
         print
     }' "$OUT/proc-mem.txt" > "$OUT/proc-mem-iap2.txt" 2>&1
grep -i -E 'iap|ipod|mm-|io-media|mme|dio_manager' "$OUT/proc-args.txt" > "$OUT/proc-args-iap2.txt" 2>&1

# 2. Where the iAP2 driver, its clients and its configs live.
{
    for r in $ROOTS; do
        find "$r" \( -name '*iap2*' -o -name '*ipod*' -o -name 'mm-*' -o -name 'io-media*' -o -name 'mme*' \) 2>/dev/null
    done
} | sort -u > "$OUT/files-found.txt" 2>&1
while read f; do
    ls -ln "$f" 2>&1
done < "$OUT/files-found.txt" > "$OUT/files-found-ls.txt"

# Copy configs and small text files, and the iAP2 driver itself (for comparison with the factory image).
while read f; do
    case "$f" in
        *.cfg|*.conf|*.ini|*.txt|*.sh|*.xml|*.json) grab "$f" files ;;
        *ipod-drvr-iap2*.so*) grab "$f" files ;;
    esac
done < "$OUT/files-found.txt"
for f in "$M"/etc/mm/* "$M"/mnt/efs-system/etc/mm/*; do
    grab "$f" files
done
ls -lnR "$M/etc/mm" "$M/mnt/efs-system/etc" > "$OUT/etc-mm-ls.txt" 2>&1

# 3. PPS: what the iAP2 driver publishes (now playing, device, messages).
ls -lnR "$M/pps/services/multimedia" > "$OUT/pps-multimedia-ls.txt" 2>&1
ls -ln "$M/pps/services" > "$OUT/pps-services-ls.txt" 2>&1
find "$M/pps/services/multimedia" -type f 2>/dev/null | while read f; do
    grab "$f" pps
done
for d in "$M"/pps/services/*; do
    case "$d" in
        *iap*|*ipod*|*carplay*|*smartphone*|*navigation*) find "$d" -type f 2>/dev/null | while read f; do grab "$f" pps; done ;;
    esac
done

# 4. System log, full and filtered.
sloginfo > "$OUT/sloginfo.txt" 2>&1
grep -i -E 'iap|ipod|ident|carplay|routeguid|maneuver|eap' "$OUT/sloginfo.txt" > "$OUT/sloginfo-iap2.txt" 2>&1

sync 2>/dev/null
mount -ur "$VOL" >/dev/null 2>&1
echo "Navigation research data written to:"
echo "  $OUT"
echo "CPMAP_NAVRECON_OK"
exit 0
