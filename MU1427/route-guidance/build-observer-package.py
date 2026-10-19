#!/usr/bin/env python3
"""Add C4 manual recorder controls to the exact tested B4 toolbox archive.

Does not rebuild or alter B4's driver, config, installer or rollback helper.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
B4_ZIP_SHA = '4e42651f0b8d26cb340ddfab299c6b8def45030ef0730cc548c390aefdeeb6a8'


def sha(data): return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native_build', type=Path)
    parser.add_argument('--qnx-result', type=Path, required=True)
    parser.add_argument('--b4-zip', type=Path, default=HERE / 'build-B4/MU1427-route-guidance-B4-toolbox.zip')
    parser.add_argument('--output', type=Path, default=HERE / 'build-C4')
    args = parser.parse_args()
    if sha(args.b4_zip.read_bytes()) != B4_ZIP_SHA: parser.error('exact tested B4 archive required')
    binary = (args.native_build / 'rgi-observer').read_bytes()
    manifest = json.loads((args.native_build / 'manifest.json').read_text())
    if (manifest['revision'], manifest['sha256'], manifest['size']) != ('C4', sha(binary), len(binary)):
        parser.error('native build/manifest mismatch')
    if sha((HERE / 'observer/observer.c').read_bytes()) != manifest['source_sha256']:
        parser.error('reader source changed; rebuild and verify before packaging')
    runtime = json.loads(args.qnx_result.read_text())
    if not runtime['qnx_smoke_passed'] or runtime['reader_sha256'] != sha(binary):
        parser.error('passing QNX check of this exact binary required')
    if runtime['factory_libc_sha256'] != manifest['firmware_libc_sha256']:
        parser.error('QNX check used a different libc')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    stage = out / 'sd-card'; stage.mkdir()
    with zipfile.ZipFile(args.b4_zip) as z: z.extractall(stage)
    payload = stage / 'Custom/route_guidance_c4'; payload.mkdir()
    (payload / 'rgi-observer').write_bytes(binary); (payload / 'rgi-observer').chmod(0o755)
    build_id = 'MU1427-RGI-C4-' + sha(binary)[:8]
    (payload / 'VERSION').write_text(build_id + '\n')
    shutil.copy2(args.native_build / 'manifest.json', payload / 'manifest.json')
    shutil.copy2(args.qnx_result, payload / 'qnx-verification.json')
    scripts = stage / 'Toolbox/scripts'
    controller = (HERE / 'observer/control.sh').read_text()
    if controller.count('@BUILD_ID@') != 1 or controller.count('@BINARY_SIZE@') != 1:
        parser.error('review changed controller placeholders')
    controller = controller.replace('@BUILD_ID@', build_id).replace('@BINARY_SIZE@', str(len(binary)))
    (scripts / 'cpmap_rgi_observer.sh').write_text(controller)
    menu = stage / 'Toolbox/GEM/carplay-maps-vc.esd'
    data = menu.read_bytes()
    for action, label in [('start', 'C4: start 5-minute guidance recorder (RAM)'),
                          ('status', 'C4: guidance recorder status'),
                          ('stop', 'C4: stop guidance recorder'),
                          ('export', 'C4: stop and export guidance recording to SD'),
                          ('remove', 'C4: remove RAM recorder/capture (export first)')]:
        wrapper = '''#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_observer.sh
[ -f "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_observer.sh
'''
        if action == 'start':
            wrapper += '''for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
    P=$V/Custom/route_guidance_c4
    if [ -s "$P/VERSION" ]; then /bin/ksh "$S" start "$P"; exit $?; fi
done
echo "CPMAP_RGI_C4_FAIL=SD_PAYLOAD_NOT_FOUND"
exit 1
'''
        else: wrapper += f'/bin/ksh "$S" {action}\n'
        name = f'cpmap_rgi_c4_{action}.sh'
        (scripts / name).write_text(wrapper); (scripts / name).chmod(0o755)
        data += f'\r\nscript\r\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/{name}"\r\n    label   "{label}"\r\n'.encode()
    (scripts / 'cpmap_rgi_observer.sh').chmod(0o755)
    menu.write_bytes(data)
    source = payload / 'source'; source.mkdir()
    for name in ('build-observer.py', 'build-observer-package.py', 'test-observer.py', 'test-observer-control.py',
                 'test-observer-qnx.py', 'rgi_observer.py', 'rgi_publication.py', 'rgi_decode.py',
                 'test-rgi-publication.py', 'OBSERVER.md', 'TEST-C4.md', 'B4-RESULTS.md'):
        shutil.copy2(HERE / name, source / name)
    shutil.copytree(HERE / 'observer', source / 'observer')
    shutil.copy2(HERE.parent.parent / 'LICENSE', source / 'LICENSE')
    # Assert every preserved B4 payload/recovery byte is unchanged.
    with zipfile.ZipFile(args.b4_zip) as z:
        for name in z.namelist():
            if name.endswith('/') or name == 'Toolbox/GEM/carplay-maps-vc.esd': continue
            if (stage / name).read_bytes() != z.read(name):
                raise ValueError('preserved B4 file changed: ' + name)
    manifest['seed_b4_zip_sha256'] = B4_ZIP_SHA
    manifest['build_id'] = build_id
    manifest['driver_change'] = False
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = out / 'MU1427-route-guidance-C4-toolbox.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(stage))
    digest = sha(archive.read_bytes())
    (out / 'SHA256SUMS.txt').write_text(digest + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'sha256': digest, 'reader_sha256': sha(binary), 'driver_change': False}))


if __name__ == '__main__': main()
