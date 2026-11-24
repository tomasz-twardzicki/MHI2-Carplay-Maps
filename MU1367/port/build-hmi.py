#!/usr/bin/env python3
"""Build firmware-pinned MU1367 guidance and audio text adapters.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import zipfile
from firmware import sha, JXE_SHA

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RG = REPO / 'MU1427/route-guidance'
AUDIO = REPO / 'MU1427/now-playing'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('java-home', 'stock-jar', 'jxe', 'asm-dir', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    factory = json.loads((HERE / 'FACTORY.json').read_text())
    baseline = load('guidance_builder', RG / 'build-live-bridge.py')
    if sha(a.jxe.read_bytes()) != JXE_SHA or baseline.stock_content(a.stock_jar) != factory['stock_content_sha256']:
        p.error('exact MU1367 JXE and pinned converted classes required')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    java, javac = (str(a.java_home / 'bin' / n) for n in ('java', 'javac'))
    stock = str(a.stock_jar.resolve())
    asm = ':'.join(str((a.asm_dir / n).resolve()) for n in ('asm-9.7.jar', 'asm-tree-9.7.jar'))
    sources = {}

    def source(path):
        sources[str(path.relative_to(REPO))] = sha(path.read_bytes())
        return str(path)

    results = {}
    for feature in ('guidance', 'audio'):
        work = out / feature
        for sub in ('stock', 'helpers', 'tools', 'patched', 'tests', 'generated'):
            (work / sub).mkdir(parents=True)
        names = [n for n in factory['classes'] if ('/navsd/' in n) == (feature == 'guidance')]
        with zipfile.ZipFile(a.stock_jar) as z:
            for name in names:
                raw = z.read(name)
                if sha(raw) != factory['classes'][name]:
                    p.error('factory class mismatch: ' + name)
                dest = work / 'stock' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
        src = RG / 'bridge' if feature == 'guidance' else AUDIO / 'n1/java'
        runtime = baseline.RUNTIME if feature == 'guidance' else ('TextModel.java', 'TextBridge.java')
        source_bytes = b''.join((src / n).read_bytes() for n in runtime)
        build_id = 'MU1367-' + feature + '-' + sha(source_bytes + bytes.fromhex(JXE_SHA))[:12]
        package = 'rgi' if feature == 'guidance' else 'audio'
        info = work / 'generated/BuildInfo.java'
        info.write_text('package com.cpmap.' + package + '; public final class BuildInfo { public static final String ID="' + build_id + '"; public static final boolean RELEASE=true; }\n')
        subprocess.run([javac, '-source', '7', '-target', '7', '-Xlint:-options', '-bootclasspath', stock,
                        '-cp', stock, '-d', str(work / 'helpers'), *(source(src / n) for n in runtime), str(info)], check=True)
        if feature == 'guidance':
            subprocess.run([javac, '-cp', asm, '-d', str(work / 'tools'), source(src / 'PatchLive.java')], check=True)
            subprocess.run([java, '-cp', str(work / 'tools') + ':' + asm, 'PatchLive',
                            str(work / 'stock'), str(work / 'helpers'), str(work / 'patched')], check=True)
            test = 'TestLive'
        else:
            patcher = work / 'generated/PatchTextObserver.java'
            source(AUDIO / 'java/PatchObserver.java')
            patcher.write_text((AUDIO / 'java/PatchObserver.java').read_text().replace('PatchObserver', 'PatchTextObserver').replace('com/cpmap/audio/NowPlayingObserver', 'com/cpmap/audio/TextBridge'))
            subprocess.run([javac, '-cp', asm, '-d', str(work / 'tools'), str(patcher), source(src / 'PatchText.java')], check=True)
            for tool, name, extra in [('PatchTextObserver', names[0], [str(work / 'helpers')]), ('PatchText', names[1], [])]:
                subprocess.run([java, '-cp', str(work / 'tools') + ':' + asm, tool,
                                str(work / 'stock' / name), *extra, str(work / 'patched')], check=True)
            test = 'TestText'
        jar = out / ('CarPlayMU1367' + feature.title() + '.jar')
        with zipfile.ZipFile(jar, 'w') as z:
            for file in sorted((work / 'patched').rglob('*.class')):
                raw = file.read_bytes()
                if struct.unpack_from('>H', raw, 6)[0] != 46:
                    p.error('every installed class must target major 46')
                entry = zipfile.ZipInfo(str(file.relative_to(work / 'patched')), (2026, 10, 27, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                z.writestr(entry, raw)
        subprocess.run([javac, '-cp', str(jar) + ':' + stock, '-d', str(work / 'tests'), source(src / (test + '.java'))], check=True)
        result = subprocess.run([java, '-Xverify:all', '-cp', str(work / 'tests') + ':' + str(jar) + ':' + stock,
                                 'com.cpmap.' + package + '.' + test], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        results[feature] = {'build_id': build_id, 'jar': jar.name, 'sha256': sha(jar.read_bytes()),
                            'size': jar.stat().st_size, 'host': json.loads(result.stdout)}
    # Rebuild the navigation-active HMI patch from this firmware too. Keep
    # the proven rev-3 behavior: no ChangeDataRate / stream-state override.
    nai = REPO / 'MU1427/NavActiveIgnore'
    work = out / 'navignore'
    for sub in ('stock', 'helpers', 'tools', 'patched', 'generated'):
        (work / sub).mkdir(parents=True)
    with zipfile.ZipFile(a.stock_jar) as z:
        for name, digest in factory['nav_ignore_classes'].items():
            raw = z.read(name)
            if sha(raw) != digest:
                p.error('factory NAI class mismatch')
            file = work / 'stock' / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
    helper = nai / 'src/de/vw/mib/navactiveignore/NavActiveIgnore.java'
    subprocess.run([javac, '-source', '7', '-target', '7', '-Xlint:-options', '-bootclasspath', stock,
                    '-cp', stock, '-d', str(work / 'helpers'), source(helper)], check=True)
    patcher = work / 'generated/Patch.java'
    source(nai / 'patcher/Patch.java')
    # Exact MU1367 javap: smartphone-navigation-active properties are
    # CarPlay 2910009 and Android Auto 2910005 (MU1427: 3010002 / 3110002).
    patcher.write_text((nai / 'patcher/Patch.java').read_text()
                      .replace('3010002', '2910009').replace('3110002', '2910005')
                      .replace('ClassWriter cw =', 'cn.version = Opcodes.V1_2; ClassWriter cw ='))
    subprocess.run([javac, '-cp', asm, '-d', str(work / 'tools'), str(patcher)], check=True)
    subprocess.run([java, '-cp', str(work / 'tools') + ':' + asm, 'Patch', str(work / 'stock'),
                    str(work / 'helpers'), str(work / 'patched')], check=True)
    jar = out / 'CarPlayMU1367NavIgnore.jar'
    with zipfile.ZipFile(jar, 'w') as z:
        for file in sorted((work / 'patched').rglob('*.class')):
            raw = file.read_bytes()
            if struct.unpack_from('>H', raw, 6)[0] != 46:
                p.error('NAI class must target 46')
            entry = zipfile.ZipInfo(str(file.relative_to(work / 'patched')), (2026, 10, 27, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, raw)
    results['navignore'] = {'jar': jar.name, 'sha256': sha(jar.read_bytes()), 'size': jar.stat().st_size,
                            'stock_pattern_assertions_passed': True, 'stream_state_override': False}
    seen = set()
    for feature in results.values():
        with zipfile.ZipFile(out / feature['jar']) as z:
            if seen & set(z.namelist()):
                raise ValueError('overlapping adapter classes')
            seen.update(z.namelist())
    manifest = {'firmware': factory['firmware'], 'jxe_sha256': JXE_SHA,
                'converted_content_sha256': factory['stock_content_sha256'], 'class_major': 46,
                'features': results, 'sources': sources, 'factory_j9_verified': False, 'on_unit_validated': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(results))


if __name__ == '__main__':
    main()
