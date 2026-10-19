#!/usr/bin/env python3
"""Add a verified, manually enabled D1 HMI bridge to the unchanged C4 toolbox.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import zipfile

HERE = Path(__file__).resolve().parent
C4_SHA = 'df73c26271ab7b6ed265a814cd03bc0f4e802984f6c010141ec8ba9cee08eff3'
READER_SHA = '603b9a148ca6ff15fdc332d89b2b97c7987489b8ca5c60dbabcebd9005860fb8'


def sha(b): return hashlib.sha256(b).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('hmi_build', type=Path)
    p.add_argument('--c4-zip', type=Path, default=HERE / 'build-C4/MU1427-route-guidance-C4-toolbox.zip')
    p.add_argument('--controls-result', type=Path, default=HERE / 'build-D1-control-verification.json')
    p.add_argument('--qnx-result', type=Path, required=True)
    p.add_argument('--profile', choices=('D1-r2', 'D2', 'D3'), default='D3')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    manifest = json.loads((a.hmi_build / 'manifest.json').read_text())
    runtime = json.loads((a.hmi_build / 'runtime-verification.json').read_text())
    controls = json.loads(a.controls_result.read_text())
    qnx = json.loads(a.qnx_result.read_text())
    jar = (a.hmi_build / 'CarPlayRouteGuidanceD1.jar').read_bytes()
    if sha(jar) != manifest['jar_sha256'] or manifest['jar_sha256'] != runtime['jar_sha256'] or not runtime['passed']:
        p.error('passing exact-JAR runtime verification required')
    if runtime['test_sha256'] != sha((HERE / 'test-live-bridge.py').read_bytes()) or runtime['builder_sha256'] != sha((HERE / 'build-live-bridge.py').read_bytes()):
        p.error('runtime test/builder changed; rerun verification')
    if (not qnx['passed'] or not qnx['qnx_actual_firmware_j9'] or qnx['jar_sha256'] != sha(jar)
            or qnx['test_sha256'] != sha((HERE / 'test-live-qnx.py').read_bytes())
            or qnx['probe_sha256'] != sha((HERE / 'bridge/LoadProbe.java').read_bytes())):
        p.error('passing actual firmware-J9 regression of this exact JAR required')
    with zipfile.ZipFile(a.hmi_build / 'CarPlayRouteGuidanceD1.jar') as z:
        if any(struct.unpack_from('>H', z.read(n), 6)[0] != 46 for n in z.namelist() if n.endswith('.class')):
            p.error('unsupported installed class version')
    for n, digest in manifest['sources'].items():
        if sha((HERE / 'bridge' / n).read_bytes()) != digest: p.error('HMI source changed; rebuild and retest')
    if not controls['passed'] or controls['controller_sha256'] != sha((HERE / 'bridge/control.sh').read_bytes()) or controls['test_sha256'] != sha((HERE / 'test-live-control.py').read_bytes()):
        p.error('passing current closed-PATH control tests required')
    if sha(a.c4_zip.read_bytes()) != C4_SHA: p.error('exact tested C4 seed required')
    allow_live = a.profile in ('D2', 'D3')
    out = (a.output or HERE / ('build-' + a.profile)).resolve(); out.mkdir(parents=True, exist_ok=False)
    stage = out / 'sd-card'; stage.mkdir()
    with zipfile.ZipFile(a.c4_zip) as z: z.extractall(stage)
    payload = stage / 'Custom/route_guidance_d1'; payload.mkdir()
    reader = (stage / 'Custom/route_guidance_c4/rgi-observer').read_bytes()
    if sha(reader) != READER_SHA or len(reader) != 16333: p.error('C4 reader identity mismatch')
    (payload / 'rgi-observer').write_bytes(reader); (payload / 'rgi-observer').chmod(0o755)
    (payload / 'CarPlayRouteGuidanceD1.jar').write_bytes(jar)
    build_id = 'MU1427-RGI-' + a.profile + '-' + sha(jar)[:8]
    (payload / 'VERSION').write_text(build_id + '\n')
    hmi_revision = manifest['revision']
    manifest.update(revision=a.profile, hmi_build_revision=hmi_revision, build_id=build_id,
                    seed_c4_sha256=C4_SHA, driver_change=False, reader_sha256=READER_SHA,
                    runtime=runtime, controls=controls, qnx_j9=qnx, default_enabled=False, live_start_allowed=allow_live)
    (payload / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    scripts = stage / 'Toolbox/scripts'
    controller = (HERE / 'bridge/control.sh').read_text()
    for key, value in {'BUILD_ID': build_id, 'JAR_SIZE': str(len(jar)), 'SOURCE_ID': manifest['source_id'], 'ALLOW_LIVE': str(int(allow_live))}.items():
        if controller.count('@' + key + '@') != 1: p.error('unexpected control placeholder')
        controller = controller.replace('@' + key + '@', value)
    (scripts / 'cpmap_rgi_live.sh').write_text(controller); (scripts / 'cpmap_rgi_live.sh').chmod(0o755)
    menu = stage / 'Toolbox/GEM/carplay-maps-vc.esd'; data = menu.read_bytes()
    actions = [('install', 'D1: install native guidance adapter (reboot)'), ('shadow', 'D1: start 5-minute SHADOW test'),
               ('verify', 'D1: verify shadow health'), ('export', 'D1: disable and export capture'),
               ('clear', 'D1: clear RAM capture (export first)'),
               ('disable', 'D1: disable native output NOW'), ('status', 'D1: adapter and recorder status'),
               ('uninstall', 'D1: remove HMI adapter (reboot)')]
    if allow_live:
        actions.insert(5, ('live', 'D1: start 5-minute LIVE arrows and distance'))
    for action, label in actions:
        if allow_live and action == 'verify': label = 'D1: verify healthy shadow before live'
        if a.profile == 'D3' and action == 'live': label = 'D1: start 5-minute LIVE guidance and route totals'
        label = label.replace('D1:', a.profile + ':')
        name = 'cpmap_rgi_d1_' + action + '.sh'
        wrapper = '''#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_live.sh
[ -f "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_live.sh
'''
        if action in ('install', 'shadow', 'live'):
            wrapper += '''for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
    P=$V/Custom/route_guidance_d1
    if [ -s "$P/VERSION" ]; then /bin/ksh "$S" ACTION "$P"; exit $?; fi
done
echo "CPMAP_RGI_D1_FAIL=SD_PAYLOAD_NOT_FOUND"
exit 1
'''.replace('ACTION', action)
        else: wrapper += '/bin/ksh "$S" ' + action + '\n'
        (scripts / name).write_text(wrapper); (scripts / name).chmod(0o755)
        data += f'\r\nscript\r\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/{name}"\r\n    label   "{label}"\r\n'.encode()
    menu.write_bytes(data)
    source = payload / 'source'; source.mkdir()
    for n in ('build-live-bridge.py', 'build-live-package.py', 'test-live-bridge.py', 'test-live-control.py',
              'rgi_bridge.py', 'rgi_maneuver.py', 'rgi_decode.py', 'rgi_publication.py', 'rgi_observer.py',
              'test-rgi-bridge.py', 'test-rgi-publication.py', 'test-observer.py', 'TEST-D1.md', 'LIVE-BRIDGE.md',
              'test-live-qnx.py', 'TEST-D1-r2.md', 'D1-RESULTS.md', 'D1-r2-RESULTS.md', 'TEST-D2.md', 'D2-RESULTS.md', 'TEST-D3.md', 'test-live-package.py'):
        shutil.copy2(HERE / n, source / n)
    shutil.copytree(HERE / 'bridge', source / 'bridge')
    shutil.copy2(HERE.parent.parent / 'LICENSE', source / 'LICENSE')
    # No previous installer, recovery helper, jar, driver or C4 recorder changes.
    with zipfile.ZipFile(a.c4_zip) as z:
        for name in z.namelist():
            if name.endswith('/') or name == 'Toolbox/GEM/carplay-maps-vc.esd': continue
            if (stage / name).read_bytes() != z.read(name): raise ValueError('preserved C4 file changed')
        if not data.startswith(z.read('Toolbox/GEM/carplay-maps-vc.esd')): raise ValueError('menu changed before appended D1 items')
    archive = out / ('MU1427-route-guidance-' + a.profile + '-toolbox.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(stage.rglob('*')):
            if file.is_file(): z.write(file, file.relative_to(stage))
    manifest['archive_sha256'] = sha(archive.read_bytes())
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'SHA256SUMS.txt').write_text(manifest['archive_sha256'] + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'sha256': manifest['archive_sha256'], 'jar_sha256': sha(jar), 'driver_change': False}))


if __name__ == '__main__': main()
