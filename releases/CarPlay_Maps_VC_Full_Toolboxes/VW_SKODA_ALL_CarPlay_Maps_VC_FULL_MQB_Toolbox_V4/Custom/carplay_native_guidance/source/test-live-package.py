#!/usr/bin/env python3
"""Verify the rendered ZIP's controls with a closed PATH and real payload.

Host filesystem fixtures only: no ARM recorder execution, firmware mounting
or HMI startup. The source controller's process/rollback failure tests are
covered separately by test-live-control.py.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent


def sha(b): return hashlib.sha256(b).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    with zipfile.ZipFile(a.archive) as z, tempfile.TemporaryDirectory(prefix='rgi-package-') as temp:
        assert z.testzip() is None
        manifest = json.loads(z.read('Custom/route_guidance_d1/manifest.json'))
        jar = z.read('Custom/route_guidance_d1/CarPlayRouteGuidanceD1.jar')
        assert sha(jar) == manifest['jar_sha256']
        with zipfile.ZipFile(io.BytesIO(jar)) as classes:
            assert all(struct.unpack_from('>H', classes.read(n), 6)[0] == 46
                       for n in classes.namelist() if n.endswith('.class'))
        controller = z.read('Toolbox/scripts/cpmap_rgi_live.sh')
        assert b'ALLOW_LIVE=1\n' in controller
        menu = z.read('Toolbox/GEM/carplay-maps-vc.esd')
        assert menu.count(('label   "' + manifest['revision'] + ':').encode()) == 9
        seed = HERE / 'build-C4/MU1427-route-guidance-C4-toolbox.zip'
        assert sha(seed.read_bytes()) == manifest['seed_c4_sha256']
        with zipfile.ZipFile(seed) as old:
            for n in old.namelist():
                if n.endswith('/'): continue
                if n == 'Toolbox/GEM/carplay-maps-vc.esd': assert menu.startswith(old.read(n))
                else: assert z.read(n) == old.read(n), 'C4 seed file changed'
        work = Path(temp); root = work / 'mmx'; payload = work / 'payload'; payload.mkdir()
        for n in ('VERSION', 'CarPlayRouteGuidanceD1.jar', 'rgi-observer'):
            (payload / n).write_bytes(z.read('Custom/route_guidance_d1/' + n))
        assert (payload / 'VERSION').read_text().strip() == manifest['build_id']
        tools = work / 'bin'; tools.mkdir()
        for n in ('ls', 'cat', 'rm', 'awk', 'cp', 'mv', 'mkdir', 'chmod', 'sync', 'dd'):
            (tools / n).symlink_to(shutil.which(n))
        for n, size in [('ifs/lsd.jxe', 52751492), ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 743196),
                        ('mnt/system/etc/mm/iap2.cfg', 6006)]:
            file = root / n; file.parent.mkdir(parents=True, exist_ok=True)
            with file.open('wb') as f: f.truncate(size)
        marker = root / 'mnt/app/route-guidance-b1/VERSION'; marker.parent.mkdir()
        marker.write_text('MU1427-iAP2-RGI-B4-3760797a\n')
        lsd = root / 'mnt/app/eso/hmi/lsd/lsd.sh'; lsd.parent.mkdir(parents=True)
        (lsd.parent / 'jars').mkdir(); (root / 'ramdisk').mkdir()
        original = ('#!/bin/ksh\nBASE_DIR=/mnt/app/eso/hmi\nBOOTCLASSPATH="-Xbootclasspath/a:/ifs/lsd.jxe"\n'
                    'BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$BASE_DIR/lsd/jars/NavActiveIgnore.jar:'
                    '$BASE_DIR/lsd/jars/CarPlayClusterControls.jar"\n$J9 $VMOPTIONS $BOOTCLASSPATH -jxe $HMI_JXE &\n')
        lsd.write_text(original); lsd.chmod(0o755)
        script = work / 'control.sh'; script.write_bytes(controller)
        env = dict(os.environ, PATH=str(tools), CPMAP_TEST_ROOT=str(root))

        def call(action, success=True, local=None):
            r = subprocess.run(['/bin/ksh', str(local or script), action, str(payload)],
                               env=env, text=True, capture_output=True, timeout=10)
            assert (r.returncode == 0) == success, r.stdout + r.stderr
            return r.stdout

        for n in z.namelist():
            if n.startswith('Toolbox/scripts/cpmap_rgi_d1_') and n.endswith('.sh') or n == 'Toolbox/scripts/cpmap_rgi_live.sh':
                syntax = work / 'syntax.sh'; syntax.write_bytes(z.read(n))
                subprocess.run(['/bin/ksh', '-n', str(syntax)], check=True, capture_output=True)
        assert 'INSTALLED_REBOOT_REQUIRED' in call('install')
        installed = lsd.parent / 'jars/CarPlayRouteGuidanceD1.jar'
        assert installed.read_bytes() == jar and stat.S_IMODE(lsd.stat().st_mode) == 0o755
        assert 'ALREADY_INSTALLED' in call('install')
        assert 'RUN_SHADOW_AND_VERIFY_FIRST' in call('live', False)
        assert not (root / 'ramdisk/cpmap-rgi-D1/request').exists()
        helper = root / 'mnt/app/route-guidance-D1/control.sh'
        assert helper.read_bytes() == controller
        shutil.rmtree(payload)
        assert 'DISABLED' in call('disable', local=helper)
        assert 'UNINSTALLED_REBOOT_REQUIRED' in call('uninstall', local=helper)
        assert lsd.read_text() == original and stat.S_IMODE(lsd.stat().st_mode) == 0o755
        assert not installed.exists()
    report = dict(passed=True, archive_sha256=sha(a.archive.read_bytes()), jar_sha256=sha(jar),
                  controller_sha256=sha(controller), all_class_major=46, c4_seed_files_preserved=True,
                  actual_packaged_install_idempotence_passed=True, actual_packaged_no_sd_removal_passed=True,
                  boot_script_mode_and_other_jars_preserved=True, live_without_shadow_rejected=True,
                  zip_crc_shell_syntax_passed=True, test_sha256=sha(Path(__file__).read_bytes()))
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__': main()
