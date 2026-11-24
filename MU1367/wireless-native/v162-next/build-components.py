#!/usr/bin/env python3
"""Build v161 owned components; firmware/SDK paths are host inputs only."""
import argparse,hashlib,json,shutil,subprocess,struct,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--tools',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--base-package',type=Path,required=True,help='Exact published MU1367 v1.6.1 ZIP')
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
run=lambda *args:subprocess.run(list(map(str,args)),check=True)
qnx=a.tools.resolve()/'qnx/sdp/target/qnx6'
clang=Path('/Library/Developer/CommandLineTools/usr/bin/clang')
flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(qnx),'-isystem',qnx/'usr/include','-march=armv7-a','-mfloat-abi=softfp','-mfpu=vfpv3-d16','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-I',HERE/'src/native','-I',HERE/'src/runtime/vc-runtime/runtime','-ffile-prefix-map='+str(HERE)+'=source','-ffile-prefix-map='+str(out)+'=build']
docker=['docker','--context','colima-cpmap-rgi'];lib='/opt/qnx650/target/qnx6/armle-v7/lib'
assert subprocess.check_output(docker+['image','inspect','cpmap-qnx65-sdp','--format','{{.Id}}'],text=True).strip()=='sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea'
products={
 'libcpmap-wcp-tap.so': ['native/wcp_tap.c','native/wcp_tap.S','native/wcp_rg.c'],
 'wireless-artwork-fetch':['artwork/wireless_fetch.c'],
 'wireless-tune':['native/wireless_tune.c'],
 'wireless-receiver-exec':['native/wireless_receiver_exec.c'],
 'altscreen-most-bridge':['runtime/vc-runtime/runtime/altscreen_most_bridge.c'],
 'carplay-cluster-supervisor':['runtime/vc-runtime/runtime/carplay_cluster_supervisor.c']}
for name,sources in products.items():
 objects=[]
 for source in sources:
  obj=out/(Path(source).name+'.o');objects.append('/w/'+obj.name)
  extra=['-DWCP_TAP_SHA256=\"'+hashlib.sha256((out/'libcpmap-wcp-tap.so').read_bytes()).hexdigest()+'\"'] if name=='wireless-receiver-exec' else []
  if name=='wireless-artwork-fetch':extra+=['-DCPMAP_PNG_COMPRESSED']
  run(clang,*flags,*extra,*(['-fPIC'] if name.endswith('.so') else []),'-c',HERE/'src'/source,'-o',obj)
 shared=name.endswith('.so')
 command=['arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','-L'+lib]
 command+=['-shared'] if shared else ['--dynamic-linker','/usr/lib/ldqnx.so.2',lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o']
 command+=objects+(['-L/opt/qnx650/target/qnx6/armle-v7/usr/lib','-lz'] if name=='wireless-artwork-fetch' else [])+['-lc']+(['-lsocket'] if name=='libcpmap-wcp-tap.so' else [])
 if not shared:command+=[lib+'/crtend.o',lib+'/crtn.o']
 command+=['-o','/w/'+name]
 run(*docker,'run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp',*command)
java=a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin'
asm=':'.join(str(a.tools.resolve()/'asm'/n) for n in ('asm-9.7.jar','asm-tree-9.7.jar'))
stock=a.tools.resolve()/'stock.jar'
for d in ('helpers','tools','stock','patched'):(out/d).mkdir()
factory=json.loads((HERE/'FACTORY.json').read_text());pins=factory['classes']
with zipfile.ZipFile(stock) as z:
 digest=hashlib.sha256();names=z.namelist();assert len(names)==len(set(names))
 for name in sorted(names):
  data=z.read(name);raw=name.encode('utf-8');digest.update(struct.pack('>IQ',len(raw),len(data)));digest.update(raw);digest.update(data)
 assert digest.hexdigest()==factory['stock_content_sha256'],'Exact converted MU1367 stock archive required'
 for name in ('ManeuverDescriptor','DistanceToNextManeuver','RGStatus','LaneGuidance','DistanceToDestination','TimeToDestination','TurnToInfo'):
  path='de/vw/mib/bap/mqbab2/navsd/functions/'+name+'.class';f=out/'stock'/path;f.parent.mkdir(parents=True,exist_ok=True);data=z.read(path);assert hashlib.sha256(data).hexdigest()==pins[path];f.write_bytes(data)
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',stock,'-d',out/'helpers',*sorted((HERE/'src/guidance').glob('*.java')))
run(java/'javac','-cp',asm,'-d',out/'tools',HERE/'tools/PatchLive.java')
run(java/'java','-cp',str(out/'tools')+':'+asm,'PatchLive',out/'stock',out/'helpers',out/'patched')
jar=out/'CarPlayMU1367Guidance.jar'
with zipfile.ZipFile(jar,'w') as z:
 for f in sorted((out/'patched').rglob('*.class')):
  data=f.read_bytes();assert struct.unpack_from('>H',data,6)[0]==46
  i=zipfile.ZipInfo(str(f.relative_to(out/'patched')),(2026,11,18,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,data)
assert hashlib.sha256(a.base_package.read_bytes()).hexdigest()=='38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1','Published v1.6.1 baseline required'
with zipfile.ZipFile(a.base_package) as z:
 audio_data=z.read('Custom/carplay_mu1367_artwork/CarPlayMU1367Audio.jar')
 assert hashlib.sha256(audio_data).hexdigest()=='c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3'
 (out/'baseline-audio.jar').write_bytes(audio_data)
dispatch='de/esolutions/fw/dsi/carplay/DSICarplayDispatcher.class'
with zipfile.ZipFile(stock) as z:
 data=z.read(dispatch);assert hashlib.sha256(data).hexdigest()==factory['classes'][dispatch]
 (out/'dispatcher.class').write_bytes(data)
audio_helpers=out/'audio-helpers';audio_helpers.mkdir()
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',str(out/'baseline-audio.jar')+':'+str(stock),'-d',audio_helpers,*sorted((HERE/'src/audio').glob('*.java')))
audio=out/'CarPlayMU1367Audio.jar'
with zipfile.ZipFile(out/'baseline-audio.jar') as z:entries={n:z.read(n) for n in z.namelist()}
for f in audio_helpers.rglob('*.class'):
 data=bytearray(f.read_bytes());struct.pack_into('>H',data,6,46);entries[str(f.relative_to(audio_helpers))]=bytes(data)
# Media now uses the ASL DSIProxyTarget notification route. Do not shadow the
# factory dispatcher or select an unrelated object by constructor order.
with zipfile.ZipFile(audio,'w') as z:
 for name,data in sorted(entries.items()):
  i=zipfile.ZipInfo(name,(2026,11,19,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,data)
cp_name='CarPlayWireless-CP-55915411.jar'
with zipfile.ZipFile(a.base_package) as z:cp_data=z.read('Custom/carplay_mu1367_wireless_native/payload/'+cp_name)
assert hashlib.sha256(cp_data).hexdigest()=='d158a3c98aa26159b51c25eb76eb16e3c666efd62fdb6c7d76b90ce771894453'
with zipfile.ZipFile(__import__('io').BytesIO(cp_data)) as z:cp_entries={n:z.read(n) for n in z.namelist()}
cp_class='de/vw/mib/asl/internal/wcpcp/WcpCp.class'
(out/'WcpCp.class').write_bytes(cp_entries[cp_class])
run(java/'javac','-cp',asm,'-d',out/'tools',HERE/'tools/PatchWirelessCp.java')
run(java/'java','-cp',str(out/'tools')+':'+asm,'PatchWirelessCp',out/'WcpCp.class',out/'WcpCp-patched.class')
cp_entries[cp_class]=(out/'WcpCp-patched.class').read_bytes()
cp_helpers=out/'cp-helpers';cp_helpers.mkdir()
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',stock,'-d',cp_helpers,*sorted((HERE/'src/cp').glob('*.java')))
for f in cp_helpers.rglob('*.class'):
 data=bytearray(f.read_bytes());struct.pack_into('>H',data,6,46);cp_entries[str(f.relative_to(cp_helpers))]=bytes(data)
with zipfile.ZipFile(out/cp_name,'w') as z:
 for name,data in sorted(cp_entries.items()):
  i=zipfile.ZipInfo(name,(2026,11,20,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,data)
manifest={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in [*products,jar.name,audio.name,cp_name]}
(out/'COMPONENTS.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
