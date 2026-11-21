#!/usr/bin/env python3
"""Compare full PES payloads after resets at every TS packet boundary."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
results={}
for label,root in [('old',HERE.parents[1]/'v162'),('fixed',HERE.parent)]:
    work=out/label;work.mkdir();bridge=root/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c'
    (work/'test.c').write_text((HERE/'bridge-recovery.c.in').read_text().replace('@BRIDGE@',str(bridge)))
    flags=['-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g',
           '-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation',
           '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'src/native'),'-I'+str(bridge.parent)]
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/clang',*flags,str(work/'test.c'),'-o',str(work/'test')],check=True)
    with (work/'stderr.log').open('w') as err:
        result=json.loads(subprocess.check_output([str(work/'test')],cwd=work,stderr=err,text=True))
    result.update(bridge_sha256=hashlib.sha256(bridge.read_bytes()).hexdigest(),
        no_reset_ts_sha256=hashlib.sha256((work/'no-reset.ts').read_bytes()).hexdigest())
    results[label]=result
assert results['old']['truncated_access_units']>0
assert not results['old']['incoming_idr_preserved'] and not results['old']['one_fast_block_recovers']
assert results['fixed']['truncated_access_units']==0
assert results['fixed']['incoming_idr_preserved'] and results['fixed']['one_fast_block_recovers']
assert results['fixed']['no_reset_ts_sha256']==results['old']['no_reset_ts_sha256']
report=dict(passed=True,sanitizers=['address','undefined'],results=results,hardware_opened=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
