#!/usr/bin/env python3
"""Check the exact N3 executable with MU1427 libc under QNX/QEMU.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
for name in ('toolchain','firmware','reader','reference','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
spec=importlib.util.spec_from_file_location('n3_fixtures',HERE/'test-worker.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
jpeg=subprocess.check_output(['git','-C',str(a.reference),'show',fixtures.PIN+':tests/fixtures/coverart/exif-thumbnail.jpg'])
png=fixtures.png(3,2,bytes([255,0,0])*6)
work=a.output.parent/(a.output.name+'-input');work.mkdir(parents=True,exist_ok=False)
text=''
for name,data in (('png',png),('jpeg',jpeg)):
    text+='static const unsigned char n3_'+name+'_fixture[]={'+','.join(str(v) for v in data)+'};\n'
    text+='static const unsigned n3_'+name+'_bytes='+str(len(data))+';\n'
source=work/'smoke.c';source.write_text(text+(HERE/'qnx-smoke.c').read_text())
base=HERE.parents[1]/'route-guidance/test-observer-qnx.py'
subprocess.run([sys.executable,str(base),str(a.toolchain),str(a.firmware),'--native-build',str(a.reader),
    '--smoke-source',str(source),'--pass-marker','N3_QNX_PASS','--output',str(a.output)],check=True)
f=a.output/'result.json';result=json.loads(f.read_text())
result.update(sources={str(s.relative_to(HERE)):sha(s) for s in
    (HERE/'qnx-smoke.c',HERE/'capture.c',HERE/'image.c',HERE/'vendor/stb_image.h',HERE/'test-worker.py',Path(__file__))},
    base_test_sha256=sha(base),generated_smoke_sha256=sha(source),fixture_commit=fixtures.PIN,
    jpeg_fixture_sha256=hashlib.sha256(jpeg).hexdigest())
f.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
