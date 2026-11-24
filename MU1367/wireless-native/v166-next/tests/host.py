#!/usr/bin/env python3
"""ASan/UBSan timing/mailbox policy and C-to-factory-Java wireless integration."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('tools','components','guidance-tests','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
clang='/Library/Developer/CommandLineTools/usr/bin/clang';native=HERE.parent/'src/native'
results={}
for name,source in [('policy','policy.c'),('publish','publish-fixture.c')]:
 command=[clang,'-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-I',str(native),'-I',str(HERE.parent/'src/runtime/vc-runtime/runtime'),str(HERE/source),str(native/'wcp_rg.c'),'-o',str(out/name)]
 subprocess.run(command,check=True)
 if name=='policy':results[name]=subprocess.check_output([str(out/name)],text=True).strip()
java=a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin'
cp=':'.join(map(str,[out,a.guidance_tests.resolve(),a.components.resolve()/'CarPlayMU1367Guidance.jar',a.tools.resolve()/'stock.jar']))
subprocess.run([str(java/'javac'),'-cp',cp,'-d',str(out),str(HERE/'TestWireless.java'),str(HERE/'TestWirelessEndToEnd.java')],check=True)
for name,args in [('TestWireless',[]),('TestWirelessEndToEnd',[str(out/'native-e2e'),str(out/'publish')])]:results[name]=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp,'com.cpmap.rgi.'+name,*args],text=True).strip()
r=dict(passed=True,sanitizers=['address','undefined'],guidance_sha256=hashlib.sha256((a.components/'CarPlayMU1367Guidance.jar').read_bytes()).hexdigest(),results=results,tests_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in HERE.iterdir() if f.is_file() and f.suffix in ('.c','.java')})
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
