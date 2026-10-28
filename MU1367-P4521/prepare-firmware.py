#!/usr/bin/env python3
"""Extract and verify P4521 inputs without mounting or modifying firmware.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'MU1367/port'))
from firmware import QNX6, image_files, stage1, stage2, sha

PATHS = {
    'driver': 'armle/lib/dll/ipod-drvr-iap2.so',
    'libairplay': 'eso/lib/libairplay.so',
    'boot': 'eso/hmi/lsd/lsd.sh',
    'dio': 'eso/bin/apps/dio_manager',
}


def extract(firmware, output):
    expected = json.loads((HERE / 'FACTORY.json').read_text())
    directory = firmware / 'mmx2'
    if not directory.is_dir():
        directory = firmware / 'MMX2'
    metadata = {}
    # Check both hardware variants before writing any extracted firmware bytes.
    first = None
    for variant in ('50', '70'):
        files = image_files(stage2(directory / f'mifs-stage2/{variant}/default/mifs-stage2.img'))
        stage2_runtime = {name: sha(data) for name, data in files.items() if name in expected['stage2_runtime']}
        if stage2_runtime != expected['stage2_runtime']:
            raise ValueError('Unsupported J9 runtime in variant ' + variant)
        inputs = {'lsd.jxe': files['ifs/lsd.jxe']}
        app = QNX6(directory / f'app/{variant}/default/app.img')
        try:
            inputs.update({name: app.get(path) for name, path in PATHS.items()})
        finally:
            app.file.close()
        raw = (directory / f'efs-sys/{variant}/default/efs-system.img').read_bytes()
        if raw.count(b'iap2.cfg\0') != 1:
            raise ValueError('Ambiguous accessory configuration')
        start = raw.index(b'# This section is mandatory.', raw.index(b'iap2.cfg\0'))
        inputs['iap2.cfg'] = raw[start:raw.index(b'\xff', start)]
        record = {name: {'sha256': sha(data), 'size': len(data)} for name, data in inputs.items()}
        if record != expected['files']:
            raise ValueError('Unsupported firmware files in variant ' + variant)
        runtime = image_files(stage1(directory / f'mifs-stage1/{variant}/default/mifs-stage1.img'))
        # These libraries underpin the inherited QNX/J9 runtime verification.
        record_runtime = {name: sha(data) for name, data in runtime.items() if name in expected['stage1_runtime']}
        if record_runtime != expected['stage1_runtime']:
            raise ValueError('Unsupported factory runtime in variant ' + variant)
        metadata[variant] = {'files': record, 'stage1_runtime': record_runtime, 'stage2_runtime': stage2_runtime}
        if first is None:
            first = inputs
    output.mkdir(parents=True, exist_ok=False)
    for name, data in first.items():
        (output / name).write_bytes(data)
    result = {'firmware': expected['firmware'], 'variants': metadata,
              'matches_k4525_v140_inputs': True, 'on_unit_validated': False}
    (output / 'metadata.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.firmware, args.output)))
