"""Combine the standard export with bounded wireless debugging evidence."""
from pathlib import Path
def apply(sd):
 sd=Path(sd);collector=(sd/'collect-wireless.sh').read_text()
 if 'WIRELESS_DIAGNOSTICS_STATUS=$WIRELESS_STATUS' in (sd/'Toolbox/scripts/cpmap_diag.sh').read_text():
  assert 'for F in latest.bin session.state idr.state' in collector
  return
 collector=collector.replace('while ! absent "$OUT";do N=$((N+1));OUT=$VOL/Log/wireless-diag-$N;done','''DEST=${2:-${CPMAP_DIAG_OUT:-}}
if [ -n "$DEST" ];then
 case "$DEST" in "$VOL"/Log/cpmap-diag-*/wireless) ;; *) echo WIRELESS_DIAG_OUTPUT_UNSAFE;exit 1;;esac
 OUT=$DEST
 absent "$OUT" || { echo WIRELESS_DIAG_OUTPUT_EXISTS;exit 1; }
else
 while ! absent "$OUT";do N=$((N+1));OUT=$VOL/Log/wireless-diag-$N;done
fi''')
 collector=collector.replace("pidin -F '%a %N'", "pidin -F '%a %256n'")
 collector=collector.replace('for F in wcp_autostart.log wcp.log wcp_video.log omonob-phone.log;', 'for F in wcp_autostart.log wcp.log wcp.log.old wcp_video.log btwcp.log wcp_cp.log omonob-phone.log;')
 collector=collector.replace('for F in session.state idr.state','for F in latest.bin session.state idr.state')
 collector=collector.replace('sync\necho "WIRELESS_DIAG_OK=', '''if [ -z "$M" ];then
 {
  if command -v ifconfig >/dev/null 2>&1;then ifconfig uap0; ifconfig mlan0;fi
  if command -v netstat >/dev/null 2>&1;then netstat -an;fi
 } > "$OUT/network.txt" 2>&1
fi
for R in carplay-route-guidance pmcp-aa-rg;do
 mkdir -p "$OUT/state/$R" || exit 1
 for F in adapter-status.txt guidance-evidence.txt lane-evidence.txt reader-failure-first.txt reader-lifecycle.log;do
  copy_file "$M/ramdisk/$R/$F" "$OUT/state/$R/$F"
 done
done
copy_file "$M/ramdisk/wcp-video-timing.bin" "$OUT/state/wcp-video-timing.bin"
sync
echo "WIRELESS_DIAG_OK=''')
 for name in ('collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh'):(sd/name).write_text(collector)
 diag=sd/'Toolbox/scripts/cpmap_diag.sh';s=diag.read_text()
 s=s.replace('M=/net/mmx\n[ -d "$M/mnt/app" ] || M=""','M=${CPMAP_TEST_ROOT:-/net/mmx}\n[ -d "$M/mnt/app" ] || M=""')
 s=s.replace('for v in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do','for v in ${CPMAP_TEST_MEDIA:-/net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0}; do')
 addition='''
WIRELESS_COLLECTOR=${0%/*}/cpmap_wireless_collect_data.sh
case "$VOL" in */fs/sda0) WIRELESS_VOL=/fs/sda0;; *) WIRELESS_VOL=/fs/sdb0;;esac
if [ -z "${CPMAP_TEST_ROOT:-}" ] && [ -n "$M" ];then
 on -f mmx /bin/ksh /eso/hmi/engdefs/scripts/mqb/cpmap_wireless_collect_data.sh "$WIRELESS_VOL" "${OUT#/net/mmx}/wireless" > "$OUT/wireless-export.txt" 2>&1
 WIRELESS_STATUS=$?
else
 /bin/ksh "$WIRELESS_COLLECTOR" "$WIRELESS_VOL" "$OUT/wireless" > "$OUT/wireless-export.txt" 2>&1
 WIRELESS_STATUS=$?
fi
echo "WIRELESS_DIAGNOSTICS_STATUS=$WIRELESS_STATUS"
'''
 s=s.replace('sync 2>/dev/null',addition+'\nsync 2>/dev/null')
 # Preserve base diagnostics on a partial wireless export, but never report
 # the combined export as wholly successful when the subcollector failed.
 s=s.replace('echo "CPMAP_DIAG_OK"\nexit 0','if [ "$WIRELESS_STATUS" != 0 ];then echo CPMAP_DIAG_PARTIAL_WIRELESS_EXPORT_FAILED;exit 1;fi\necho "CPMAP_DIAG_OK"\nexit 0')
 diag.write_text(s)
