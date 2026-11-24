#!/usr/bin/env python3
"""Run the 790-only launcher with the actual unchanged test2 BT wrapper."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for n in ('build','launcher','setup','toolchain','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sd=a.build.resolve()/'sd-card';base=sd/'Custom/carplay_mu1367_wireless_native/payload';child=sd/'Custom/carplay_mu1367_input_profile/790/payload'
proof=json.loads((a.launcher/'VERIFICATION.json').read_text());assert proof['passed']
for name,pin in proof['files'].items():assert sha((child/name).read_bytes())==pin
inputs=a.output.resolve().with_name(a.output.name+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
wrapper=(base/'btstack_wrap.sh').read_text();pin=sha(wrapper.encode())
assert wrapper.count('exec "$REAL" "$@"')==2
wrapper=wrapper.replace('exec "$REAL" "$@"','echo "V167_BT_WRAPPER guard=${CPMAP_BT_GUARD:-0} preload=${LD_PRELOAD:-none}";exit 0')
(inputs/'wrapper.sh').write_text(wrapper)
extra={'launch790':child/'wireless-receiver-exec','guard165t2.so':base/'libcpmap-bt-session.so','addon.so':base/'libbtwcp.so','transport.so':base/'libv75-transport.so','maps790.so':child/'libomonob-wireless-maps.so','media790.so':child/'libcpmap-wcp-media790.so','receiver790':child/'wcp_receiver','wrapper.sh':inputs/'wrapper.sh'}
assert sha((base/'libcpmap-bt-session.so').read_bytes())=='fd8f39c21bf52253bb1a8d222fee7f850fe39a96b3bf16723f9c96cc698c8acc'
script=r'''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/app/carplaymaps /ramdisk/ota /ramdisk/gate-persist
cp /proc/boot/launch790 /ramdisk/app/carplaymaps/wireless-receiver-exec
cp /proc/boot/guard165t2.so /ramdisk/app/carplaymaps/libcpmap-bt-session.so
cp /proc/boot/addon.so /ramdisk/ota/libbtwcp.so
cp /proc/boot/transport.so /ramdisk/app/carplaymaps/libv75-transport.so
cp /proc/boot/maps790.so /ramdisk/app/carplaymaps/libomonob-wireless-maps.so
cp /proc/boot/media790.so /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
cp /proc/boot/receiver790 /dev/shmem/wcp_receiver
/proc/boot/launch790 --transport-status
/proc/boot/launch790 --bt-guard-status
/proc/boot/launch790 --verify-only
/proc/boot/launch790 --launch-stamp video-before 0
if /proc/boot/launch790 --launch-stamp invalid 0;then exit 70;fi
echo 1 > /mnt/persist/btwcp_enable
/bin/ksh /proc/boot/wrapper.sh > /ramdisk/good
grep 'guard=1 preload=/mnt/app/carplaymaps/libcpmap-bt-session.so:' /ramdisk/good
mv /ramdisk/app/carplaymaps/libcpmap-bt-session.so /ramdisk/guard.saved
echo drift > /ramdisk/app/carplaymaps/libcpmap-bt-session.so
if /proc/boot/launch790 --bt-guard-status;then exit 71;fi
/bin/ksh /proc/boot/wrapper.sh > /ramdisk/drift
grep 'guard=0 preload=none' /ramdisk/drift
rm /ramdisk/app/carplaymaps/libcpmap-bt-session.so
ln -s /ramdisk/guard.saved /ramdisk/app/carplaymaps/libcpmap-bt-session.so
if /proc/boot/launch790 --bt-guard-status;then exit 72;fi
rm /ramdisk/app/carplaymaps/libcpmap-bt-session.so
mv /ramdisk/guard.saved /ramdisk/app/carplaymaps/libcpmap-bt-session.so
echo 1 > /mnt/persist/btwcp_off
/bin/ksh /proc/boot/wrapper.sh > /ramdisk/off
grep 'guard=0 preload=none' /ramdisk/off
rm /mnt/persist/btwcp_off
echo drift > /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
if /proc/boot/launch790 --verify-only;then exit 73;fi
echo V167_LAUNCHER_PASS baseline_wrapper=1 baseline_guard=1 only_final_bt_exec_stubbed=1
'''
template=HERE.parents[1]/'tests/receiver-alt-gate.py'
ns=dict(__file__=str(template),__name__='v167_launcher_fixture');exec(compile(template.read_text(),str(template),'exec'),ns)
ns.update(SOURCE='int v167_launcher_fixture_no_receiver;\n',EXTRA_FILES=extra,
 IFS_EXTRA=''.join(n+'\n' for n in extra)+'[type=link] /mnt/app=/ramdisk/app\n[type=link] /mnt/ota=/ramdisk/ota\n',RUN_SCRIPT=script,PASS_MARKER='V167_LAUNCHER_PASS',
 EVIDENCE=dict(scope='Actual 790 bootstrap CLI and test2 BT wrapper; final btstack exec only replaced by readback; receiver/radio not executed.',components=proof['files'],bt_wrapper_sha256=pin,bt_guard_sha256=proof['bt_guard_sha256']))
sys.argv=[sys.argv[0],'--setup',str(a.setup),'--toolchain',str(a.toolchain),'--output',str(a.output)]
ns['main']()
