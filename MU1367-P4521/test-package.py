#!/usr/bin/env python3
"""Test P4521 archive, strict preflight, four-layer installation and OEM restore.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('p4521_package', HERE / 'package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
sha = package.sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('package', 'inputs', 'verifier', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    stage = args.package.resolve() / 'sd-card'
    checks = 0

    def check(value, message):
        nonlocal checks
        if not value:
            raise AssertionError(message)
        checks += 1

    archive = args.package / package.ARCHIVE
    check(sha(package.BASE.read_bytes()) == package.BASE_SHA, 'immutable baseline ZIP')
    preserved = 0
    with zipfile.ZipFile(package.BASE) as base, zipfile.ZipFile(archive) as release:
        check(release.testzip() is None, 'archive CRC')
        for item in release.infolist():
            file = stage / item.filename
            check(file.read_bytes() == release.read(item), 'exact archive bytes: ' + item.filename)
            check(file.stat().st_mode & 0o777 == (item.external_attr >> 16) & 0o777, 'archive permissions')
        for name in base.namelist():
            if name.startswith('Custom/'):
                check(base.read(name) == release.read(name), 'unchanged baseline Custom payload: ' + name)
                preserved += 1
    source = stage / 'Custom/carplay_mu1367_p4521/source'
    manifest = json.loads((args.package / 'manifest.json').read_text())
    for name, digest in manifest['source_sha256'].items():
        check(sha((HERE / name).read_bytes()) == digest == sha((source / name).read_bytes()), 'current source snapshot: ' + name)
    scripts = stage / 'Toolbox/scripts'
    for menu in (stage / 'Toolbox/GEM').glob('carplay-maps-vc*.esd'):
        for name in re.findall(r'/eso/hmi/engdefs/scripts/mqb/([^"\s]+)', menu.read_text()):
            check((scripts / name).is_file(), 'menu script exists: ' + name)
            subprocess.run(['/bin/ksh', '-n', str(scripts / name)], check=True)
    with tempfile.TemporaryDirectory(prefix='p4521-package-') as temp:
        root = Path(temp) / 'mmx'
        app = root / 'mnt/app'
        destinations = {'lsd.jxe': 'ifs/lsd.jxe', 'driver': 'mnt/app/armle/lib/dll/ipod-drvr-iap2.so',
                        'iap2.cfg': 'mnt/system/etc/mm/iap2.cfg', 'boot': 'mnt/app/eso/hmi/lsd/lsd.sh',
                        'dio': 'mnt/app/eso/bin/apps/dio_manager', 'libairplay': 'mnt/app/eso/lib/libairplay.so'}
        for name, dest in destinations.items():
            file = root / dest
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.inputs / name, file)
        (root / 'ramdisk').mkdir()
        (app / 'eso/hmi/lsd/jars').mkdir()
        installed = app / 'eso/hmi/engdefs/scripts/mqb'
        shutil.copytree(scripts, installed)
        media = Path(temp) / 'sd'
        shutil.copytree(stage / 'Custom', media / 'Custom', ignore=shutil.ignore_patterns('source'))
        parent = media / 'Custom/carplay_mu1367'
        settings = media / 'Custom/carplay_mu1367_settings'
        lanes = media / 'Custom/carplay_mu1367_lanes'
        for layer in (parent, settings, lanes):
            shutil.copy2(args.verifier, layer / 'verify')
        env = dict(os.environ, CPMAP_TEST_ROOT=str(root), CPMAP_TEST_MEDIA=str(media))

        def snapshot():
            return {str(f.relative_to(root)): (sha(f.read_bytes()), f.stat().st_mode & 0o777)
                    for f in root.rglob('*') if f.is_file()}

        def run(file, *argv, success=True):
            result = subprocess.run(['/bin/ksh', str(file), *map(str, argv)], env=env,
                                    capture_output=True, text=True, timeout=60)
            check((result.returncode == 0) == success, result.stdout + result.stderr)
            return result.stdout

        pristine = snapshot()
        # Each modified original keeps its original size; SHA checks must catch it
        # before any target or backup is created, including modified OEM scripts.
        for name, dest in destinations.items():
            file = root / dest
            original = file.read_bytes()
            changed = bytearray(original)
            changed[-1] ^= 1
            file.write_bytes(changed)
            before = snapshot()
            check('ORIGINAL_HASH_' in run(installed / 'cpmap_install_791.sh', success=False), 'reject modified ' + name)
            check(snapshot() == before, 'preflight rejection writes nothing: ' + name)
            file.write_bytes(original)
        check(snapshot() == pristine, 'negative fixtures restored')
        check('REQUIRES_791' in run(installed / 'cpmap_install_790.sh', success=False), '790 explicitly refused')
        run(installed / 'cpmap_install_791.sh')
        check((app / 'carplaymaps/PROFILE').read_text().strip() == 'MU1367/791', 'unchanged runtime profile')
        # The inherited native wrapper uses physical SD mount paths; exercise
        # its unchanged transaction controller directly in the host fixture.
        run(parent / 'control.sh', 'install', parent)
        run(installed / 'cpmap_settings_install.sh')
        run(installed / 'cpmap_lanes_install.sh')
        for layer in ('carplay-mu1367', 'carplay-mu1367-settings', 'carplay-mu1367-lanes'):
            check((app / layer / 'STATE').read_text().strip() == 'installed', 'installed ' + layer)
        lane_manifest = json.loads((lanes / 'manifest.json').read_text())
        for name, dest in [('CarPlayMU1367Guidance.jar', 'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar'),
                           ('VCMenu.jar', 'eso/hmi/lsd/jars/VCMenu.jar'), ('core.so', 'carplaymaps/core.so')]:
            check(sha((app / dest).read_bytes()) == lane_manifest['runtime']['files'][name], 'exact v1.4.0 runtime: ' + name)
        boot = app / 'eso/hmi/lsd/lsd.sh'
        check(boot.read_text().count('-Xbootclasspath/p:') == 1, 'one boot prepend')
        for name in ('VCMenu', 'CarPlayClusterControls', 'CarPlayMU1367Guidance', 'CarPlayMU1367Audio', 'CarPlayMU1367NavIgnore'):
            check(boot.read_text().count(name + '.jar') == 1, 'single boot JAR: ' + name)
        for action in ('uninstall', 'recover'):
            for layer in ('carplay-mu1367', 'carplay-mu1367-settings'):
                check('LANES_LAYER_FIRST' in run(app / layer / 'control.sh', action, success=False), 'reverse-order guard')
        run(installed / 'cpmap_install_791.sh', success=False)
        # Saved recovery must work after the entire SD bundle disappears.
        shutil.rmtree(media)
        run(installed / 'cpmap_restore.sh')
        for name, dest in destinations.items():
            check((root / dest).read_bytes() == (args.inputs / name).read_bytes(), 'exact P4521 OEM restored: ' + name)
        check(not (app / 'carplaymaps').exists(), 'base video removed')
        for name in ('VCMenu', 'CarPlayClusterControls', 'CarPlayMU1367Guidance', 'CarPlayMU1367Audio', 'CarPlayMU1367NavIgnore'):
            check(not (app / 'eso/hmi/lsd/jars' / (name + '.jar')).exists(), 'OEM JAR absence restored')
        for layer in ('carplay-mu1367', 'carplay-mu1367-settings', 'carplay-mu1367-lanes'):
            check((app / layer / 'STATE').read_text().strip() == 'removed', 'recovery retained: ' + layer)
    result = {'passed': True, 'checks': checks, 'firmware': manifest['firmware'],
              'archive_sha256': sha(archive.read_bytes()), 'baseline_custom_files_unchanged': preserved,
              'all_six_same_size_modified_originals_refused_without_writes': True,
              'four_layer_install_and_no_sd_factory_restore': True,
              'on_unit_validated': False, 'test_sha256': sha(Path(__file__).read_bytes())}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
