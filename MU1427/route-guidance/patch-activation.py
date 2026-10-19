#!/usr/bin/env python3
"""Build B4: enable the publication pool after native filesystem initialization.

Reproduces and fingerprints B3 first. No changes to receive validation, ring
format, snapshot read handler, identification/start bytes or native dispatch.
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('b3', HERE / 'patch-publication.py')
b3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b3)


def build(stock, clang='clang'):
    baseline, old = b3.build(stock, clang)
    if b3.b2.sha(baseline) != 'bfd79ed0c1a86d7ed48837d6ec4c766f2be024366d8376ceb730a1403854741d':
        raise ValueError('B3 baseline changed')
    old_symbols = {k: int(v, 16) for k, v in old['symbols'].items()}
    base = (len(baseline) + 15) & ~15
    targets = {'b3_publication_init': old_symbols['publication_init'],
               'b3_publication_control': old_symbols['publication_control'],
               'stock_fsys_init_return': 0x90a0}
    code, symbols = b3.assemble(base, targets, clang, HERE / 'publication-activation.S')
    data = bytearray(baseline)
    expected = b3.b2.branch(0x909c, old_symbols['publication_init_hook'])
    if struct.unpack_from('<I', data, 0x909c)[0] != expected:
        raise ValueError('unexpected B3 filesystem hook')
    struct.pack_into('<I', data, 0x909c, b3.b2.branch(0x909c, symbols['activation_init_hook']))
    for name, prefix in (('start_log', b'CPMAP_RGI_START B'), ('receive_log', b'CPMAP_RGI_RX B')):
        at = old_symbols[name] + len(prefix)
        if data[at] != ord('3'): raise ValueError('unexpected B3 marker')
        data[at] = ord('4')
    data.extend(bytes(base - len(data))); data.extend(code)
    elf = ELFFile(io.BytesIO(baseline))
    header = elf['e_phoff'] + 3 * elf['e_phentsize']
    size = len(data) - b3.b2.INJECT
    struct.pack_into('<II', data, header + 16, size, size)
    manifest = dict(old)
    manifest.update(build='MU1427-iAP2-RGI-B4', b3_sha256=b3.b2.sha(baseline),
                    patched_sha256=b3.b2.sha(data), patched_size=len(data),
                    activation_source_sha256=b3.b2.sha((HERE / 'publication-activation.S').read_bytes()),
                    symbols={**old['symbols'], **{k: hex(v) for k, v in symbols.items() if not k.startswith('$')}},
                    publication_hooks={**old['publication_hooks'], '0x909c': 'activation_init_hook'})
    return bytes(data), manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock', type=Path); p.add_argument('output', type=Path)
    args = p.parse_args()
    if args.stock.resolve() == args.output.resolve(): p.error('output must differ from input')
    data, manifest = build(args.stock.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    args.output.with_suffix(args.output.suffix + '.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"{manifest['build']} {len(data)} bytes sha256={manifest['patched_sha256']}")


if __name__ == '__main__': main()
