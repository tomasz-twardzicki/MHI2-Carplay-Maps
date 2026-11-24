#!/usr/bin/env python3
"""Production PF generation/locking on QNX; stub kernel/network queries.

All templates/utilities are from the supplied MU1367 firmware. The isolated VM
has no /dev/pf or vehicle AP. Application and AP queries are explicit stand-ins;
the real PF dry-run is also attempted and its availability reported separately.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def argument(name):
    at=sys.argv.index('--'+name);value=Path(sys.argv[at+1]).resolve();del sys.argv[at:at+2];return value
firmware=argument('firmware');components=argument('components')
out=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
inputs=out.with_name(out.name+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(HERE.parents[3]/'MU1367/port'))
from firmware import QNX6,image_files,stage1,stage2
from f3s import f3s_files
files=image_files(stage1(firmware/'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
files.update(image_files(stage2(firmware/'MMX2/mifs-stage2/50/default/mifs-stage2.img')))
efs,_=f3s_files((firmware/'MMX2/efs-sys/50/default/efs-system.img').read_bytes())
files.update(efs)
app=QNX6(firmware/'MMX2/app/50/default/app.img')
files['armle/sbin/pfctl']=app.get('armle/sbin/pfctl');app.file.close()
pins={}
for name in ['pf.conf','pf.mlan0.conf','pf.ecm0.conf','pf.ppp0.conf','sleep','pidin','pfctl','ifconfig']:
    hits={b for p,b in files.items() if Path(p).name==name};assert len(hits)==1,name
    data=hits.pop();(inputs/name).write_bytes(data);pins[name]=hashlib.sha256(data).hexdigest()
kernel=r'''#!/bin/sh
case "$1" in
-s)
 if [ "$2" = rules ];then
  [ -f /ramdisk/pf-loaded ] && echo 'pass in quick from (uap0:network) to (uap0) port = 5000'
  exit 0
 fi
 [ "$2" = nat ] || exit 1
 [ ! -f /ramdisk/nat-unready ] || exit 0
 U=$(cat /ramdisk/uplink)
 case "$U" in
 default) echo 'nat pass on ppp0 all tagged WLAN';echo 'nat pass on ecm0 all tagged WLAN';;
 mlan0) echo 'nat pass on mlan0 all tagged WLAN';;
 ecm0) echo 'nat pass on ecm0 all tagged WLAN';;
 ppp0) echo 'nat pass on ppp0 all tagged WLAN';echo 'nat pass on en0 all tagged WLAN';;
 esac ;;
-n)
 [ ! -f /ramdisk/syntax-fail ] && [ -s "$3" ] || exit 1
 grep -q 'wlan_if' "$3" || exit 1 ;;
-f)
 [ ! -f /ramdisk/apply-fail ] || exit 1
 if ! mkdir /ramdisk/pf-in-apply;then echo PF_CONCURRENT_APPLY > /ramdisk/pf-race;exit 91;fi
 if [ -f /ramdisk/delay-apply ];then sleep 1;fi
 cp "$2" /ramdisk/applied.conf || exit 1
 echo applied > /ramdisk/pf-loaded
 rm -rf /ramdisk/pf-in-apply ;;
*) exit 1;;
esac
'''
(inputs/'pf-kernel.sh').write_text(kernel)
(inputs/'ap-query.sh').write_text('''#!/bin/sh
[ ! -f /ramdisk/ap-unready ] || exit 1
echo 'uap0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST>'
echo ' inet 10.173.189.1 netmask 0xffffff00'
''')
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE='int unused_pf_fixture;\n'
fixture.EXTRA_FILES={name:inputs/name for name in ['pf.conf','pf.mlan0.conf','pf.ecm0.conf','pf.ppp0.conf','sleep','pidin','pf-kernel.sh','ap-query.sh']}
fixture.EXTRA_FILES.update({'firmware-pfctl':inputs/'pfctl','firmware-ifconfig':inputs/'ifconfig',
    'wireless-tune':components/'wireless-tune','pf-production.sh':HERE.parent/'src/runtime/wcp_pf.sh',
    'controller.sh':HERE.parent/'src/runtime/wcp_ctl.sh'})
fixture.IFS_EXTRA='[type=link] /mnt/app=/ramdisk/app\n[type=link] /mnt/ota=/ramdisk/ota\n[type=link] /etc=/ramdisk/etc\n[type=file]\n'+'\n'.join(fixture.EXTRA_FILES)+'\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/app/carplaymaps /ramdisk/app/armle/sbin /ramdisk/ota /ramdisk/etc /ramdisk/gate-persist
cp /proc/boot/wireless-tune /mnt/app/carplaymaps/wireless-tune
cp /proc/boot/pf-production.sh /mnt/ota/wcp_pf.sh
cp /proc/boot/pf-kernel.sh /mnt/app/armle/sbin/pfctl
cp /proc/boot/ap-query.sh /ramdisk/ifconfig
chmod 755 /mnt/app/carplaymaps/wireless-tune /mnt/app/armle/sbin/pfctl /ramdisk/ifconfig
export PATH=/ramdisk:/proc/boot:/bin
for F in pf.conf pf.mlan0.conf pf.ecm0.conf pf.ppp0.conf;do cp /proc/boot/$F /etc/$F;done
echo default > /ramdisk/uplink
echo wait > /ramdisk/ap-unready
if /bin/sh /mnt/ota/wcp_pf.sh on;then exit 81;fi
test ! -f /ramdisk/wcp-pf.ready
rm -f /ramdisk/ap-unready
echo wait > /ramdisk/nat-unready
if /bin/sh /mnt/ota/wcp_pf.sh on;then exit 82;fi
test ! -f /ramdisk/wcp-pf.ready
if WCP_VIDEO=0 /bin/sh /proc/boot/controller.sh start > /ramdisk/not-ready 2>&1;then exit 83;fi
grep WCP_PF_NOT_READY /ramdisk/not-ready
test ! -f /dev/shmem/wcp_receiver.pid
rm -f /ramdisk/nat-unready
for U in default mlan0 ecm0 ppp0;do
 echo "$U" > /ramdisk/uplink
 /bin/sh /mnt/ota/wcp_pf.sh on
 case "$U" in default) EXPECT=/etc/pf.conf;; *) EXPECT=/etc/pf.$U.conf;;esac
 grep "$EXPECT" /ramdisk/wcp-pf.ready
 grep "$EXPECT" /dev/shmem/wcp_pf.src
done
A=$(cat /ramdisk/wcp-pf.ready)
/bin/sh /mnt/ota/wcp_pf.sh check
test "$(cat /ramdisk/wcp-pf.ready)" = "$A"
echo force > /ramdisk/syntax-fail
if /bin/sh /mnt/ota/wcp_pf.sh on;then exit 84;fi
test ! -f /ramdisk/wcp-pf.ready
rm -f /ramdisk/syntax-fail
echo force > /ramdisk/apply-fail
if /bin/sh /mnt/ota/wcp_pf.sh on;then exit 85;fi
test ! -f /ramdisk/wcp-pf.ready
rm -f /ramdisk/apply-fail
echo wait > /ramdisk/delay-apply
/bin/sh /mnt/ota/wcp_pf.sh on > /ramdisk/apply-one 2>&1 &
A=$!
/bin/sh /mnt/ota/wcp_pf.sh on > /ramdisk/apply-two 2>&1 &
B=$!
wait "$A"
wait "$B"
test ! -f /ramdisk/pf-race
grep PF_READY /ramdisk/apply-one
grep PF_READY /ramdisk/apply-two
# Kernel-held locks are released on a killed owner; no stale mkdir lock exists.
/bin/sh /mnt/ota/wcp_pf.sh on > /ramdisk/killed-apply 2>&1 &
A=$!
sleep 1
kill "$A" 2>/dev/null || :
wait "$A" 2>/dev/null || :
sleep 2
rm -rf /ramdisk/pf-in-apply
rm -f /ramdisk/delay-apply
/bin/sh /mnt/ota/wcp_pf.sh on
test ! -f /ramdisk/pf-race
/bin/sh /mnt/ota/wcp_pf.sh off
test ! -f /ramdisk/wcp-pf.ready
test ! -f /dev/shmem/wcp_pf.src
/mnt/app/carplaymaps/wireless-tune monotonic
# A real parser dry-run is separate from the explicit kernel stand-in above.
if /proc/boot/firmware-pfctl -n -f /etc/pf.conf > /ramdisk/pf-real-dryrun 2>&1;then
 echo PF_REAL_PARSER_DRYRUN_AVAILABLE
else
 echo PF_REAL_PARSER_DRYRUN_UNAVAILABLE
 cat /ramdisk/pf-real-dryrun
fi
echo PF_QNX_PASS serialization=1 readiness=1 startup_gate=1 uplinks=4 error_recovery=1 lock_owner_exit=1 oem_off=1 kernel_queries_stubbed=1
'''
fixture.PASS_MARKER='PF_QNX_PASS'
fixture.EVIDENCE=dict(components=json.loads((components/'COMPONENTS.json').read_text()),
    firmware=firmware.name,firmware_files_sha256=pins,
    pf_script_sha256=hashlib.sha256((HERE.parent/'src/runtime/wcp_pf.sh').read_bytes()).hexdigest(),
    kernel_queries_stubbed=True,actual_kernel_pf_application_tested=False)
fixture.main()
