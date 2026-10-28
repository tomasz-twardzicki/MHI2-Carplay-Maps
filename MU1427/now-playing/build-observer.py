#!/usr/bin/env python3
"""Build N0 observation JAR against exact MU1427 inputs; run host regressions.

SPDX-License-Identifier: GPL-3.0-or-later
This is a research artifact, without an installer or cluster-output hooks.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
TARGET = 'de/vw/mib/asl/internal/carplay/target/HsmTarget.class'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--java-home', type=Path, required=True)
    p.add_argument('--stock-jar', type=Path, required=True)
    p.add_argument('--jxe', type=Path, required=True)
    p.add_argument('--asm-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location(
        'guidance_builder', HERE.parent / 'route-guidance/build-live-bridge.py')
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    if sha(a.jxe.read_bytes()) != baseline.JXE_SHA or baseline.stock_content(a.stock_jar) != baseline.STOCK_CONTENT_SHA:
        p.error('exact factory MU1427 JXE and pinned converted stock.jar required')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for name in ('helpers', 'patched', 'tools', 'tests', 'generated'):
        (out / name).mkdir()
    sources = {f.name: sha(f.read_bytes()) for f in sorted((HERE / 'java').glob('*.java'))}
    build = 'MU1427-AUDIO-N0-' + sha(json.dumps(sources, sort_keys=True).encode())[:12]
    with zipfile.ZipFile(a.stock_jar) as z:
        target = z.read(TARGET)
    (out / 'HsmTarget.class').write_bytes(target)
    generated = out / 'generated/BuildInfo.java'
    generated.write_text('package com.cpmap.audio; public final class BuildInfo { public static final String ID="' + build + '"; }\n')
    java, javac = (str(a.java_home / 'bin' / n) for n in ('java', 'javac'))
    asm = ':'.join(str((a.asm_dir / n).resolve()) for n in ('asm-9.7.jar', 'asm-tree-9.7.jar'))
    stock = str(a.stock_jar.resolve())
    subprocess.run([javac, '-source', '7', '-target', '7', '-Xlint:-options',
                    '-bootclasspath', stock, '-cp', stock, '-d', str(out / 'helpers'),
                    str(HERE / 'java/NowPlayingObserver.java'), str(generated)], check=True)
    subprocess.run([javac, '-cp', asm, '-d', str(out / 'tools'),
                    str(HERE / 'java/PatchObserver.java')], check=True)
    subprocess.run([java, '-cp', str(out / 'tools') + ':' + asm, 'PatchObserver',
                    str(out / 'HsmTarget.class'), str(out / 'helpers'), str(out / 'patched')], check=True)
    jar = out / 'CarPlayNowPlayingObserverN0.jar'
    with zipfile.ZipFile(jar, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted((out / 'patched').rglob('*.class')):
            data = f.read_bytes()
            if struct.unpack_from('>H', data, 6)[0] != 46:
                p.error('all installed classes must target major 46')
            info = zipfile.ZipInfo(str(f.relative_to(out / 'patched')), (2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    cp = str(jar) + ':' + stock
    subprocess.run([javac, '-cp', cp, '-d', str(out / 'tests'),
                    str(HERE / 'java/TestObserver.java')], check=True)
    result = subprocess.run([java, '-Xverify:all', '-cp', str(out / 'tests') + ':' + cp,
                             'com.cpmap.audio.TestObserver'], capture_output=True, text=True, check=True)
    verification = json.loads(result.stdout)
    manifest = {'build_id': build, 'phase': 'N0-observation-only', 'all_class_major': 46,
                'factory_jxe_sha256': baseline.JXE_SHA,
                'stock_content_sha256': baseline.STOCK_CONTENT_SHA,
                'factory_target_sha256': sha(target), 'jar_sha256': sha(jar.read_bytes()),
                'jar_bytes': jar.stat().st_size, 'sources': sources, 'host': verification,
                'factory_j9_verified': False, 'on_unit_validated': False,
                'cluster_output': False, 'installer_included': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
