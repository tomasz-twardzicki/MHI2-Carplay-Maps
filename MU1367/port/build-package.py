#!/usr/bin/env python3
"""Assemble a separate MU1367 test toolbox; never updates published payloads.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import zipfile
from firmware import sha, JXE_SHA

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / 'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4'


def render(payload):
    names = {'driver': 'ipod-drvr-iap2-B4.so', 'config': 'iap2.cfg',
             'guidance': 'CarPlayMU1367Guidance.jar', 'audio': 'CarPlayMU1367Audio.jar', 'navignore': 'CarPlayMU1367NavIgnore.jar',
             'reader': 'rgi-observer', 'capture': 'artwork-capture'}
    values = {'H_JXE': JXE_SHA, 'H_STOCK_DRIVER': '7149a3e75b1b19e89021841759f420a6eced456b6c697a3dd1f0e436abea0b8c',
              'H_STOCK_CONFIG': '88a4d24f5c50b181d73429fb585ad6b38d10daca67c5b5a9798ef17f84208bbe',
              'H_N3': sha((payload / 'ipod-drvr-iap2-N3.so').read_bytes())}
    for key, name in names.items():
        values['N_' + key] = name
        values['H_' + key] = sha((payload / name).read_bytes())
    build = 'MU1367-integration-' + sha(json.dumps(values, sort_keys=True).encode())[:12]
    hashes = '\n'.join(k + '=' + shlex.quote(v) for k, v in values.items())
    controller = (HERE / 'control.sh').read_text().replace('@BUILD@', shlex.quote(build)).replace('@HASHES@', hashes)
    return build, controller


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('hmi', 'native', 'display', 'inputs', 'qnx', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--b4', type=Path, required=True)
    p.add_argument('--n3', type=Path, required=True)
    a = p.parse_args()
    qnx = json.loads((a.qnx / 'result.json').read_text())
    hmi = json.loads((a.hmi / 'manifest.json').read_text())
    native = json.loads((a.native / 'manifest.json').read_text())
    if not qnx['passed'] or qnx['hmi'] != hmi['features'] or qnx['native'] != native['binaries']:
        p.error('passing runtime verification for these exact artifacts required')
    for name, digest in hmi['sources'].items():
        if sha((REPO / name).read_bytes()) != digest:
            p.error('HMI source changed since build: ' + name)
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out / 'sd-card'
    shutil.copytree(BASE, stage, ignore=shutil.ignore_patterns('.DS_Store', 'carplay_native_guidance', 'carplay_audio_n0', 'carplay_audio_n1', 'carplay_artwork_n2', 'carplay_artwork_n3'))
    payload = stage / 'Custom/carplay_mu1367'
    payload.mkdir()
    for feature in hmi['features'].values():
        file = a.hmi / feature['jar']
        if sha(file.read_bytes()) != feature['sha256']:
            p.error('HMI payload changed')
        shutil.copy2(file, payload / file.name)
    for name, info in native['binaries'].items():
        file = a.native / name
        if sha(file.read_bytes()) != info['sha256']:
            p.error('native payload changed')
        shutil.copy2(file, payload / name)
    for file, name in ((a.b4, 'ipod-drvr-iap2-B4.so'), (a.n3, 'ipod-drvr-iap2-N3.so')):
        record = json.loads(file.with_suffix('.json').read_text())
        if sha(file.read_bytes()) != record['sha256'] or not record['identical_program_segments']:
            p.error('driver verification mismatch')
        shutil.copy2(file, payload / name)
    config = (a.inputs / 'iap2.cfg').read_bytes()
    if sha(config) != '88a4d24f5c50b181d73429fb585ad6b38d10daca67c5b5a9798ef17f84208bbe' or b'[ident]' in config:
        p.error('exact MU1367 accessory configuration required')
    (payload / 'iap2.cfg').write_bytes(config + b'# MU1367 native route guidance\n[ident]\nsendmsgs=0x5200,0x5203\nrecvmsgs=0x5201,0x5202,0x5204\n')
    build, controller = render(payload)
    (payload / 'VERSION').write_text(build + '\n')
    (payload / 'control.sh').write_text(controller)
    (payload / 'control.sh').chmod(0o755)
    subprocess.run(['/bin/ksh', '-n', str(payload / 'control.sh')], check=True)
    maps = stage / 'Custom/carplay_maps_vc'
    for cluster in ('791', '790'):
        for file in (a.display / cluster).rglob('core.so'):
            target = maps / 'tuning/MU1367' / cluster / file.parent.name / 'core.so'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
        shutil.copy2(a.display / cluster / 'default/core.so', maps / ('payload/profiles/MU1367/' + cluster + '/core.so'))
    scripts = stage / 'Toolbox/scripts'
    # Remove obsolete MU1427 guidance entry points from this isolated test bundle.
    for file in scripts.glob('cpmap_guidance*.sh'):
        file.unlink()
    prefix = '''#!/bin/ksh
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
P=""
for V in /fs/sda0 /fs/sdb0 /net/mmx/fs/sda0 /net/mmx/fs/sdb0; do
    if [ -s "$V/Custom/carplay_mu1367/VERSION" ]; then P=$V/Custom/carplay_mu1367; break; fi
done
S=$M/mnt/app/carplay-mu1367/control.sh
'''
    entries = [('cpmap_install_791.sh', '1. Install MU1367 / 791 video (reboot after step 2)'),
               ('cpmap_install_790.sh', '790 video ONLY (experimental, no native adapter)')]
    for action, label in [('install', '2. Install MU1367 / 791 guidance + audio text'), ('status', 'MU1367 integration status'),
                          ('disable', 'Disable native guidance until reboot'), ('uninstall', 'Remove integration; retain video (reboot)'),
                          ('recover', 'Recover interrupted integration (reboot)'), ('artwork-on', 'Experimental N3 capture ON (reboot)'),
                          ('artwork-off', 'Experimental N3 capture OFF (reboot)')]:
        text = prefix
        if action == 'install':
            text += '[ -n "$P" ] || exit 1\nS=$P/control.sh\n'
        text += '/bin/ksh "$S" ' + action + ' "$P"\n'
        name = 'cpmap_mu1367_' + action + '.sh'
        (scripts / name).write_text(text)
        (scripts / name).chmod(0o755)
        entries.append((name, label))
    entries += [('cpmap_diag.sh', 'Collect diagnostics before reboot'), ('cpmap_restore.sh', 'Restore factory video + integration (reboot)')]
    menu = 'screen carplay-maps-vc Customization\n\nkeyValue\n    value String sys 0x00000000 0\n    label "MU1367 test - omonob / tomasz-twardzicki"\n    poll 0\n'
    for name, label in entries:
        menu += '\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/' + name + '"\n    label "' + label + '"\n'
    (stage / 'Toolbox/GEM/carplay-maps-vc.esd').write_text(menu)
    tune = scripts / 'cpmap_tune.sh'
    tune.write_text(tune.read_text().replace('MU1427/791)', 'MU1367/791|MU1367/790)'))
    tuning = stage / 'Toolbox/GEM/carplay-maps-vc-tuning.esd'
    tuning.write_text(tuning.read_text().replace('MU1427 / 791 only', 'MU1367 / 791 and 790 test'))
    with tuning.open('a') as f:
        for variant in ('stock-40fps', 'low-card'):
            name = 'cpmap_tune_' + variant + '.sh'
            (scripts / name).write_text('#!/bin/ksh\n/bin/ksh /mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_tune.sh ' + variant + '\n')
            (scripts / name).chmod(0o755)
            f.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/' + name + '"\n    label "' + variant + ' (low-card: 790 only)"\n')
    # Never let a later base reinstallation discard integration recovery state.
    guard = '''M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
if [ -s "$M/mnt/app/carplay-mu1367/STATE" ] && [ "$(cat "$M/mnt/app/carplay-mu1367/STATE")" != removed ]; then
    echo MU1367_REMOVE_INTEGRATION_AND_REBOOT_BEFORE_BASE_INSTALL; exit 1
fi
'''
    for name in ('cpmap_install_791.sh', 'cpmap_install_790.sh'):
        file = scripts / name
        file.write_text(file.read_text().replace('#!/bin/ksh\n', '#!/bin/ksh\n' + guard, 1))
    restore = scripts / 'cpmap_restore.sh'
    restore.write_text(restore.read_text().replace('G=$M/mnt/app/carplay-route-guidance', '''U=$M/mnt/app/carplay-mu1367
if [ -s "$U/STATE" ] && [ "$(cat "$U/STATE")" != removed ]; then
    /bin/ksh "$U/control.sh" uninstall || exit $?
fi
G=$M/mnt/app/carplay-route-guidance'''))
    for name in ('INSTALL.md', 'README.md'):
        if (HERE / name).exists():
            shutil.copy2(HERE / name, stage / ('MU1367_' + name))
    source = payload / 'source'
    source.mkdir()
    # The source snapshot is complete enough to restore in the repository tree.
    for relative in ('MU1367/port', 'MU1367/790_AID10.5/tuning', 'MU1427/route-guidance', 'MU1427/now-playing', 'MU1427/NavActiveIgnore'):
        def ignore(directory, names):
            return [n for n in names if n in ('__pycache__', '.DS_Store') or n.endswith('.zip')
                    or Path(directory).resolve() == HERE and n == 'VERIFICATION.json'
                    or n.startswith('build') and (not n.endswith('.py') or (Path(directory) / n).is_dir())]
        shutil.copytree(REPO / relative, source / relative, ignore=ignore)
    shutil.copy2(REPO / 'LICENSE', source / 'LICENSE')
    manifest = {'build_id': build, 'firmware': 'MU1367', 'cluster': '791', 'on_unit_validated': False,
                'artwork_enabled_by_default': False, 'cluster_picture_output': False,
                'hmi': hmi, 'native': native, 'qnx': qnx,
                'firmware_inputs': json.loads((a.inputs / 'metadata.json').read_text()),
                'display': json.loads((a.display / 'manifest.json').read_text())}
    (payload / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = out / 'CarPlay_Maps_VC_MU1367_791_Integration_Test.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(stage.rglob('*')):
            if file.is_file():
                z.write(file, file.relative_to(stage))
    manifest['archive_sha256'] = sha(archive.read_bytes())
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'SHA256SUMS.txt').write_text(manifest['archive_sha256'] + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'sha256': manifest['archive_sha256']}))


if __name__ == '__main__':
    main()
