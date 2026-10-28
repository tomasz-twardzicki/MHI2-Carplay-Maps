#!/usr/bin/env python3
"""Exercise N0 installation/recovery with real shell utilities and a closed PATH.
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

from package_support import controller, scripts, JAR, PAYLOAD

HERE = Path(__file__).resolve().parent
PHASE = 'N0'
SCRIPT_NAME = 'cpmap_audio_n0.sh'


class Controls(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='audio-n0-controls-')
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.root = self.work / 'mmx'
        self.sd = self.work / 'sd'
        self.payload = self.sd / PAYLOAD
        self.payload.mkdir(parents=True)
        self.jar_data = (ARGS.hmi / JAR).read_bytes()
        manifest = json.loads((ARGS.hmi / 'manifest.json').read_text())
        self.build = manifest['build_id']
        self.assertEqual(hashlib.sha256(self.jar_data).hexdigest(), manifest['jar_sha256'])
        (self.payload / JAR).write_bytes(self.jar_data)
        (self.payload / 'VERSION').write_text(self.build + '\n')
        self.tools = self.work / 'bin'
        self.tools.mkdir()
        for name in ('ls', 'cat', 'rm', 'mkdir', 'awk', 'cp', 'mv', 'chmod', 'sync'):
            (self.tools / name).symlink_to(shutil.which(name))
        f = self.root / 'ifs/lsd.jxe'
        f.parent.mkdir(parents=True)
        with f.open('wb') as stream:
            stream.truncate(52751492)
        (self.root / 'ramdisk').mkdir()
        self.profile = self.root / 'mnt/app/carplaymaps/PROFILE'
        self.profile.parent.mkdir(parents=True)
        self.profile.write_text('MU1427/791\n')
        self.lsd = self.root / 'mnt/app/eso/hmi/lsd/lsd.sh'
        self.lsd.parent.mkdir(parents=True)
        (self.lsd.parent / 'jars').mkdir()
        self.original = ('#!/bin/ksh\nBASE_DIR=/mnt/app/eso/hmi\n'
            'BOOTCLASSPATH="-Xbootclasspath/a:/ifs/lsd.jxe"\n'
            'BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$BASE_DIR/lsd/jars/CarPlayRouteGuidanceD1.jar:$BASE_DIR/lsd/jars/NavActiveIgnore.jar:$BASE_DIR/lsd/jars/CarPlayClusterControls.jar"\n'
            '/mnt/app/carplay-route-guidance/rgi-observer start-live /dev/ipod0/rgi-events /ramdisk/carplay-route-guidance # CPMAP_GUIDANCE_AUTOSTART\n'
            '$J9 $VMOPTIONS $BOOTCLASSPATH -jxe $HMI_JXE &\n')
        self.lsd.write_text(self.original)
        self.lsd.chmod(0o755)
        self.jar = self.lsd.parent / 'jars' / JAR
        self.saved = self.root / ('mnt/app/carplay-now-playing-' + PHASE.lower())
        self.ram = self.root / ('ramdisk/carplay-now-playing-' + PHASE.lower() + '.status')
        self.script = self.work / 'control.sh'
        self.script.write_text(controller(self.build, len(self.jar_data)))
        self.env = dict(os.environ, PATH=str(self.tools), CPMAP_TEST_ROOT=str(self.root), CPMAP_TEST_SD=str(self.sd))
        # Other installed binary/config files must never be changed by N0.
        self.preserved = {}
        for name in ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 'mnt/system/etc/mm/iap2.cfg',
                     'mnt/app/eso/hmi/lsd/jars/CarPlayRouteGuidanceD1.jar'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'preserve-' + name.encode())
            self.preserved[path] = path.read_bytes()

    def tearDown(self):
        for path, data in self.preserved.items():
            self.assertEqual(path.read_bytes(), data)

    def run_control(self, action, success=True, local=False, argument=None):
        script = self.saved / 'control.sh' if local else self.script
        r = subprocess.run(['/bin/ksh', str(script), action, str(argument or self.payload)],
                           env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode == 0, success, r.stdout + r.stderr)
        return r.stdout

    def reject_rename(self, path):
        tool = self.tools / 'mv'
        tool.unlink()
        tool.write_text('#!/bin/sh\nif [ "$2" = ' + shlex.quote(str(path)) +
                        ' ]; then exit 1; fi\nexec ' + shlex.quote(shutil.which('mv')) + ' "$@"\n')
        tool.chmod(0o755)

    def test_install_idempotent_no_sd_remove(self):
        self.run_control('install')
        self.assertIn('ALREADY_INSTALLED', self.run_control('install'))
        self.assertEqual(self.jar.read_bytes(), self.jar_data)
        self.assertEqual(self.jar.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.lsd.stat().st_mode & 0o777, 0o755)
        shutil.rmtree(self.payload)
        self.run_control('uninstall', local=True)
        self.assertEqual(self.lsd.read_text(), self.original)
        self.assertFalse(self.jar.exists())
        self.run_control('uninstall', local=True)

    def test_no_prepend_line_and_later_jars(self):
        self.original = '\n'.join(x for x in self.original.split('\n') if not x.startswith('BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:'))
        self.lsd.write_text(self.original)
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))
        self.run_control('uninstall')
        self.assertIn('Later.jar', self.lsd.read_text())
        self.assertNotIn(JAR, self.lsd.read_text())

    def test_later_prepend_entry_survives(self):
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))
        self.run_control('uninstall')
        self.assertEqual(self.lsd.read_text(), self.original.replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))

    def test_wrong_firmware_profile_and_payload_refused(self):
        self.profile.write_text('MU1367/791\n')
        self.assertIn('INSTALL_791', self.run_control('install', False))
        self.profile.write_text('MU1427/791\n')
        (self.payload / JAR).write_bytes(b'bad')
        self.assertIn('PAYLOAD_JAR_SIZE', self.run_control('install', False))
        with (self.root / 'ifs/lsd.jxe').open('wb') as stream:
            stream.truncate(55840541)
        self.assertIn('MU1427_ONLY', self.run_control('install', False))
        self.assertFalse(self.saved.exists())
        self.assertEqual(self.lsd.read_text(), self.original)

    def test_unknown_layout_and_prepend_after_launch_refused(self):
        self.lsd.write_text('unknown layout\n')
        self.assertIn('UNKNOWN_LSD_LAYOUT', self.run_control('install', False))
        lines = self.original.splitlines()
        prepend = lines.pop(3)
        self.lsd.write_text('\n'.join(lines + [prepend]) + '\n')
        self.assertIn('PREPEND_AFTER_LAUNCH', self.run_control('install', False))

    def test_existing_jar_or_boot_reference_refused(self):
        self.jar.write_bytes(b'old')
        self.assertIn('EXISTING_JAR', self.run_control('install', False))
        self.jar.unlink()
        self.lsd.write_text(self.original + '# ' + JAR + '\n')
        self.assertIn('EXISTING_BOOT_ENTRY', self.run_control('install', False))

    def test_boot_failure_rolls_back_jar(self):
        self.reject_rename(self.lsd)
        self.run_control('install', False)
        self.assertEqual(self.lsd.read_text(), self.original)
        self.assertFalse(self.jar.exists())
        self.assertTrue((self.saved / 'control.sh').is_file())

    def test_marker_failure_keeps_recoverable_boot_and_jar(self):
        self.reject_rename(self.saved / 'VERSION')
        self.assertIn('MARKER_COMMIT', self.run_control('install', False))
        self.assertIn(JAR, self.lsd.read_text())
        self.assertTrue(self.jar.exists())
        shutil.rmtree(self.payload)
        self.run_control('uninstall', local=True)
        self.assertEqual(self.lsd.read_text(), self.original)

    def test_failed_removal_keeps_jar_and_supports_retry(self):
        self.run_control('install')
        before = self.lsd.read_bytes()
        self.reject_rename(self.lsd)
        shutil.rmtree(self.payload)
        self.run_control('uninstall', False, local=True)
        self.assertEqual(self.lsd.read_bytes(), before)
        self.assertTrue(self.jar.exists())
        (self.tools / 'mv').unlink()
        (self.tools / 'mv').symlink_to(shutil.which('mv'))
        self.run_control('uninstall', local=True)
        self.assertFalse(self.jar.exists())

    def test_duplicate_reference_removal_refused(self):
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/' + JAR + ':'))
        before = self.lsd.read_bytes()
        self.run_control('uninstall', False)
        self.assertEqual(self.lsd.read_bytes(), before)
        self.assertTrue(self.jar.exists())

    def test_shared_lock_refused_without_stealing_it(self):
        lock = self.root / 'ramdisk/.carplay-guidance-install-lock'
        lock.mkdir()
        self.assertIn('ANOTHER_OPERATION', self.run_control('install', False))
        self.assertTrue(lock.is_dir())
        self.assertFalse(self.saved.exists())

    def test_reinstall_rejects_wrong_reference(self):
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('$BASE_DIR/lsd/jars/' + JAR, '/wrong/' + JAR))
        self.assertIn('INSTALLED_BOOT_ENTRY', self.run_control('install', False))

    def test_symlinks_refused(self):
        other = self.work / 'other'
        other.mkdir()
        self.saved.symlink_to(other)
        self.assertIn('RECOVERY_SYMLINK', self.run_control('install', False))
        self.saved.unlink()
        (self.lsd.parent / 'lsd.sh.audio-new').symlink_to(self.lsd)
        self.assertIn('STALE_STAGING_FILE', self.run_control('install', False))
        self.assertEqual(self.lsd.read_text(), self.original)

    def test_export_wrapper_slots_full_preserves_snapshots(self):
        installed = self.root / 'mnt/app/eso/hmi/engdefs/scripts/mqb'
        installed.mkdir(parents=True)
        shutil.copy2(self.script, installed / SCRIPT_NAME)
        wrapper = self.work / 'export.sh'
        wrapper.write_text(scripts()['export'])
        for i in range(1, 17):
            directory = self.sd / ('Log/cpmap-audio-' + PHASE + '-%02d' % i)
            directory.mkdir(parents=True)
            (directory / 'status.txt').write_text('preserve\n')
        r = subprocess.run(['/bin/ksh', str(wrapper)], env=self.env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('EXPORT_SLOTS_FULL', r.stdout)
        self.assertEqual((self.sd / ('Log/cpmap-audio-' + PHASE + '-01/status.txt')).read_text(), 'preserve\n')

    def test_status_export_without_sd_or_installation(self):
        self.assertIn('NOT_AVAILABLE', self.run_control('status'))
        self.run_control('install')
        self.ram.write_text('format=1 tracks=7 valid_tracks=7 cover_urls=3\nwrites=20\n')
        shutil.rmtree(self.payload)
        out = self.work / 'snapshot'
        self.run_control('export', local=True, argument=out)
        self.assertIn('tracks=7', (out / 'status.txt').read_text())
        self.run_control('export', False, local=True, argument=out)
        self.assertIn('tracks=7', (out / 'status.txt').read_text())

    def test_status_size_and_symlink_limits(self):
        self.ram.write_bytes(bytes(4097))
        self.assertIn('STATUS_OVERSIZE', self.run_control('status', False))
        self.ram.unlink()
        self.ram.symlink_to(self.profile)
        self.assertIn('STATUS_SYMLINK', self.run_control('status', False))

    def test_menu_wrappers_and_export_slots(self):
        installed = self.root / 'mnt/app/eso/hmi/engdefs/scripts/mqb'
        installed.mkdir(parents=True)
        shutil.copy2(self.script, installed / SCRIPT_NAME)
        wrappers = scripts()
        for name, text in wrappers.items():
            path = self.work / (name + '.sh')
            path.write_text(text)
            subprocess.run(['/bin/ksh', '-n', str(path)], check=True)
        for name in ('install', 'status', 'export', 'export', 'remove'):
            result = subprocess.run(['/bin/ksh', str(self.work / (name + '.sh'))], env=self.env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.sd / ('Log/cpmap-audio-' + PHASE + '-01/status.txt')).exists())
        self.assertTrue((self.sd / ('Log/cpmap-audio-' + PHASE + '-02/status.txt')).exists())
        self.assertEqual(self.lsd.read_text(), self.original)

    def test_n1_refuses_n0_class_and_unrebooted_runtime(self):
        if PHASE != 'N1':
            return
        old = self.jar.parent / 'CarPlayNowPlayingObserverN0.jar'
        old.write_bytes(b'old N0')
        self.assertIn('REMOVE_N0_AND_REBOOT', self.run_control('install', False))
        old.unlink()
        old_status = self.root / 'ramdisk/carplay-now-playing-n0.status'
        old_status.write_text('old runtime\n')
        self.assertIn('N0_RUNTIME_PRESENT', self.run_control('install', False))
        self.assertFalse(self.saved.exists())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('hmi', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--phase', choices=('N0', 'N1'), default='N0')
    ARGS = p.parse_args()
    PHASE = ARGS.phase
    if PHASE == 'N1':
        JAR = 'CarPlayNowPlayingTextN1.jar'
        PAYLOAD = 'Custom/carplay_audio_n1'
        SCRIPT_NAME = 'cpmap_audio_n1.sh'
        from functools import partial
        controller = partial(controller, phase='N1')
        scripts = partial(scripts, phase='N1')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    record = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'jar_sha256': hashlib.sha256((ARGS.hmi / JAR).read_bytes()).hexdigest(),
              'sources': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ('control.sh', 'package_support.py', 'test-controls.py')}}
    ARGS.output.write_text(json.dumps(record, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
