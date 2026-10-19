#!/usr/bin/env python3
"""Build D1 from the exact converted MU1427 classes; no firmware bytes in git.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
STOCK_CONTENT_SHA = '7c63a1130d42999f18d1f30195292ba547aa14a767df7edab5d09f1ae6feffdf'
JXE_SHA = 'f46290b4a33b98d957170f6207073ad329316902a87cd4c27da4168548ad911a'
CLASSES = dict(zip(('ManeuverDescriptor', 'DistanceToNextManeuver', 'RGStatus', 'LaneGuidance'), (
    '5c0fb75e1c4532b9665363fdae72414d82242c00fee256f9d2944c750db8ef33',
    '8222aa0d2bd086b15b17942bb935a081c028041c788c785ea11dd3c99cfa9e6d',
    'fa83a46b89b56f6fa98e83a2f7fe9861da161191bc9ae5e878daeb81b58c6573',
    '5bbaf19f7a188da5405ba43fdb54611ca0423348e837a37b7673a1abeb9d8d4f')))
CLASSES.update({'DistanceToDestination': 'ca5388a1cb25b176669d9f9f4c9bcc89562daf100080a1c8768cb5f35409b8c0', 'TimeToDestination': '8d307c132b00d74828562429b10dc3058fbb0f93fb5e53f084e77504905fe8aa'})
RUNTIME = ('LiveModel.java', 'JournalReader.java', 'MailboxReader.java', 'LiveBridge.java')


def sha(data): return hashlib.sha256(data).hexdigest()


def stock_content(path):
    # jxe2jar sets ZIP timestamps at conversion time. Verify all entry names
    # and bytes, without making a correct rebuild depend on those timestamps.
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(set(names)) != len(names): raise ValueError('duplicate stock JAR entries')
        for name in sorted(names):
            data = z.read(name); raw = name.encode('utf-8')
            digest.update(struct.pack('>IQ', len(raw), len(data))); digest.update(raw); digest.update(data)
    return digest.hexdigest()


def source_id(release=False):
    return sha(b''.join(n.encode() + b'\0' + (HERE / 'bridge' / n).read_bytes() for n in (*RUNTIME, 'PatchLive.java')) + (b'release' if release else b'manual'))[:16]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--java-home', type=Path, required=True)
    p.add_argument('--stock-jar', type=Path, required=True)
    p.add_argument('--jxe', type=Path, required=True)
    p.add_argument('--asm-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, default=HERE / 'build-D3-hmi')
    p.add_argument('--release', action='store_true')
    a = p.parse_args()
    if sha(a.jxe.read_bytes()) != JXE_SHA or stock_content(a.stock_jar) != STOCK_CONTENT_SHA:
        p.error('exact verified JXE/pinned converted stock.jar required')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    for sub in ('stock', 'helpers', 'patcher', 'patched', 'tests', 'generated'): (out / sub).mkdir()
    java, javac = a.java_home / 'bin/java', a.java_home / 'bin/javac'
    asm = ':'.join(str((a.asm_dir / n).resolve()) for n in ('asm-9.7.jar', 'asm-tree-9.7.jar'))
    with zipfile.ZipFile(a.stock_jar) as z:
        for name, digest in CLASSES.items():
            n = 'de/vw/mib/bap/mqbab2/navsd/functions/' + name + '.class'
            data = z.read(n)
            if sha(data) != digest: p.error('factory class mismatch: ' + name)
            dest = out / 'stock' / n; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
    build_info = out / 'generated/BuildInfo.java'
    build_info.write_text('package com.cpmap.rgi; public final class BuildInfo { public static final String ID="' + source_id(a.release) + '"; public static final boolean RELEASE=' + str(a.release).lower() + '; }\n')
    subprocess.run([str(javac), '-source', '7', '-target', '7', '-Xlint:-options', '-bootclasspath', str(a.stock_jar), '-cp', str(a.stock_jar), '-d', str(out / 'helpers'),
                    *(str(HERE / 'bridge' / n) for n in RUNTIME), str(build_info)], check=True)
    subprocess.run([str(javac), '-cp', asm, '-d', str(out / 'patcher'), str(HERE / 'bridge/PatchLive.java')], check=True)
    subprocess.run([str(java), '-cp', str(out / 'patcher') + ':' + asm, 'PatchLive', str(out / 'stock'), str(out / 'helpers'), str(out / 'patched')], check=True)
    cp = str(out / 'patched') + ':' + str(a.stock_jar.resolve())
    subprocess.run([str(javac), '-cp', cp, '-d', str(out / 'tests'), str(HERE / 'bridge/TestLive.java')], check=True)
    jar = out / 'CarPlayRouteGuidanceD1.jar'
    with zipfile.ZipFile(jar, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted((out / 'patched').rglob('*.class')):
            if struct.unpack_from('>H', f.read_bytes(), 6)[0] != 46: p.error('non-CDC class version in installed JAR')
            info = zipfile.ZipInfo(str(f.relative_to(out / 'patched')), date_time=(2026, 10, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16; z.writestr(info, f.read_bytes())
    result = subprocess.run([str(java), '-Xverify:all', '-cp', str(out / 'tests') + ':' + str(jar) + ':' + str(a.stock_jar.resolve()), 'com.cpmap.rgi.TestLive'], capture_output=True, text=True, check=True)
    verification = json.loads(result.stdout)
    manifest = {'revision': 'release' if a.release else 'D3', 'all_class_major': 46, 'factory_cdc_compile': True,
                'source_id': source_id(a.release), 'jar_sha256': sha(jar.read_bytes()), 'jar_size': jar.stat().st_size,
                'factory_jxe_sha256': JXE_SHA, 'converted_jar_sha256': sha(a.stock_jar.read_bytes()),
                'converted_content_sha256': STOCK_CONTENT_SHA, 'factory_classes': CLASSES,
                'sources': {n: sha((HERE / 'bridge' / n).read_bytes()) for n in (*RUNTIME, 'PatchLive.java', 'TestLive.java')},
                'integration': verification}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'jar': str(jar), 'size': jar.stat().st_size, 'sha256': manifest['jar_sha256'], **verification}))


if __name__ == '__main__': main()
