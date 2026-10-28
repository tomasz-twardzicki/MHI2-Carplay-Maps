#!/usr/bin/env python3
"""Build a full toolbox for N0 after matching host/controller/factory-J9 checks.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zipfile

from package_support import controller, scripts, menu, JAR, PAYLOAD

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / 'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hmi', type=Path, required=True)
    p.add_argument('--qnx-result', type=Path, required=True)
    p.add_argument('--controls-result', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--phase', choices=('N0', 'N1'), default='N0')
    a = p.parse_args()
    phase = a.phase
    jar_name = JAR if phase == 'N0' else 'CarPlayNowPlayingTextN1.jar'
    payload_name = PAYLOAD if phase == 'N0' else 'Custom/carplay_audio_n1'
    hmi = json.loads((a.hmi / 'manifest.json').read_text())
    qnx = json.loads(a.qnx_result.read_text())
    controls = json.loads(a.controls_result.read_text())
    jar = (a.hmi / jar_name).read_bytes()
    require(sha(jar) == hmi['jar_sha256'] == qnx['jar_sha256'] == controls['jar_sha256'], 'JAR verification mismatch')
    require(qnx['passed'] and qnx['factory_j9_verified'] and qnx['class49_negative_rejected'], 'factory J9 checks required')
    require(controls['passed'] and hmi['host'].get('observer_assertions', hmi['host'].get('text_assertions', 0)) >= 30, 'host/controller checks required')
    for name, digest in hmi['sources'].items():
        path = HERE / ('java/' + name if phase == 'N0' else name)
        require(sha(path.read_bytes()) == digest, 'stale HMI source: ' + name)
    for name, digest in controls['sources'].items():
        require(sha((HERE / name).read_bytes()) == digest, 'stale controller source: ' + name)
    for path, digest in [('test-observer-qnx.py', qnx['test_sha256']), (hmi.get('probe_source', 'java/LoadObserver.java'), qnx['probe_sha256'])]:
        require(sha((HERE / path).read_bytes()) == digest, 'stale QNX check: ' + path)
    with zipfile.ZipFile(a.hmi / jar_name) as z:
        names = z.namelist()
        require(all(struct.unpack_from('>H', z.read(n), 6)[0] == 46 for n in names), 'class major must be 46')
        target = 'de/vw/mib/asl/internal/carplay/target/HsmTarget.class'
        targets = {target}
        if phase == 'N1':
            targets.add('de/vw/mib/bap/mqbab2/audiosd/functions/CurrentStationInfo.class')
        require(targets.issubset(names) and all(n in targets or n.startswith('com/cpmap/audio/') for n in names), 'unexpected installed class')
    # Detect target replacement conflicts in the supplied baseline bundle.
    for other in BASE.rglob('*.jar'):
        with zipfile.ZipFile(other) as z:
            require(not targets.intersection(z.namelist()), 'baseline target conflict: ' + str(other))
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out / 'sd-card'
    shutil.copytree(BASE, stage, ignore=shutil.ignore_patterns('.DS_Store', '__pycache__'))
    payload = stage / payload_name
    payload.mkdir()
    (payload / jar_name).write_bytes(jar)
    (payload / 'VERSION').write_text(hmi['build_id'] + '\n')
    common = controller(hmi['build_id'], len(jar), phase=phase)
    script_dir = stage / 'Toolbox/scripts'
    rendered = {'cpmap_audio_' + phase.lower() + '.sh': common,
                **{'cpmap_audio_' + phase.lower() + '_' + action + '.sh': text for action, text in scripts(phase=phase).items()}}
    for name, text in rendered.items():
        (script_dir / name).write_text(text)
        (script_dir / name).chmod(0o755)
    gem = stage / 'Toolbox/GEM/carplay-maps-vc.esd'
    original = gem.read_bytes()
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    gem.write_bytes(original + menu(phase=phase).encode().replace(b'\n', newline))
    (stage / ('AUDIO_' + phase + '_TEST.md')).write_bytes((HERE / ('TEST-' + phase + '.md')).read_bytes())
    source = payload / 'source'
    source.mkdir()
    for f in HERE.iterdir():
        if f.is_file() and f.suffix in ('.py', '.sh', '.md', '.json'):
            shutil.copy2(f, source / f.name)
    shutil.copytree(HERE / 'java', source / 'java')
    if (HERE / 'n1').exists():
        shutil.copytree(HERE / 'n1', source / 'n1')
    shutil.copy2(HERE.parents[1] / 'LICENSE', source / 'LICENSE')
    # All existing release files except the appended menu must remain byte-identical.
    baseline_hashes = {}
    for f in BASE.rglob('*'):
        if not f.is_file() or f.name == '.DS_Store' or '__pycache__' in f.parts:
            continue
        rel = f.relative_to(BASE)
        baseline_hashes[str(rel)] = sha(f.read_bytes())
        if str(rel) != 'Toolbox/GEM/carplay-maps-vc.esd':
            require((stage / rel).read_bytes() == f.read_bytes(), 'baseline changed: ' + str(rel))
    record = {'phase': phase + ('-on-unit-observation-test' if phase == 'N0' else '-native-text-test'), 'build_id': hmi['build_id'],
              'jar_sha256': sha(jar), 'cluster_output': phase == 'N1', 'cover_output': False, 'on_unit_validated': False,
              'installer_included': True,
              'hmi': hmi, 'qnx': qnx, 'controls': controls,
              'rendered_scripts': {n: sha(t.encode()) for n, t in rendered.items()},
              'baseline_files_sha256': baseline_hashes,
              'source_sha256': {str(f.relative_to(source)): sha(f.read_bytes()) for f in source.rglob('*') if f.is_file()}}
    (payload / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    archive = out / ('CarPlay_Maps_VC_MU1427_Audio_' + phase + '_Test.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob('*')):
            if f.is_file():
                info = zipfile.ZipInfo(str(f.relative_to(stage)), (2026, 10, 19, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100000 | (f.stat().st_mode & 0o777)) << 16
                z.writestr(info, f.read_bytes())
    digest = sha(archive.read_bytes())
    (out / 'SHA256SUMS.txt').write_text(digest + '  ' + archive.name + '\n')
    (out / 'manifest.json').write_text(json.dumps({'archive_sha256': digest, **record}, indent=2) + '\n')
    print(json.dumps({'archive': str(archive), 'sha256': digest, 'build_id': hmi['build_id']}))


if __name__ == '__main__':
    main()
