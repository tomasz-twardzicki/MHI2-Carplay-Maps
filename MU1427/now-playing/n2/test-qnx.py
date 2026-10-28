#!/usr/bin/env python3
"""Run the N2 helper with factory libc and stamp matching source evidence.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
for name in ('toolchain','firmware','reader','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();base=HERE.parents[1]/'route-guidance/test-observer-qnx.py'
subprocess.run([sys.executable,str(base),str(a.toolchain),str(a.firmware),
    '--native-build',str(a.reader),'--smoke-source',str(HERE/'qnx-smoke.c'),
    '--pass-marker','N2_QNX_PASS','--output',str(a.output)],check=True)
f=a.output/'result.json';result=json.loads(f.read_text())
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
result.update(smoke_source_sha256=sha(HERE/'qnx-smoke.c'),
              helper_source_sha256=sha(HERE/'snapshot.c'),
              test_sha256=sha(Path(__file__)),base_test_sha256=sha(base))
f.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
