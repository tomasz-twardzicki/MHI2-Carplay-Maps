#!/usr/bin/env python3
"""Closed-PATH D1 installation/handback controls with the real host C4 reader."""
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reader_fixtures', HERE / 'test-observer.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f.ProcessTests.setUpClass(); cls.binary = f.ProcessTests.binary

    @classmethod
    def tearDownClass(cls): f.ProcessTests.tearDownClass()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rgi-d1-controls-'); self.work = Path(self.temp.name)
        self.root = self.work / 'mmx'; self.sd = self.work / 'sd'; self.sd.mkdir()
        self.payload = self.work / 'payload'; self.payload.mkdir()
        self.tools = self.work / 'bin'; self.tools.mkdir()
        for name in ('ls', 'cat', 'rm', 'awk', 'cp', 'mv', 'mkdir', 'chmod', 'sync', 'dd'):
            (self.tools / name).symlink_to(shutil.which(name))
        for name, size in [('ifs/lsd.jxe', 52751492), ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 743196), ('mnt/system/etc/mm/iap2.cfg', 6006)]:
            file = self.root / name; file.parent.mkdir(parents=True, exist_ok=True)
            with file.open('wb') as stream: stream.truncate(size)
        self.marker = self.root / 'mnt/app/route-guidance-b1/VERSION'
        self.marker.parent.mkdir(); self.marker.write_text('MU1427-iAP2-RGI-B4-3760797a\n')
        self.lsd = self.root / 'mnt/app/eso/hmi/lsd/lsd.sh'; self.lsd.parent.mkdir(parents=True)
        (self.lsd.parent / 'jars').mkdir()
        self.factory = '#!/bin/ksh\nBASE_DIR=/mnt/app/eso/hmi\nBOOTCLASSPATH="-Xbootclasspath/a:/ifs/lsd.jxe"\n$J9 $VMOPTIONS $BOOTCLASSPATH -jxe $HMI_JXE &\n'
        self.lsd.write_text(self.factory); self.lsd.chmod(0o755)
        self.jar = self.lsd.parent / 'jars/CarPlayRouteGuidanceD1.jar'
        (self.root / 'ramdisk').mkdir(); self.ram = self.root / 'ramdisk/cpmap-rgi-D1'
        source = self.root / 'dev/ipod0/rgi-events'; source.parent.mkdir(parents=True); source.write_bytes(f.guiding())
        (self.payload / 'CarPlayRouteGuidanceD1.jar').write_bytes(b'jar-fixture')
        (self.payload / 'VERSION').write_text('D1-test\n'); shutil.copy2(self.binary, self.payload / 'rgi-observer')
        self.script = self.work / 'control.sh'
        self.script.write_text((HERE / 'bridge/control.sh').read_text().replace('@BUILD_ID@', 'D1-test').replace('@JAR_SIZE@', '11')
                               .replace('@SOURCE_ID@', 'test-source').replace('@ALLOW_LIVE@', '1').replace('BINARY_SIZE=16333', 'BINARY_SIZE=' + str(self.binary.stat().st_size)))
        self.env = dict(os.environ, PATH=str(self.tools), CPMAP_TEST_ROOT=str(self.root), CPMAP_TEST_VOL=str(self.sd))

    def tearDown(self):
        if (self.ram / 'capture').is_dir(): subprocess.run([str(self.binary), 'stop', str(self.ram / 'capture')], capture_output=True, timeout=5)
        self.temp.cleanup()

    def run_control(self, action, success=True, script=None):
        result = subprocess.run(['/bin/ksh', str(script or self.script), action, str(self.payload)], env=self.env, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr); return result.stdout

    def healthy(self, **kw):
        run = (self.ram / 'request').read_text().split()[1]
        fields = dict(build='test-source', run=run, mode=1, context=0, ticks=5, proposals=3, writes=0, failures=0, error=0)
        fields.update(kw); (self.ram / 'adapter-status.txt').write_text('D1 ' + ' '.join(f'{k}={v}' for k, v in fields.items()) + '\n')

    def test_factory_install_idempotence_local_rollback_and_reinstall(self):
        self.run_control('install'); modified = self.lsd.read_bytes(); self.run_control('install')
        self.assertEqual(self.lsd.read_bytes(), modified); self.assertEqual(self.lsd.stat().st_mode & 0o777, 0o755)
        helper = self.root / 'mnt/app/route-guidance-D1/control.sh'
        shutil.rmtree(self.payload); self.run_control('uninstall', script=helper)
        self.assertEqual(self.lsd.read_text(), self.factory); self.assertFalse(self.jar.exists())
        self.payload.mkdir(); (self.payload / 'CarPlayRouteGuidanceD1.jar').write_bytes(b'jar-fixture'); (self.payload / 'VERSION').write_text('D1-test\n')
        self.run_control('install'); self.run_control('uninstall'); self.assertEqual(self.lsd.read_text(), self.factory)

    def test_existing_and_later_bootclasspath_jars_preserved(self):
        line = 'BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$BASE_DIR/lsd/jars/NavActiveIgnore.jar:$BASE_DIR/lsd/jars/CarPlayClusterControls.jar"\n'
        original = self.factory.replace('$J9 ', line + '$J9 '); self.lsd.write_text(original)
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))
        self.run_control('uninstall')
        self.assertEqual(self.lsd.read_text(), original.replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))

    def test_remove_last_entry_after_later_control_install(self):
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/CarPlayClusterControls.jar:'))
        self.run_control('uninstall'); self.assertIn('CarPlayClusterControls.jar"', self.lsd.read_text()); self.assertNotIn('D1.jar', self.lsd.read_text())

    def test_wrong_firmware_and_payload_no_persistent_changes(self):
        self.marker.write_text('wrong\n'); self.run_control('install', False)
        self.assertEqual(self.lsd.read_text(), self.factory); self.assertFalse(self.jar.exists())
        self.marker.write_text('MU1427-iAP2-RGI-B4-3760797a\n'); (self.payload / 'CarPlayRouteGuidanceD1.jar').write_bytes(b'bad')
        self.run_control('install', False); self.assertFalse((self.root / 'mnt/app/route-guidance-D1').exists())

    def test_unknown_script_layout_refused_untouched(self):
        self.lsd.write_text('unknown layout\n'); self.run_control('install', False); self.assertEqual(self.lsd.read_text(), 'unknown layout\n')

    def test_prepend_after_launch_refused_untouched(self):
        script = self.factory + 'BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$BASE_DIR/lsd/jars/Other.jar"\n'
        self.lsd.write_text(script); self.run_control('install', False); self.assertEqual(self.lsd.read_text(), script); self.assertFalse(self.jar.exists())

    def test_restore_commit_failure_keeps_jar_and_can_retry_without_sd(self):
        self.run_control('install'); modified = self.lsd.read_bytes(); shutil.rmtree(self.payload)
        (self.tools / 'mv').unlink()
        (self.tools / 'mv').write_text('#!/bin/sh\nif [ "$2" = ' + shlex.quote(str(self.lsd)) + ' ]; then exit 1; fi\nexec ' + shlex.quote(shutil.which('mv')) + ' "$@"\n'); (self.tools / 'mv').chmod(0o755)
        self.run_control('uninstall', False); self.assertEqual(self.lsd.read_bytes(), modified); self.assertTrue(self.jar.exists())
        (self.tools / 'mv').unlink(); (self.tools / 'mv').symlink_to(shutil.which('mv'))
        self.run_control('uninstall'); self.assertEqual(self.lsd.read_text(), self.factory)

    def test_jar_stage_copy_failure_never_changes_boot_script(self):
        (self.tools / 'cp').unlink()
        (self.tools / 'cp').write_text('#!/bin/sh\ncase "$1" in *CarPlayRouteGuidanceD1.jar) exit 1;; esac\nexec ' + shlex.quote(shutil.which('cp')) + ' "$@"\n'); (self.tools / 'cp').chmod(0o755)
        self.run_control('install', False); self.assertEqual(self.lsd.read_text(), self.factory); self.assertFalse(self.jar.exists())

    def test_script_commit_failure_keeps_old_hmi_and_rollback_available(self):
        (self.tools / 'mv').unlink()
        (self.tools / 'mv').write_text('#!/bin/sh\nif [ "$2" = ' + shlex.quote(str(self.lsd)) + ' ]; then exit 1; fi\nexec ' + shlex.quote(shutil.which('mv')) + ' "$@"\n'); (self.tools / 'mv').chmod(0o755)
        self.run_control('install', False); self.assertEqual(self.lsd.read_text(), self.factory); self.assertFalse(self.jar.exists())
        (self.tools / 'mv').unlink(); (self.tools / 'mv').symlink_to(shutil.which('mv'))
        self.run_control('uninstall'); self.assertEqual(self.lsd.read_text(), self.factory)

    def test_shadow_verify_export_clear_live_disable(self):
        self.run_control('install'); self.assertIn('RUN_SHADOW', self.run_control('live', False))
        self.run_control('shadow'); self.assertIn('EXPORT_AND_CLEAR', self.run_control('shadow', False))
        self.healthy(); self.run_control('verify'); self.run_control('export')
        output, = (self.sd / 'Log').glob('cpmap-rgi-D1-*')
        with (output / 'events.rgj').open('rb') as stream: summary = f.observer.replay(stream)
        self.assertEqual(summary['end_reason'], 1); self.run_control('clear')
        self.run_control('live'); self.assertTrue((self.ram / 'request').read_text().startswith('live '))
        self.marker.unlink(); shutil.rmtree(self.payload); self.run_control('disable'); self.assertFalse((self.ram / 'request').exists())
        self.run_control('clear'); self.assertFalse((self.ram / 'capture').exists())

    def test_shadow_proof_rejects_errors_wrong_run_build_or_any_writes(self):
        self.run_control('install'); self.run_control('shadow')
        for fields in [dict(mode=0), dict(context=3), dict(proposals=0), dict(writes=1), dict(failures=1), dict(error=1), dict(build='old'), dict(run='old')]:
            self.healthy(**fields); self.run_control('verify', False); self.assertFalse((self.ram / 'shadow-verified').exists())
        self.healthy(); self.run_control('verify')

    def test_shadow_only_release_cannot_start_live_even_with_proof(self):
        self.run_control('install'); self.run_control('shadow'); self.healthy(); self.run_control('verify'); self.run_control('clear')
        self.script.write_text(self.script.read_text().replace('ALLOW_LIVE=1','ALLOW_LIVE=0'))
        self.assertIn('LIVE_DISABLED', self.run_control('live', False)); self.assertFalse((self.ram / 'request').exists())

    def test_verified_shadow_evidence_survives_disable_and_counter_reset(self):
        self.run_control('install'); self.run_control('shadow'); self.healthy(); self.run_control('verify')
        expected = (self.ram / 'adapter-status.txt').read_bytes()
        self.run_control('disable')
        (self.ram / 'adapter-status.txt').write_text('D1 mode=0 run=0 proposals=0 writes=0 records=0 error=0\n')
        self.run_control('export')
        output, = (self.sd / 'Log').glob('cpmap-rgi-D1-*')
        self.assertEqual((output / 'shadow-verification.txt').read_bytes(), expected)
        self.assertIn('mode=0', (output / 'adapter-status.txt').read_text())

    def test_export_captures_status_and_request_before_disable(self):
        self.run_control('install'); self.run_control('shadow'); self.healthy()
        expected = (self.ram / 'adapter-status.txt').read_bytes(); request = (self.ram / 'request').read_bytes()
        self.run_control('export')
        output, = (self.sd / 'Log').glob('cpmap-rgi-D1-*')
        self.assertEqual((output / 'adapter-status-before-disable.txt').read_bytes(), expected)
        self.assertEqual((output / 'request-before-disable.txt').read_bytes(), request)
        self.assertFalse((self.ram / 'request').exists())

    def test_observed_live_status_survives_manual_disable_and_export(self):
        self.run_control('install'); self.run_control('shadow'); self.healthy(); self.run_control('verify')
        shadow = (self.ram / 'shadow-verification.txt').read_bytes()
        self.run_control('status'); self.run_control('clear'); self.run_control('live')
        self.assertFalse((self.ram / 'adapter-status-observed.txt').exists())
        self.assertEqual((self.ram / 'shadow-verification.txt').read_bytes(), shadow)
        self.healthy(mode=2, writes=12); expected = (self.ram / 'adapter-status.txt').read_bytes()
        self.run_control('status'); self.run_control('disable')
        (self.ram / 'adapter-status.txt').write_text('D1 mode=0 run=0 writes=0\n')
        self.run_control('export')
        output, = (self.sd / 'Log').glob('cpmap-rgi-D1-*')
        self.assertEqual((output / 'adapter-status-observed.txt').read_bytes(), expected)
        self.assertEqual((output / 'shadow-verification.txt').read_bytes(), shadow)

    def test_status_snapshot_failure_does_not_leave_native_output_enabled(self):
        self.run_control('install'); self.run_control('shadow'); self.healthy()
        (self.tools / 'cp').unlink()
        (self.tools / 'cp').write_text('#!/bin/sh\nif [ "$1" = ' + shlex.quote(str(self.ram / 'adapter-status.txt')) + ' ]; then exit 1; fi\nexec ' + shlex.quote(shutil.which('cp')) + ' "$@"\n')
        (self.tools / 'cp').chmod(0o755)
        self.assertIn('STATUS_SNAPSHOT_FAILED', self.run_control('export', False))
        self.assertFalse((self.ram / 'request').exists()); self.assertTrue((self.ram / 'capture/events.rgj').exists())

    def test_disable_needs_only_rm_ls_cat_and_no_payload(self):
        self.ram.mkdir(); (self.ram / 'request').write_text('live 1\n')
        for name in ('awk', 'cp', 'mv', 'mkdir', 'chmod', 'sync', 'dd'): (self.tools / name).unlink()
        self.run_control('disable'); self.assertFalse((self.ram / 'request').exists())

    def test_failed_export_retains_ram_and_disables_output(self):
        self.run_control('install'); self.run_control('shadow'); self.env['CPMAP_TEST_VOL'] = str(self.work / 'missing-sd')
        self.run_control('export', False); self.assertFalse((self.ram / 'request').exists()); self.assertTrue((self.ram / 'capture/events.rgj').exists())

    def test_missing_recorder_does_not_block_uninstall(self):
        self.run_control('install'); self.ram.mkdir(); (self.ram / 'request').write_text('live 1\n'); (self.ram / 'capture').mkdir()
        self.run_control('uninstall'); self.assertFalse((self.ram / 'request').exists()); self.assertEqual(self.lsd.read_text(), self.factory)
        (self.ram / 'capture').rmdir()

    def test_unsupported_removal_layout_keeps_jar_and_script_for_recovery(self):
        self.run_control('install'); original = self.lsd.read_text().replace('BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:', 'OTHER="')
        self.lsd.write_text(original); self.run_control('uninstall', False)
        self.assertEqual(self.lsd.read_text(), original); self.assertTrue(self.jar.exists())


if __name__ == '__main__':
    import hashlib
    import json
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    if result.wasSuccessful():
        (HERE / 'build-D1-control-verification.json').write_text(json.dumps({
            'passed': True, 'tests': result.testsRun,
            'controller_sha256': hashlib.sha256((HERE / 'bridge/control.sh').read_bytes()).hexdigest(),
            'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        }, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
