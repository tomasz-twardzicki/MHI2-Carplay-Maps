#!/usr/bin/env python3
"""Exercise actual 790 iAP2/FT code through the media-only ARM shims."""
import argparse,hashlib,importlib.util,json,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('components','setup','tools','upstream','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();components=a.components.resolve();proof=json.loads((components/'VERIFICATION.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
assert proof['passed']
for name,pin in proof['files'].items():assert sha((components/name).read_bytes())==pin
inputs=a.output.resolve().with_name(a.output.name+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
with zipfile.ZipFile(a.upstream) as z:
 for name in ('wcp_receiver','libomonob-wireless-maps.so'):
  (inputs/name).write_bytes(z.read('SD_ROOT/carplay/payload/wireless/profiles/AID10.5-17PM/'+name))
source=(HERE/'test-receiver.c').read_text().replace('@SOURCE@',str(components/'src/media790.c'))
source=source.replace('@ASM@','__asm__('+json.dumps((components/'src/media790.S').read_text())+');')
fixture_image=HERE.parents[1]/'build-v161-stable-repo/MU1367/integration/tests/artwork-png/fixtures/colors.jpg'
source=source.replace('@IMAGE@',','.join(str(b) for b in fixture_image.read_bytes()))
template=HERE.parents[1]/'tests/receiver-alt-gate.py'
code=template.read_text().replace('f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1',proof['receiver_sha256'])
ns=dict(__file__=str(template),__name__='media790_receiver_fixture');exec(compile(code,str(template),'exec'),ns)
ns.update(SOURCE=source,CFLAGS=['-I'+str(components/'src')],
 EXTRA_FILES={'payload/payload/wcp_receiver':inputs/'wcp_receiver',
              'payload/payload/libomonob-wireless-maps.so':inputs/'libomonob-wireless-maps.so',
              'media790.so':components/'libcpmap-wcp-media790.so','media790-exec':components/'wireless-receiver-exec'},
 IFS_EXTRA='media790.so\nmedia790-exec\n[type=link] /mnt/app=/ramdisk/app\n',
 RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist /ramdisk/app/carplaymaps /ramdisk/.v75-native-0123456789abcdef0123456789abcdef
cp /test/payload/payload/wcp_receiver /dev/shmem/wcp_receiver
cp /test/payload/payload/libv75-transport.so /ramdisk/app/carplaymaps/libv75-transport.so
cp /test/payload/payload/libomonob-wireless-maps.so /ramdisk/app/carplaymaps/libomonob-wireless-maps.so
cp /proc/boot/media790.so /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
/proc/boot/media790-exec --verify-only
mv /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so /ramdisk/app/carplaymaps/media.saved
echo unknown > /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
if /proc/boot/media790-exec --verify-only;then exit 79;fi
rm /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
ln -s media.saved /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
if /proc/boot/media790-exec --verify-only;then exit 80;fi
rm /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
mv /ramdisk/app/carplaymaps/media.saved /ramdisk/app/carplaymaps/libcpmap-wcp-media790.so
MU1367_GATE_ONLY=1 V75_WCP_NATIVE=1 V75_WCP_CARD=790 V75_WCP_TRANSPORT=1 V75_WCP_SCOPE=/ramdisk/.v75-native-0123456789abcdef0123456789abcdef CPMAP_WCP_MEDIA790=1 WCP_FPS=30 WCP_VIDEO_FPS=30 LD_PRELOAD=/proc/boot/gate.so:/mnt/app/carplaymaps/libv75-transport.so:/mnt/app/carplaymaps/libomonob-wireless-maps.so /dev/shmem/wcp_receiver --version
''',
 PASS_MARKER='MEDIA790_ACTUAL_RECEIVER_PASS',
 EVIDENCE=dict(media790_actual_parser=True,actual_native_file_transfer=True,production_arm_shims=True,
               launcher_hash_drift_and_symlink_refused=True,components=proof['files'],
               scope='Real 790 CSM/FT parser and production ARM metadata observer; hardware/radio/MOST/audio paths not executed.'))
sys.argv=[sys.argv[0],'--setup',str(a.setup),'--toolchain',str(a.tools/'qnx'),'--output',str(a.output)]
ns['main']()
