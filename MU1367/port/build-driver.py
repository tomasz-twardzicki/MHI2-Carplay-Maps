#!/usr/bin/env python3
"""Reuse verified hooks only after proving exact code equivalence to MU1427.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import io
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from build_support import load
from firmware import sha

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STOCK_SHA = '7149a3e75b1b19e89021841759f420a6eced456b6c697a3dd1f0e436abea0b8c'
NORMAL_SHA = '0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51'
# The complete difference between the two exact factory files. All bytes are
# inside non-allocated QNX_info / .gnu_debuglink, outside every program segment. Nothing in
# code, rodata, imports, relocations, layout, or stock RX ownership differs.
METADATA = {0xae403:(54,53), 0xae406:(49,48), 0xae408:(48,49), 0xae409:(52,54),
            0xae40b:(49,48), 0xae40c:(55,53), 0xae40f:(54,49), 0xae411:(50,52),
            0xae412:(48,55), 0xae453:(52,49), 0xae460:(56,55), 0xae461:(49,56),
            0xae462:(54,57), 0xae463:(55,56), 0xae464:(49,54), 0xae465:(52,55),
            0xae47f:(187,232), 0xae480:(80,193), 0xae481:(4,45), 0xae482:(163,218)}


def normalize(stock):
    if sha(stock) != STOCK_SHA:
        raise ValueError('exact MU1367 stock driver required')
    elf = ELFFile(io.BytesIO(stock))
    notes = [elf.get_section_by_name(n) for n in ('QNX_info', '.gnu_debuglink')]
    if any(n is None or n['sh_flags'] != 0 for n in notes):
        raise ValueError('metadata must not be allocated')
    data = bytearray(stock)
    for at, (old, new) in METADATA.items():
        if not any(n['sh_offset'] <= at < n['sh_offset'] + n['sh_size'] for n in notes):
            raise ValueError('difference outside build metadata')
        if any(s['p_offset'] <= at < s['p_offset'] + s['p_filesz'] for s in elf.iter_segments()):
            raise ValueError('metadata difference inside a loaded segment')
        if data[at] != old:
            raise ValueError('metadata mismatch')
        data[at] = new
    if sha(data) != NORMAL_SHA:
        raise ValueError('MU1367 executable content differs from verified hook baseline')
    return bytes(data)


def build(stock, artwork=False):
    normalized = normalize(stock)
    source = REPO / ('MU1427/now-playing/n3/build-driver.py' if artwork else 'MU1427/route-guidance/patch-activation.py')
    baseline, inherited = load('mu1367_native_builder', source).build(normalized)
    data = bytearray(baseline)
    for at, (old, new) in METADATA.items():
        if data[at] != new:
            raise ValueError('hook patch unexpectedly altered build metadata')
        data[at] = old
    # Check every load mapping and all bytes, including injected hooks.
    a, b = ELFFile(io.BytesIO(baseline)), ELFFile(io.BytesIO(data))
    for left, right in zip(a.iter_segments(), b.iter_segments(), strict=True):
        if left.header != right.header or left.data() != right.data():
            raise ValueError('ported runtime differs from regression baseline')
    return bytes(data), {'firmware': 'MU1367', 'variant': 'N3' if artwork else 'B4',
                         'stock_sha256': STOCK_SHA, 'normalized_stock_sha256': NORMAL_SHA,
                         'normalized_patched_sha256': sha(baseline), 'sha256': sha(data), 'size': len(data),
                         'metadata_bytes_preserved': len(METADATA), 'identical_program_segments': True,
                         'inherited': inherited, 'on_unit_validated': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--artwork', action='store_true')
    a = p.parse_args()
    if a.stock.resolve() == a.output.resolve():
        p.error('output must differ from stock')
    data, manifest = build(a.stock.read_bytes(), a.artwork)
    with a.output.open('xb') as f:
        f.write(data)
    a.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:v for k,v in manifest.items() if k != 'inherited'}))
