#!/usr/bin/env python3
"""Extract exact private MU1367 build inputs and record firmware metadata.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
from firmware import QNX6, JXE_SHA, JXE_SIZE, image_files, stage1, stage2, sha

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    expected = json.loads((HERE / 'FACTORY.json').read_text())
    metadata = {}
    for variant in ('50', '70'):
        directory = a.firmware / 'MMX2'
        ifs = stage2(directory / ('mifs-stage2/' + variant + '/default/mifs-stage2.img'))
        files = image_files(ifs)
        jxe = files['ifs/lsd.jxe']
        if len(jxe) != JXE_SIZE or sha(jxe) != JXE_SHA:
            raise ValueError('unsupported firmware HMI image')
        (out / ('stage2-' + variant + '.ifs')).write_bytes(ifs)
        if variant == '50':
            (out / 'lsd.jxe').write_bytes(jxe)
        app = QNX6(directory / ('app/' + variant + '/default/app.img'))
        paths = {'driver': 'armle/lib/dll/ipod-drvr-iap2.so', 'libairplay': 'eso/lib/libairplay.so',
                 'boot': 'eso/hmi/lsd/lsd.sh', 'dio': 'eso/bin/apps/dio_manager'}
        record = {'jxe_sha256': sha(jxe), 'stage2_sha256': sha(ifs)}
        for key, path in paths.items():
            data = app.get(path)
            if key in ('driver', 'libairplay') and sha(data) != expected[key + '_sha256']:
                raise ValueError('unsupported firmware ' + key)
            record[key] = {'sha256': sha(data), 'size': len(data)}
            if variant == '50':
                (out / key).write_bytes(data)
        # This exact uncompressed F3S image stores this small config contiguously.
        # Require a unique file header and pinned complete content, not arbitrary
        # text matches or an assumption that every F3S file has one extent.
        raw = (directory / ('efs-sys/' + variant + '/default/efs-system.img')).read_bytes()
        if raw.count(b'iap2.cfg\0') != 1:
            raise ValueError('ambiguous F3S config')
        start = raw.index(b'# This section is mandatory.', raw.index(b'iap2.cfg\0'))
        config = raw[start:raw.index(b'\xff', start)]
        if sha(config) != expected['config_sha256']:
            raise ValueError('unsupported/fragmented F3S config')
        record['config'] = {'sha256': sha(config), 'size': len(config)}
        if variant == '50':
            (out / 'iap2.cfg').write_bytes(config)
        metadata[variant] = record
    for variant in metadata.values():
        for key in ('driver', 'libairplay', 'config'):
            if variant[key] != metadata['50'][key]:
                raise ValueError('firmware variants differ')
    first = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
    metadata['libc_sha256'] = sha(first['proc/boot/libc.so.3'])
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
