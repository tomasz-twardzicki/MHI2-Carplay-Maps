#!/usr/bin/env python3
"""Check menu wiring and actual video + HMI installation/full rollback order.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from firmware import sha

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('package', 'inputs', 'verifier', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    stage = a.package / 'sd-card'
    scripts = stage / 'Toolbox/scripts'
    payload = stage / 'Custom/carplay_mu1367'
    maps = stage / 'Custom/carplay_maps_vc'
    checks = 0

    def check(ok, message):
        nonlocal checks
        if not ok:
            raise AssertionError(message)
        checks += 1

    with zipfile.ZipFile(a.package / 'CarPlay_Maps_VC_MU1367_791_Integration_Test.zip') as z:
        check(z.testzip() is None, 'archive CRC')
        for name in z.namelist():
            file = stage / name
            check(z.read(name) == file.read_bytes(), 'archive/tree bytes: ' + name)
            check((z.getinfo(name).external_attr >> 16) & 0o777 == file.stat().st_mode & 0o777, 'archive/tree mode: ' + name)
    for file in (stage / 'Toolbox/GEM').glob('carplay-maps-vc*.esd'):
        for name in re.findall(r'/eso/hmi/engdefs/scripts/mqb/([^"\s]+)', file.read_text()):
            target = scripts / name
            check(target.is_file(), 'missing menu script ' + name)
            subprocess.run(['/bin/ksh', '-n', str(target)], check=True)
    with tempfile.TemporaryDirectory(prefix='mu1367-package-') as temp:
        root = Path(temp) / 'mmx'
        app = root / 'mnt/app'
        env = dict(os.environ, CPMAP_TEST_ROOT=str(root), CPMAP_TEST_MEDIA=str(stage.resolve()))
        for dest, source in [('ifs/lsd.jxe', 'lsd.jxe'), ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 'driver'),
                             ('mnt/system/etc/mm/iap2.cfg', 'iap2.cfg'), ('mnt/app/eso/hmi/lsd/lsd.sh', 'boot'),
                             ('mnt/app/eso/bin/apps/dio_manager', 'dio')]:
            file = root / dest
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a.inputs / source, file)
        (root / 'ramdisk').mkdir()
        (app / 'eso/hmi/lsd/jars').mkdir()
        installed_scripts = app / 'eso/hmi/engdefs/scripts/mqb'
        shutil.copytree(scripts, installed_scripts)
        boot = app / 'eso/hmi/lsd/lsd.sh'
        dio = app / 'eso/bin/apps/dio_manager'
        original_boot, original_dio = boot.read_bytes(), dio.read_bytes()

        def run(file, *args, success=True):
            result = subprocess.run(['/bin/ksh', str(file), *map(str, args)], env=env,
                                    capture_output=True, text=True, timeout=60)
            check((result.returncode == 0) == success, result.stdout + result.stderr)
            return result.stdout

        run(maps / 'payload/common/install-carplay-maps.sh', maps / 'payload', 'MU1367', '791')
        check((app / 'carplaymaps/core.so').read_bytes() == (maps / 'tuning/MU1367/791/default/core.so').read_bytes(), 'default display')
        run(scripts / 'cpmap_tune.sh', 'stock-40fps')
        check((app / 'carplaymaps/core.so').read_bytes() == (maps / 'tuning/MU1367/791/stock-40fps/core.so').read_bytes(), 'stock video fallback')
        run(scripts / 'cpmap_tune.sh', 'low-card', success=False)
        run(scripts / 'cpmap_tune.sh', 'default')
        test_payload = Path(temp) / 'payload'
        shutil.copytree(payload, test_payload, ignore=shutil.ignore_patterns('source'))
        shutil.copy2(a.verifier, test_payload / 'verify')
        run(test_payload / 'control.sh', 'install', test_payload)
        check(boot.read_text().count('-Xbootclasspath/p:') == 1, 'one effective prepend option')
        for name in ('CarPlayClusterControls', 'CarPlayMU1367Guidance', 'CarPlayMU1367Audio', 'CarPlayMU1367NavIgnore'):
            check(boot.read_text().count(name + '.jar') == 1, 'boot entry ' + name)
        run(scripts / 'cpmap_install_791.sh', success=False)
        # The actual full-restore wrapper must remove the new add-on BEFORE
        # the base restore deletes its state/boot controls.
        run(installed_scripts / 'cpmap_restore.sh')
        check(boot.read_bytes() == original_boot, 'full OEM boot rollback')
        check(dio.read_bytes() == original_dio, 'full OEM dio rollback')
        check(not (app / 'carplaymaps').exists(), 'base removed')
        check((app / 'armle/lib/dll/ipod-drvr-iap2.so').read_bytes() == (a.inputs / 'driver').read_bytes(), 'OEM driver rollback')
        check((root / 'mnt/system/etc/mm/iap2.cfg').read_bytes() == (a.inputs / 'iap2.cfg').read_bytes(), 'OEM accessory config rollback')
    result = {'passed': True, 'checks': checks, 'archive_sha256': sha((a.package / 'CarPlay_Maps_VC_MU1367_791_Integration_Test.zip').read_bytes()),
              'test_sha256': sha(Path(__file__).read_bytes()), 'full_video_and_hmi_restore': True}
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
