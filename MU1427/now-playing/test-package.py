#!/usr/bin/env python3
"""Verify the produced ZIP, its source/payload identity and install/remove behavior.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

from package_support import controller, menu, scripts, JAR, PAYLOAD

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / 'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='audio-n0-package-') as tmp, zipfile.ZipFile(a.archive) as z:
        phase = 'N1' if 'Custom/carplay_audio_n1/manifest.json' in z.namelist() else 'N0'
        jar_name = JAR if phase == 'N0' else 'CarPlayNowPlayingTextN1.jar'
        payload_name = PAYLOAD if phase == 'N0' else 'Custom/carplay_audio_n1'
        work = Path(tmp)
        names = z.namelist()
        assert len(set(names)) == len(names) and z.testzip() is None
        assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names)
        manifest = json.loads(z.read(payload_name + '/manifest.json'))
        jar = z.read(payload_name + '/' + jar_name)
        assert sha(jar) == manifest['jar_sha256']
        assert manifest['installer_included'] and manifest['cluster_output'] == (phase == 'N1') and not manifest['on_unit_validated']
        baseline_checked = 0
        for name, digest in manifest['baseline_files_sha256'].items():
            if name == 'Toolbox/GEM/carplay-maps-vc.esd':
                original = (BASE / name).read_bytes()
                assert sha(original) == digest
                newline = b'\r\n' if b'\r\n' in original else b'\n'
                assert z.read(name) == original + menu(phase=phase).encode().replace(b'\n', newline)
            else:
                assert sha(z.read(name)) == digest, name
                baseline_checked += 1
        rendered = {'cpmap_audio_' + phase.lower() + '.sh': controller(manifest['build_id'], len(jar), phase=phase),
                    **{'cpmap_audio_' + phase.lower() + '_' + action + '.sh': text for action, text in scripts(phase=phase).items()}}
        for name, text in rendered.items():
            assert z.read('Toolbox/scripts/' + name) == text.encode()
            assert sha(text.encode()) == manifest['rendered_scripts'][name]
            path = work / name
            path.write_text(text)
            subprocess.run(['/bin/ksh', '-n', str(path)], check=True)
        for name, digest in manifest['source_sha256'].items():
            assert sha(z.read(payload_name + '/source/' + name)) == digest, name
        # Test installation/removal with the actual archived JAR.
        hmi = work / 'hmi'
        hmi.mkdir()
        (hmi / jar_name).write_bytes(jar)
        (hmi / 'manifest.json').write_text(json.dumps(manifest['hmi']))
        controls_result = work / 'controls.json'
        subprocess.run(['python3', str(HERE / 'test-controls.py'), str(hmi),
                        '--phase', phase, '--output', str(controls_result)], check=True)
        controls = json.loads(controls_result.read_text())
        assert controls['passed'] and controls['jar_sha256'] == manifest['jar_sha256']
        # Verification failures must stop the builder before staging a bundle.
        qnx = work / 'qnx.json'
        qnx.write_text(json.dumps(manifest['qnx']))
        bad_controls = work / 'bad-controls.json'
        bad_controls.write_text(json.dumps({**manifest['controls'], 'passed': False}))
        destination = work / 'must-not-exist'
        refused = subprocess.run(['python3', str(HERE / 'build-test-package.py'), '--hmi', str(hmi),
            '--qnx-result', str(qnx), '--controls-result', str(bad_controls), '--phase', phase, '--output', str(destination)],
            capture_output=True, text=True)
        assert refused.returncode != 0 and not destination.exists()
        result = {'passed': True, 'archive_sha256': sha(a.archive.read_bytes()),
                  'jar_sha256': manifest['jar_sha256'], 'baseline_files_preserved': baseline_checked,
                  'controller_cases_against_archived_jar': controls['tests'],
                  'unverified_package_refused': True, 'on_unit_validated': False,
                  'test_sha256': sha(Path(__file__).read_bytes())}
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
