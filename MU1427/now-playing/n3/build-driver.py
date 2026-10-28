#!/usr/bin/env python3
"""Add an owned artwork mailbox to the exact A2-tested N2/B4 driver.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('n3_base', HERE.parent/'n2/build-driver.py')
n2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(n2)
sha = n2.sha
N2_SHA = '65bc96f204bdd7737434e4fe328e18ebc681ccd5db4d805684ffc7f95ee1a772'


def build(stock, clang='clang'):
    baseline, old = n2.build(stock, clang)
    if sha(baseline) != N2_SHA: raise ValueError('A2-tested N2 required')
    symbols = {k: int(v, 16) for k, v in old['symbols'].items()}
    allocation = int(old['allocation_patch'], 16)
    targets = {**n2.b4.b3.NATIVE, 'b4_find': symbols['publication_find'],
               'n2_read': symbols['artwork_read_hook'], 'n2_setup': symbols['artwork_setup_hook'],
               'allocation_resume': allocation+4, 'stock_destroy_resume': 0x85b0,
               'stock_complete_resume': 0x87a0}
    base = (len(baseline)+15)&~15
    code, local = n2.b4.b3.assemble(base, targets, clang, HERE/'artwork-hooks.S')
    data = bytearray(baseline)
    hooks = {allocation: (0xe30811c0, 'artwork_allocation'),
             0x85ac: (0xe92d4070, 'artwork_destroy_hook'),
             0x879c: (0xe3a03000, 'artwork_complete_hook'),
             0x89ac: (n2.b4.b3.b2.branch(0x89ac, symbols['artwork_setup_hook']), 'artwork_setup_hook_n3'),
             0x9260: (n2.b4.b3.b2.branch(0x9260, symbols['artwork_read_hook']), 'artwork_read_hook_n3')}
    for at, (expected, name) in hooks.items():
        if struct.unpack_from('<I', data, at)[0] != expected:
            raise ValueError('N3 seam fingerprint mismatch: '+hex(at))
        struct.pack_into('<I', data, at, n2.b4.b3.b2.branch(at, local[name]))
    data.extend(bytes(base-len(data))); data.extend(code)
    elf = ELFFile(io.BytesIO(baseline)); ph = elf['e_phoff']+3*elf['e_phentsize']
    length = len(data)-n2.b4.b3.b2.INJECT
    struct.pack_into('<II', data, ph+16, length, length)
    return bytes(data), {'build': 'MU1427-AUDIO-N3-CAPTURE', 'n2_sha256': N2_SHA,
        'driver_sha256': sha(data), 'driver_bytes': len(data),
        'source_sha256': sha((HERE/'artwork-hooks.S').read_bytes()),
        'builder_sha256': sha(Path(__file__).read_bytes()),
        'symbols': {**old['symbols'], **{k: hex(v) for k, v in local.items() if not k.startswith('$')}},
        'hooks': {hex(k): v for k, (_, v) in hooks.items()},
        'allocation_bytes': 833344, 'guidance_snapshot_bytes': 33088,
        'diagnostic_snapshot_bytes': 128, 'image_request_bytes': 800128,
        'maximum_image_bytes': 800000, 'mailbox_header_bytes': 128,
        'track_identity_verified': False, 'cluster_picture_output': False,
        'on_unit_validated': False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock',type=Path); p.add_argument('output',type=Path); a=p.parse_args()
    if a.stock.resolve()==a.output.resolve(): p.error('output must differ from stock')
    data, record=build(a.stock.read_bytes()); a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(data); a.output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k!='symbols'}))
