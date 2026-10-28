#!/usr/bin/env python3
"""Real controller/payload with exact firmware inputs and fault injection.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mu1367-control-')
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.root = self.work / 'mmx'
        self.app = self.root / 'mnt/app'
        self.saved = self.app / 'carplay-mu1367'
        self.payload = self.work / 'payload'
        shutil.copytree(ARGS.payload, self.payload, ignore=shutil.ignore_patterns('source'))
        shutil.copy2(ARGS.verifier, self.payload / 'verify')
        self.tools = self.work / 'bin'
        self.tools.mkdir()
        for name in ('ls', 'cat', 'awk', 'cp', 'mv', 'rm', 'mkdir', 'chmod', 'sync'):
            (self.tools / name).symlink_to(shutil.which(name))
        for target, source in [('ifs/lsd.jxe', 'lsd.jxe'), ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 'driver'),
                               ('mnt/system/etc/mm/iap2.cfg', 'iap2.cfg')]:
            file = self.root / target
            file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ARGS.inputs / source, file)
        (self.root / 'ramdisk').mkdir()
        self.lsd = self.app / 'eso/hmi/lsd/lsd.sh'
        self.lsd.parent.mkdir(parents=True)
        (self.lsd.parent / 'jars').mkdir()
        self.boot = ('#!/bin/ksh\nBASE_DIR=/mnt/app/eso/hmi\nBOOTCLASSPATH="-Xbootclasspath/a:/ifs/lsd.jxe"\n'
                     'BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$BASE_DIR/lsd/jars/CarPlayClusterControls.jar"\n'
                     '$J9 $VMOPTIONS $BOOTCLASSPATH -jxe $HMI_JXE &\n')
        self.lsd.write_text(self.boot)
        self.lsd.chmod(0o755)
        profile = self.app / 'carplaymaps/PROFILE'
        profile.parent.mkdir()
        profile.write_text('MU1367/791\n')
        self.env = dict(os.environ, PATH=str(self.tools), CPMAP_TEST_ROOT=str(self.root))
        self.original = self.snapshot()

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and ('/jars/' in str(p) or p.name in ('lsd.sh', 'ipod-drvr-iap2.so', 'iap2.cfg'))}

    def run_control(self, action, success=True, saved=False, env=None):
        file = self.saved / 'control.sh' if saved else self.payload / 'control.sh'
        result = subprocess.run(['/bin/ksh', str(file), action, str(self.payload)], env=env or self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result.stdout

    def test_install_idempotence_and_saved_uninstall_without_sd(self):
        self.run_control('install')
        self.assertIn('ALREADY_INSTALLED', self.run_control('install'))
        self.assertEqual(self.lsd.read_text().count('MU1367_AUTOSTART'), 1)
        shutil.rmtree(self.payload)
        self.run_control('uninstall', saved=True)
        self.assertEqual(self.snapshot(), self.original)
        self.assertEqual(self.lsd.stat().st_mode & 0o777, 0o755)
        self.assertTrue((self.saved / 'BACKUPS_READY').is_file())

    def test_wrong_same_size_firmware_changes_nothing(self):
        file = self.root / 'ifs/lsd.jxe'
        with file.open('r+b') as stream:
            stream.write(b'bad')
        self.run_control('install', False)
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(self.saved.exists())

    def test_wrong_same_size_payload_changes_nothing(self):
        file = self.payload / 'CarPlayMU1367Audio.jar'
        data = bytearray(file.read_bytes()); data[-1] ^= 1; file.write_bytes(data)
        self.run_control('install', False)
        self.assertEqual(self.snapshot(), self.original)

    def test_790_adapter_refused(self):
        (self.app / 'carplaymaps/PROFILE').write_text('MU1367/790\n')
        self.run_control('install', False)
        self.assertEqual(self.snapshot(), self.original)

    def test_unknown_driver_and_config_refused(self):
        for path in ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 'mnt/system/etc/mm/iap2.cfg'):
            file = self.root / path
            original = file.read_bytes()
            data = bytearray(original);data[-1] ^= 1;file.write_bytes(data)
            self.run_control('install', False)
            file.write_bytes(original)
        self.assertEqual(self.snapshot(), self.original)

    def test_backup_corruption_refuses_before_restore(self):
        self.run_control('install')
        current = self.snapshot()
        (self.saved / 'backup/driver').write_bytes(b'corrupt')
        self.run_control('recover', False, saved=True)
        self.assertEqual(self.snapshot(), current)

    def test_normal_removal_preserves_later_unrelated_boot_entries(self):
        self.run_control('install')
        text = self.lsd.read_text().replace('CarPlayClusterControls.jar"', 'CarPlayClusterControls.jar:$BASE_DIR/lsd/jars/Other.jar"')
        self.lsd.write_text(text)
        self.run_control('uninstall', saved=True)
        self.assertIn('Other.jar', self.lsd.read_text())
        self.assertNotIn('CarPlayMU1367', self.lsd.read_text())

    def test_removal_without_original_prepend_line(self):
        self.lsd.write_text('\n'.join(x for x in self.boot.splitlines() if '-Xbootclasspath/p:' not in x) + '\n')
        original = self.lsd.read_bytes()
        self.run_control('install')
        self.run_control('uninstall', saved=True)
        self.assertEqual(self.lsd.read_bytes(), original)

    def test_artwork_swap_and_removal_restore_oem(self):
        self.run_control('install')
        self.run_control('artwork-on', saved=True)
        self.assertEqual((self.app / 'armle/lib/dll/ipod-drvr-iap2.so').read_bytes(), (self.payload / 'ipod-drvr-iap2-N3.so').read_bytes())
        self.run_control('artwork-off', saved=True)
        self.run_control('artwork-on', saved=True)
        self.run_control('uninstall', saved=True)
        self.assertEqual(self.snapshot(), self.original)

    def test_symlink_target_and_recovery_directory_refused(self):
        target = self.app / 'eso/hmi/lsd/jars/CarPlayMU1367Audio.jar'
        external = self.work / 'untouched';external.write_text('untouched')
        target.symlink_to(external)
        self.run_control('install', False)
        self.assertEqual(external.read_text(), 'untouched')
        target.unlink()
        self.saved.symlink_to(self.work)
        self.run_control('install', False)

    def test_later_modified_adapter_is_preserved(self):
        self.run_control('install')
        file = self.lsd.parent / 'jars/CarPlayMU1367Audio.jar'
        file.write_bytes(b'other revision')
        current = self.snapshot()
        self.run_control('uninstall', False, saved=True)
        self.assertEqual(self.snapshot(), current)

    def test_operation_lock_preserved(self):
        lock = self.root / 'ramdisk/.carplay-guidance-install-lock'
        lock.mkdir()
        self.run_control('install', False)
        self.assertTrue(lock.exists())
        self.assertEqual(self.snapshot(), self.original)

    def test_failure_after_driver_commit_rolls_back_all_files(self):
        real = shutil.which('mv')
        file = self.tools / 'mv';file.unlink()
        target = self.root / 'mnt/system/etc/mm/iap2.cfg'
        file.write_text('#!/bin/ksh\nif [ "$2" = ' + shlex.quote(str(target)) + ' ] && [ ! -f ' + shlex.quote(str(self.work / 'once')) + ' ]; then\n: > ' + shlex.quote(str(self.work / 'once')) + '\nexit 1\nfi\nexec ' + shlex.quote(real) + ' "$@"\n')
        file.chmod(0o755)
        self.run_control('install', False)
        self.assertEqual(self.snapshot(), self.original)

    def test_crash_then_saved_recovery_with_stale_stage(self):
        self.run_control('install')
        # Exact persistent state after an untrappable interruption: backups
        # ready, some files committed, optional stage left on the same volume.
        (self.saved / 'STATE').write_text('prepared\n')
        (self.app / 'armle/lib/dll/ipod-drvr-iap2.so.mu1367-new').write_bytes(b'partial stage')
        shutil.rmtree(self.payload)
        self.run_control('recover', saved=True)
        self.assertEqual(self.snapshot(), self.original)

    def test_reinstall_does_not_overwrite_recovery_snapshot(self):
        self.run_control('install')
        self.run_control('uninstall', saved=True)
        original = (self.saved / 'backup/boot').read_bytes()
        self.run_control('install', False)
        self.assertEqual((self.saved / 'backup/boot').read_bytes(), original)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'inputs', 'verifier', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    ARGS = p.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'controller_sha256': hashlib.sha256((ARGS.payload / 'control.sh').read_bytes()).hexdigest(),
              'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'host_verifier_same_c_source': True}
    ARGS.output.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
