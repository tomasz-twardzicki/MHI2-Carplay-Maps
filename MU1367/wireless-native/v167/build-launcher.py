#!/usr/bin/env python3
"""790-only ABI compatibility with the exact test2 BT wrapper; no JAR build."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for name in ('baseline','tested-790','tools','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
assert sha(a.baseline.read_bytes())=='e9b815eb0be0e1b9cf45564278e15b12ddbe4d0436553a40177e54324882fcae'
assert sha(a.tested_790.read_bytes())=='202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359'
with zipfile.ZipFile(a.baseline) as z:
 guard=z.read('Custom/carplay_mu1367_wireless_native/payload/libcpmap-bt-session.so')
 assert sha(guard)=='fd8f39c21bf52253bb1a8d222fee7f850fe39a96b3bf16723f9c96cc698c8acc'
with zipfile.ZipFile(a.tested_790) as z:
 observer=z.read('Custom/carplay_mu1367_input_profile/790/payload/libcpmap-wcp-media790.so')
 assert sha(observer)=='3d0f639b517a010ad6a10d456498d37f3e0f464eb246978ab94ec4c256366962'
(out/'libcpmap-wcp-media790.so').write_bytes(observer)
shutil.copy2(HERE/'src/receiver_exec790.c',out/'receiver_exec790.c')
header=HERE.parent/'v162-next/src/native/wcp_sha.h';shutil.copy2(header,out/'wcp_sha.h')
qnx=a.tools.resolve()/'qnx/sdp/target/qnx6';clang='/Library/Developer/CommandLineTools/usr/bin/clang'
subprocess.run([clang,'--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(qnx),'-isystem',str(qnx/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mfpu=vfpv3-d16','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-I'+str(out),'-ffile-prefix-map='+str(out)+'=build','-DWCP_MEDIA790_SHA256="'+sha(observer)+'"','-DBT_GUARD_SHA256="'+sha(guard)+'"','-c',str(out/'receiver_exec790.c'),'-o',str(out/'launcher.o')],check=True)
docker=['docker','--context','colima-cpmap-rgi'];lib='/opt/qnx650/target/qnx6/armle-v7/lib'
assert subprocess.check_output(docker+['image','inspect','cpmap-qnx65-sdp','--format','{{.Id}}'],text=True).strip()=='sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea'
subprocess.run(docker+['run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp','arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','-L'+lib,'--dynamic-linker','/usr/lib/ldqnx.so.2',lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o','/w/launcher.o','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/wireless-receiver-exec'],check=True)
r=dict(passed=True,scope='790 bootstrap build only; baseline 791 runtime and JARs untouched.',files={n:sha((out/n).read_bytes()) for n in ('wireless-receiver-exec','libcpmap-wcp-media790.so')},bt_guard_sha256=sha(guard),source_sha256=sha((HERE/'src/receiver_exec790.c').read_bytes()),header_sha256=sha(header.read_bytes()))
(out/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
