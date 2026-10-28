#!/usr/bin/env python3
"""Build isolated MU1367 display variants without touching either baseline.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    variants = {
        '791': {'default': ['--max-fps', '30', '--cluster-content', 'map-card', '--safe-area', '200,96,400,364'],
                'wide-card': ['--max-fps', '30', '--cluster-content', 'map-card', '--safe-area', '160,96,480,364'],
                'no-card': ['--max-fps', '30', '--safe-area', '200,80,400,380'], 'stock-40fps': []},
        '790': {'default': ['--max-fps', '30', '--cluster-content', 'map-card', '--safe-area', '253,16,504,360'],
                'wide-card': ['--max-fps', '30', '--cluster-content', 'map-card', '--safe-area', '202,16,606,360'],
                'low-card': ['--max-fps', '30', '--cluster-content', 'map-card', '--safe-area', '253,48,504,328'],
                'no-card': ['--max-fps', '30'], 'stock-40fps': []}}
    result = {}
    for cluster, options in variants.items():
        src = REPO / ('MU1367/791_AID12.3/payload/profiles/MU1367/791/core.so' if cluster == '791'
                      else 'MU1102/790_AID10.5/payload/profiles/MU1102/790/core.so')
        script = REPO / ('MU1427/791_AID12.3/tuning/patch-core-tuning.py' if cluster == '791'
                         else 'MU1367/790_AID10.5/tuning/patch-core-tuning.py')
        with tempfile.TemporaryDirectory() as tmp:
            patcher = Path(tmp) / 'patch.py'
            text = script.read_text()
            if cluster == '791':
                # Same original 791 core; MU1367 uses its existing AES offset
                # 0x1c8. ONLY the input identity changes, never the AES instruction.
                text = text.replace('46da26893c38367baa483f27ada72f601cc3d418e5b0fee21f7fe3cee88a6a35',
                                    '00b48a8fe876e6ff405124b87ed9eace1bcb079220ff7f02b866f42676477a4a')
            patcher.write_text(text)
            for name, args in options.items():
                dst = a.output / cluster / name / 'core.so'
                dst.parent.mkdir(parents=True)
                if args:
                    subprocess.run([sys.executable, str(patcher), *args, str(src), str(dst)], check=True)
                else:
                    shutil.copy2(src, dst)
                result[cluster + '/' + name] = hashlib.sha256(dst.read_bytes()).hexdigest()
    (a.output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
