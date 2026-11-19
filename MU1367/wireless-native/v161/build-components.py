#!/usr/bin/env python3
"""Build v161 owned components; firmware/SDK paths are host inputs only."""
import argparse,hashlib,json,shutil,subprocess,struct,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--tools',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
run=lambda *args:subprocess.run(list(map(str,args)),check=True)
qnx=a.tools.resolve()/'qnx/sdp/target/qnx6'
clang=Path('/Library/Developer/CommandLineTools/usr/bin/clang')
flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(qnx),'-isystem',qnx/'usr/include','-march=armv7-a','-mfloat-abi=softfp','-mfpu=vfpv3-d16','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-I',HERE/'src/native','-I',HERE/'src/runtime/vc-runtime/runtime','-ffile-prefix-map='+str(HERE)+'=source','-ffile-prefix-map='+str(out)+'=build']
docker=['docker','--context','colima-cpmap-rgi'];lib='/opt/qnx650/target/qnx6/armle-v7/lib'
assert subprocess.check_output(docker+['image','inspect','cpmap-qnx65-sdp','--format','{{.Id}}'],text=True).strip()=='sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea'
products={
 'libcpmap-wcp-tap.so': ['native/wcp_tap.c','native/wcp_tap.S','native/wcp_rg.c'],
 'wireless-tune':['native/wireless_tune.c'],
 'wireless-receiver-exec':['native/wireless_receiver_exec.c'],
 'altscreen-most-bridge':['runtime/vc-runtime/runtime/altscreen_most_bridge.c'],
 'carplay-cluster-supervisor':['runtime/vc-runtime/runtime/carplay_cluster_supervisor.c']}
for name,sources in products.items():
 objects=[]
 for source in sources:
  obj=out/(Path(source).name+'.o');objects.append('/w/'+obj.name)
  extra=['-DWCP_TAP_SHA256=\"'+hashlib.sha256((out/'libcpmap-wcp-tap.so').read_bytes()).hexdigest()+'\"'] if name=='wireless-receiver-exec' else []
  run(clang,*flags,*extra,*(['-fPIC'] if name.endswith('.so') else []),'-c',HERE/'src'/source,'-o',obj)
 shared=name.endswith('.so')
 command=['arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','-L'+lib]
 command+=['-shared'] if shared else ['--dynamic-linker','/usr/lib/ldqnx.so.2',lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o']
 command+=objects+['-lc']+(['-lsocket'] if name=='libcpmap-wcp-tap.so' else [])
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
manifest={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in [*products,jar.name]}
(out/'COMPONENTS.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
