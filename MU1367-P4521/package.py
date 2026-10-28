#!/usr/bin/env python3
"""Package the immutable MU1367 v1.4.0 payload with a P4521 installation path.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / 'MU1367/port'))
from firmware import sha

BASE = REPO / 'releases/MU1367/v1.4.0/CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip'
BASE_SHA = '942c9d2a1b38e7f417f97e1a8806e42559b29565f3605215c92b932d58c1259f'
ARCHIVE = 'CarPlay_Maps_VC_MU1367_P4521_791_v1.4.0_Experimental.zip'


def package(inputs, output):
    factory = json.loads((HERE / 'FACTORY.json').read_text())
    evidence = json.loads((inputs / 'metadata.json').read_text())
    if evidence['firmware'] != factory['firmware']:
        raise ValueError('P4521 extraction evidence required')
    for variant in ('50', '70'):
        if evidence['variants'][variant] != {key: factory[key] for key in ('files', 'stage1_runtime', 'stage2_runtime')}:
            raise ValueError('Both exact firmware variants must pass verification')
    for name, record in factory['files'].items():
        data = (inputs / name).read_bytes()
        if sha(data) != record['sha256'] or len(data) != record['size']:
            raise ValueError('Extracted input changed: ' + name)
    if sha(BASE.read_bytes()) != BASE_SHA:
        raise ValueError('Exact published v1.4.0 ZIP required')
    output.mkdir(parents=True, exist_ok=False)
    stage = output / 'sd-card'
    stage.mkdir()
    with zipfile.ZipFile(BASE) as archive:
        for item in archive.infolist():
            path = Path(item.filename)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive member')
            dest = stage / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if item.is_dir():
                dest.mkdir(exist_ok=True)
            else:
                dest.write_bytes(archive.read(item))
                dest.chmod((item.external_attr >> 16) & 0o777 or 0o644)
    separate = stage / 'Custom/carplay_mu1367_p4521'
    separate.mkdir()
    shutil.copy2(HERE / '791_AID12.3/install.sh', separate / 'install.sh')
    shutil.copy2(HERE / 'FACTORY.json', separate / 'FACTORY.json')
    scripts = stage / 'Toolbox/scripts'
    # A dedicated first step checks all OEM originals before calling the exact
    # released base installer. Subsequent transactional controllers are unchanged.
    (scripts / 'cpmap_install_791.sh').write_text('''#!/bin/ksh
for V in ${CPMAP_TEST_MEDIA:-/fs/sda0 /fs/sdb0 /net/mmx/fs/sda0 /net/mmx/fs/sdb0}; do
 if [ -s "$V/Custom/carplay_mu1367_p4521/install.sh" ]; then
  exec /bin/ksh "$V/Custom/carplay_mu1367_p4521/install.sh" "$V/Custom/carplay_maps_vc"
 fi
done
echo MU1367_P4521_MATCHING_SD_REQUIRED
exit 1
''')
    # Keep the existing menu path present but explicitly refuse unsupported 790.
    (scripts / 'cpmap_install_790.sh').write_text('#!/bin/ksh\necho MU1367_P4521_RELEASE_REQUIRES_791\nexit 1\n')
    menu = stage / 'Toolbox/GEM/carplay-maps-vc.esd'
    text = menu.read_text().replace('MU1367 settings v2 test -', 'MU1367 P4521 v1.4.0 experimental -')
    text = text.replace('Install MU1367 / 791', 'Install MU1367 P4521 / 791')
    text = text.replace('790 video ONLY (experimental, no native adapter)', '790 unsupported in P4521 release')
    menu.write_text(text)
    for name in ('README.md', 'INSTALL.md'):
        shutil.copy2(HERE / name, stage / ('MU1367_P4521_' + name))
    # The inherited source/docs remain an immutable historical baseline; put
    # the supported firmware and current instructions first in every SD guide.
    for doc in stage.glob('MU1367_*.md'):
        if not doc.name.startswith('MU1367_P4521_'):
            doc.write_text('P4521 experimental v1.4.0 bundle: read `MU1367_P4521_INSTALL.md` first. '
                           'The following document is inherited from the K4525 baseline; '
                           'P4521 support is verified separately in `Custom/carplay_mu1367_p4521/FACTORY.json`.\n\n' + doc.read_text())
    source = separate / 'source'
    shutil.copytree(HERE, source, ignore=shutil.ignore_patterns('build-*', '__pycache__', 'VERIFICATION.json'))
    for script in [separate / 'install.sh', scripts / 'cpmap_install_791.sh', scripts / 'cpmap_install_790.sh']:
        script.chmod(0o755)
        subprocess.run(['/bin/ksh', '-n', str(script)], check=True)
    manifest = {'firmware': factory['firmware'], 'cluster': '791', 'version': '1.4.0-p4521-experimental',
                'baseline_tag': factory['baseline_tag'], 'baseline_commit': factory['baseline_commit'],
                'baseline_archive_sha256': BASE_SHA, 'factory': factory, 'firmware_verification': evidence,
                'runtime_payloads_and_controllers_unchanged': True, 'on_unit_validated': False,
                'source_sha256': {str(f.relative_to(source)): sha(f.read_bytes()) for f in sorted(source.rglob('*')) if f.is_file()}}
    (separate / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(output / ARCHIVE, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(stage.rglob('*')):
            if file.is_file():
                archive.write(file, file.relative_to(stage))
    manifest['archive_sha256'] = sha((output / ARCHIVE).read_bytes())
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'SHA256SUMS.txt').write_text(manifest['archive_sha256'] + '  ' + ARCHIVE + '\n')
    print(json.dumps({'archive': str(output / ARCHIVE), 'sha256': manifest['archive_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    package(args.inputs, args.output)
