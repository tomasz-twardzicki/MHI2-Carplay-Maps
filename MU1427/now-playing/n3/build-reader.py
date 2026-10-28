#!/usr/bin/env python3
"""Build the N3 worker with pinned QNX tools and transitive source hashes.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1]/'route-guidance/build-observer.py'
def sources():
    return {str(f.relative_to(HERE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
        (HERE/'capture.c',HERE/'image.c',HERE/'vendor/stb_image.h',Path(__file__))}
p=argparse.ArgumentParser(description=__doc__)
for name in ('toolchain','firmware','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();before=sources()
subprocess.run([sys.executable,str(BASE),str(a.toolchain),str(a.firmware),'--source',str(HERE/'capture.c'),
    '--revision','N3','--output',str(a.output)],check=True)
assert before==sources(),'source changed during build'
f=a.output/'manifest.json';m=json.loads(f.read_text())
m.update(sources=before,base_builder_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest())
f.write_text(json.dumps(m,indent=2)+'\n')
