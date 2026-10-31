#!/usr/bin/env python3
"""Identity-bound, owned artwork capture over exact MU1367 B4/N3.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import tempfile
HERE=Path(__file__).resolve().parent
MU=HERE.parents[1]
REPO=HERE.parents[2]
NATIVE=HERE.parent/'src/artwork-native'
sys.path.insert(0,str(MU/'port'))
from build_support import load
from firmware import sha
port=load('artwork_port',MU/'port/build-driver.py')
n3=load('artwork_n3',REPO/'MU1427/now-playing/n3/build-driver.py')

def replace(s,a,b):
    if s.count(a)!=1: raise ValueError('Source fingerprint: '+a)
    return s.replace(a,b)

def build(stock,clang='clang'):
    normalized=port.normalize(stock)
    original=n3.HERE
    with tempfile.TemporaryDirectory(prefix='mu1367-artwork-') as d:
        stage=Path(d);s=(original/'artwork-hooks.S').read_text()
        s=replace(s,'    ldr r2, [r4, #0xbc]','    ldrb r2, [r4, #0xbc]')
        s=replace(s,'    str r0, [r4, #24]\n','    str r0, [r4, #24]\n    str r0, [r4, #44]\n')
        s=replace(s,'    str r10, [r7, #24]','    str r10, [r7, #24]\n    bl artwork_stamp')
        s=replace(s,'    movw r0, #0x334e','    movw r0, #0x344e')
        s=replace(s,'    str r0, [r9, #80]','    str r0, [r9, #56]\n    str r0, [r9, #60]\n'+''.join('    str r0, [r9, #'+str(i)+']\n' for i in range(80,128,4)).rstrip())
        s+='\n'+(NATIVE/'identity-hooks.S').read_text()
        (stage/'artwork-hooks.S').write_text(s)
        (stage/'build-driver.py').write_bytes(Path(__file__).read_bytes())
        old_assemble=n3.n2.b4.b3.assemble
        def assemble(base,targets,cc='clang',source=None):
            if source==stage/'artwork-hooks.S': targets={**targets,'stock_track_resume':0x1bcf0,'stock_bind_resume':0x1c87c}
            return old_assemble(base,targets,cc,source)
        n3.HERE=stage;n3.n2.b4.b3.assemble=assemble
        try: raw,m=n3.build(normalized,clang)
        finally:n3.HERE=original;n3.n2.b4.b3.assemble=old_assemble
    data=bytearray(raw)
    for at,expected,name in [(0x1bcec,0xe5d53000,'artwork_track_hook'),(0x1c878,0xe59d0034,'artwork_bind_hook')]:
        if struct.unpack_from('<I',data,at)[0]!=expected: raise ValueError('Identity seam fingerprint')
        struct.pack_into('<I',data,at,n3.n2.b4.b3.b2.branch(at,int(m['symbols'][name],16)))
        m['hooks'][hex(at)]=name
    for at,(old,new) in port.METADATA.items():
        if data[at]!=new:raise ValueError('Unexpected metadata modification')
        data[at]=old
    m.update(build='MU1367-ARTWORK-N4',driver_sha256=sha(data),driver_bytes=len(data),
             stock_sha256=port.STOCK_SHA,track_identity_verified=True,cluster_picture_output=False,
             sources={p.name:sha(p.read_bytes()) for p in (Path(__file__),NATIVE/'identity-hooks.S',original/'artwork-hooks.S')})
    return bytes(data),m

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stock',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    b,m=build(a.stock.read_bytes());a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('xb') as f:f.write(b)
    a.output.with_suffix('.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps({k:v for k,v in m.items() if k not in ('symbols','hooks')}))
