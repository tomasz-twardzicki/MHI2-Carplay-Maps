#!/usr/bin/env python3
"""Extend the exact B4 driver with metadata-only artwork counters.
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
RG = HERE.parents[1] / 'route-guidance'
spec = importlib.util.spec_from_file_location('b4_artwork_base', RG / 'patch-activation.py')
b4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b4)
sha = b4.b3.b2.sha
B4_SHA = '3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b'


def build(stock, clang='clang'):
    baseline, old = b4.build(stock, clang)
    if sha(baseline) != B4_SHA:
        raise ValueError('tested B4 baseline required')
    symbols = {k: int(v, 16) for k, v in old['symbols'].items()}
    base = (len(baseline) + 15) & ~15
    targets = {**b4.b3.NATIVE, 'b4_find': symbols['publication_find'],
               'b4_read': symbols['publication_read_hook'],
               'stock_init_resume': 0x865c, 'stock_setup_resume': 0x89b0,
               'stock_data_resume': 0x86b4}
    code, local = b4.b3.assemble(base, targets, clang, HERE / 'artwork-hooks.S')
    data = bytearray(baseline)
    hooks = {0x8658: (0xe92d41f0, 'artwork_init_hook'),
             0x89ac: (0xe92d4ff0, 'artwork_setup_hook'),
             0x86b0: (0xe92d4ff0, 'artwork_data_hook'),
             0x9260: (b4.b3.b2.branch(0x9260, symbols['publication_read_hook']), 'artwork_read_hook')}
    for at, (expected, name) in hooks.items():
        if struct.unpack_from('<I', data, at)[0] != expected:
            raise ValueError('hook fingerprint mismatch: ' + hex(at))
        struct.pack_into('<I', data, at, b4.b3.b2.branch(at, local[name]))
    # Extend the existing calloc only. Its visible 33088-byte header/ring and
    # read size stay unchanged; 128 extra bytes hold independent diagnostics.
    allocation = symbols['publication_init'] + 0x20
    if struct.unpack_from('<I', data, allocation)[0] != 0xe3081140:
        raise ValueError('B4 allocation instruction differs')
    struct.pack_into('<I', data, allocation, 0xe30811c0)
    data.extend(bytes(base - len(data))); data.extend(code)
    elf = ELFFile(io.BytesIO(baseline))
    ph = elf['e_phoff'] + 3 * elf['e_phentsize']
    length = len(data) - b4.b3.b2.INJECT
    struct.pack_into('<II', data, ph + 16, length, length)
    manifest = {'build': 'MU1427-AUDIO-N2-OBSERVER', 'b4_sha256': B4_SHA,
                'driver_sha256': sha(data), 'driver_bytes': len(data),
                'source_sha256': sha((HERE / 'artwork-hooks.S').read_bytes()),
                'builder_sha256': sha(Path(__file__).read_bytes()),
                'symbols': {**old['symbols'], **{k: hex(v) for k, v in local.items() if not k.startswith('$')}},
                'hooks': {hex(k): name for k, (_, name) in hooks.items()},
                'allocation_patch': hex(allocation), 'allocation_bytes': 33216,
                'guidance_snapshot_bytes': 33088, 'artwork_snapshot_bytes': 128,
                'image_output': False, 'on_unit_validated': False}
    return bytes(data), manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.stock.resolve() == a.output.resolve(): p.error('output must differ from input')
    data, manifest = build(a.stock.read_bytes())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(data)
    a.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'symbols'}))
