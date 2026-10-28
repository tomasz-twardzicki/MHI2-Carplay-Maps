#!/usr/bin/env python3
"""Build N1 native audio text from exact MU1427 classes and run host integration.
SPDX-License-Identifier: GPL-3.0-or-later
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
JAVA = HERE / 'n1/java'
JAR = 'CarPlayNowPlayingTextN1.jar'
STOCK = {
    'de/vw/mib/asl/internal/carplay/target/HsmTarget.class': '9017646043df87c6f1b6191008d2b7423e522917f6e7f2c4106558b696a59153',
    'de/vw/mib/bap/mqbab2/audiosd/functions/CurrentStationInfo.class': '875b2132e26b9968847379159dafdc16fd46cb8939cd7e74a544d7c56e405a3e',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('java-home', 'stock-jar', 'jxe', 'asm-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('guidance_builder', HERE.parent / 'route-guidance/build-live-bridge.py')
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    if sha(a.jxe.read_bytes()) != baseline.JXE_SHA or baseline.stock_content(a.stock_jar) != baseline.STOCK_CONTENT_SHA:
        p.error('exact verified MU1427 JXE and converted classes required')
    sources = {str(f.relative_to(HERE)): sha(f.read_bytes()) for f in sorted(JAVA.glob('*.java'))}
    sources['java/PatchObserver.java'] = sha((HERE / 'java/PatchObserver.java').read_bytes())
    build = 'MU1427-AUDIO-N1-' + sha(json.dumps(sources, sort_keys=True).encode())[:12]
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for name in ('stock', 'helpers', 'patched', 'tools', 'tests', 'generated'):
        (out / name).mkdir()
    with zipfile.ZipFile(a.stock_jar) as z:
        for name, digest in STOCK.items():
            data = z.read(name)
            if sha(data) != digest:
                p.error('factory class mismatch: ' + name)
            (out / 'stock' / Path(name).name).write_bytes(data)
    generated = out / 'generated/BuildInfo.java'
    generated.write_text('package com.cpmap.audio; public final class BuildInfo { public static final String ID="' + build + '"; }\n')
    # Reuse the already verified N0 lifecycle-hook/CDC patcher, targeting N1's listener.
    patcher = out / 'generated/PatchTextObserver.java'
    patcher.write_text((HERE / 'java/PatchObserver.java').read_text().replace('PatchObserver', 'PatchTextObserver').replace('com/cpmap/audio/NowPlayingObserver', 'com/cpmap/audio/TextBridge'))
    java, javac = (str(a.java_home / 'bin' / name) for name in ('java', 'javac'))
    asm = ':'.join(str((a.asm_dir / n).resolve()) for n in ('asm-9.7.jar', 'asm-tree-9.7.jar'))
    stock = str(a.stock_jar.resolve())
    subprocess.run([javac, '-source', '7', '-target', '7', '-Xlint:-options', '-bootclasspath', stock,
        '-cp', stock, '-d', str(out / 'helpers'), str(JAVA / 'TextModel.java'), str(JAVA / 'TextBridge.java'), str(generated)], check=True)
    subprocess.run([javac, '-cp', asm, '-d', str(out / 'tools'), str(patcher), str(JAVA / 'PatchText.java')], check=True)
    cp = str(out / 'tools') + ':' + asm
    subprocess.run([java, '-cp', cp, 'PatchTextObserver', str(out / 'stock/HsmTarget.class'), str(out / 'helpers'), str(out / 'patched')], check=True)
    subprocess.run([java, '-cp', cp, 'PatchText', str(out / 'stock/CurrentStationInfo.class'), str(out / 'patched')], check=True)
    jar = out / JAR
    with zipfile.ZipFile(jar, 'w') as z:
        for f in sorted((out / 'patched').rglob('*.class')):
            if struct.unpack_from('>H', f.read_bytes(), 6)[0] != 46:
                p.error('installed class must target 46')
            info = zipfile.ZipInfo(str(f.relative_to(out / 'patched')), (2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    cp = str(jar) + ':' + stock
    subprocess.run([javac, '-cp', cp, '-d', str(out / 'tests'), str(JAVA / 'TestText.java')], check=True)
    result = subprocess.run([java, '-Xverify:all', '-cp', str(out / 'tests') + ':' + cp, 'com.cpmap.audio.TestText'], capture_output=True, text=True)
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    host = json.loads(result.stdout)
    manifest = {'phase': 'N1-text-output-test', 'build_id': build, 'jar_name': JAR, 'jar_sha256': sha(jar.read_bytes()),
        'jar_bytes': jar.stat().st_size, 'all_class_major': 46, 'sources': sources, 'host': host,
        'factory_jxe_sha256': baseline.JXE_SHA, 'stock_content_sha256': baseline.STOCK_CONTENT_SHA,
        'factory_classes': STOCK, 'probe_source': 'n1/java/LoadText.java', 'probe_class': 'com.cpmap.audio.LoadText',
        'factory_j9_verified': False, 'on_unit_validated': False, 'cover_output': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
