#!/usr/bin/env python3
"""Build the GPS prototype and exercise parser rejection/OEM callback behavior."""
import argparse,hashlib,json,struct,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;SRC=HERE.parent
p=argparse.ArgumentParser()
p.add_argument('--tools',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
run=lambda *v:subprocess.run(list(map(str,v)),check=True)
clang='/Library/Developer/CommandLineTools/usr/bin/clang'
run(clang,'-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',SRC/'src/native',HERE/'location-native.c','-o',out/'location-native')
native=subprocess.check_output([str(out/'location-native')],text=True).strip()
java=a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin';stock=a.tools.resolve()/'stock.jar'
asm=':'.join(str(a.tools.resolve()/'asm'/n) for n in ('asm-9.7.jar','asm-tree-9.7.jar'))
for n in ('stock','helpers','patched','tools','test'):(out/n).mkdir()
gps=json.loads((SRC/'GPS-FACTORY.json').read_text());factory=json.loads((SRC/'FACTORY.json').read_text())
with zipfile.ZipFile(stock) as z:
 digest=hashlib.sha256()
 for n in sorted(z.namelist()):
  b=z.read(n);raw=n.encode();digest.update(struct.pack('>IQ',len(raw),len(b)));digest.update(raw);digest.update(b)
 assert digest.hexdigest()==gps['stock_content_sha256']
 for n in ('ManeuverDescriptor','DistanceToNextManeuver','RGStatus','LaneGuidance','DistanceToDestination','TimeToDestination','TurnToInfo','CurrentPositionInfo'):
  path='de/vw/mib/bap/mqbab2/navsd/functions/'+n+'.class';b=z.read(path);assert hashlib.sha256(b).hexdigest()==factory['classes'][path]
  f=out/'stock'/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
 for path,pin in gps['classes'].items():
  b=z.read(path);assert hashlib.sha256(b).hexdigest()==pin;f=out/'stock'/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',stock,'-d',out/'helpers',*sorted((SRC/'src/guidance').glob('*.java')))
run(java/'javac','-cp',asm,'-d',out/'tools',SRC/'tools/PatchLive.java',SRC/'tools/PatchGpsProbe.java')
run(java/'java','-cp',str(out/'tools')+':'+asm,'PatchLive',out/'stock',out/'helpers',out/'patched')
for path,pin in gps['classes'].items():
 run(java/'java','-cp',str(out/'tools')+':'+asm,'PatchGpsProbe',out/'stock'/path,out/'patched'/path,pin,'navigation' if '/navigation/' in path else 'clock')
with zipfile.ZipFile(out/'gps-prototype.jar','w') as z:
 for f in sorted((out/'patched').rglob('*.class')):
  b=f.read_bytes();assert struct.unpack_from('>H',b,6)[0]==46;z.writestr(str(f.relative_to(out/'patched')),b)
# Controlled monotonic-clock boundary only; production LiveBridge remains in JAR.
(out/'TestClock.java').write_text('package com.cpmap.rgi; final class LiveBridge { static long now(){return 1234;} static long hold(){return 180000;} }\n')
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',str(out/'gps-prototype.jar')+':'+str(stock),'-d',out/'test',out/'TestClock.java',HERE/'TestGpsProbe.java',HERE/'TestRoadLabel.java')
for f in (out/'test').rglob('*.class'):
 b=bytearray(f.read_bytes());struct.pack_into('>H',b,6,46);f.write_bytes(b)
cp=':'.join(map(str,[out/'test',out/'gps-prototype.jar',stock]))
probe=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp,'com.cpmap.rgi.TestGpsProbe'],text=True).strip()
r=dict(passed=True,native=native,probe=probe,prototype_jar_sha256=hashlib.sha256((out/'gps-prototype.jar').read_bytes()).hexdigest(),source_connected=False,receiver_send_hook=False,on_unit_validated=False)
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
