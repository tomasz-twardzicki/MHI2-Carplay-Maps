#!/usr/bin/env python3
"""v1.5.0-e: Android Auto navigation -> hook mailbox (pmcp_rg.c, host build) -> release guidance JAR.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('build','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--docker-context',default='colima-cpmap-rgi');p.add_argument('--image',default='cpmap143e-host-tests')
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
hook=HERE.parent/'src/android-auto/hook'
# Native half in the disposable Debian host-test image (no network); Java half on the host JDK.
(out/'rg').mkdir()
c=subprocess.run(['docker','--context',a.docker_context,'run','--rm','--network=none','-v',str(hook)+':/hook:ro',
    '-v',str(HERE/'android-auto')+':/t:ro','-v',str(out)+':/o',a.image,'sh','-c',
    'cc -O1 -Wall -Wextra -Werror -std=gnu99 -pthread -I/hook /hook/pmcp_rg.c /t/rg_test.c -o /o/rg_test && '
    'GAL_PMCP_RG=1 GAL_PMCP_RG_STALE_MS=3000 GAL_PMCP_RG_END_MS=9000 GAL_PMCP_RG_DIR=/o/rg GAL_PMCP_RG_STATUS=/o/rg.txt /o/rg_test'],
    capture_output=True,text=True)
(out/'hook.log').write_text(c.stdout+c.stderr)
assert c.returncode==0 and 'FAILED CHECKS C: 0' in c.stdout,c.stdout
jar=a.build.resolve()/'CarPlayMU1367Guidance.jar';cp=':'.join(map(str,[out/'classes',jar,a.stock_jar.resolve()]))
(out/'classes').mkdir()
subprocess.run([str(a.java_home/'bin/javac'),'-nowarn','-cp',cp,'-d',str(out/'classes'),str(HERE/'android-auto/TestAndroidAutoMailbox.java')],check=True)
j=subprocess.run([str(a.java_home/'bin/java'),'-Xverify:all','-cp',cp,'com.cpmap.rgi.TestAndroidAutoMailbox',str(out/'rg')],capture_output=True,text=True)
(out/'java.log').write_text(j.stdout+j.stderr)
assert j.returncode==0 and 'FAILED CHECKS Java: 0' in j.stdout,j.stdout+j.stderr
r={'passed':True,'hook_source_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(hook.glob('pmcp_rg.*'))},
   'guidance_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'hook_checks':c.stdout.count('ok '),'java_checks':j.stdout.count('ok '),'on_unit_validated':False}
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
