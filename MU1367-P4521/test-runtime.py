#!/usr/bin/env python3
"""Rerun v1.4.0 guidance/card host checks against the exact released P4521 JARs.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'MU1367/lanes'))
import stage
sys.path.insert(0, str(HERE.parent / 'MU1367/port'))
from firmware import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('package', 'java-home', 'stock-jar', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    # Content-pin the converted factory classes; the P4521 extraction separately
    # pins the complete, byte-identical OEM JXE from which they are converted.
    factory = json.loads((HERE.parent / 'MU1367/port/FACTORY.json').read_text())
    sys.path.insert(0, str(HERE.parent / 'MU1427/route-guidance'))
    spec = importlib.util.spec_from_file_location('p4521_guidance_builder', HERE.parent / 'MU1427/route-guidance/build-live-bridge.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    if builder.stock_content(args.stock_jar) != factory['stock_content_sha256']:
        raise ValueError('Exact converted factory classes required')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    src = stage.guidance(out)
    custom = args.package.resolve() / 'sd-card/Custom'
    guidance = custom / 'carplay_mu1367_lanes/CarPlayMU1367Guidance.jar'
    menu = custom / 'carplay_mu1367_lanes/VCMenu.jar'
    cp = ':'.join(map(str, (guidance, menu, args.stock_jar.resolve())))
    java, javac = (str(args.java_home / 'bin' / name) for name in ('java', 'javac'))
    tests = [src / 'TestLive.java', HERE.parent / 'MU1367/lanes/TestLanes.java',
             HERE.parent / 'MU1367/lanes/TestCardDefault.java']
    subprocess.run([javac, '-cp', cp, '-d', str(out), *map(str, tests)], check=True)
    results = {}
    for name, argv in [('com.cpmap.rgi.TestLive', []), ('com.cpmap.rgi.TestLanes', []),
                       ('TestCardDefault', [str(out / 'card-state')])]:
        results[name] = subprocess.check_output([java, '-Xverify:all', '-cp', str(out) + ':' + cp, name, *argv], text=True).strip()
    for jar in custom.glob('carplay_mu1367*/*.jar'):
        with zipfile.ZipFile(jar) as archive:
            for name in archive.namelist():
                if name.endswith('.class') and int.from_bytes(archive.read(name)[6:8], 'big') != 46:
                    raise ValueError('Unexpected class version: ' + str(jar) + ':' + name)
    result = {'passed': True, 'results': results, 'all_installed_classes_major_46': True,
              'jars': {file.name: sha(file.read_bytes()) for file in (guidance, menu)},
              'test_sha256': sha(Path(__file__).read_bytes()), 'on_unit_validated': False}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
