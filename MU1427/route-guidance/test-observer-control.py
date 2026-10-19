#!/usr/bin/env python3
"""Exercise C4 controls with a real host reader and only verified utilities."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('observer_tests', HERE / 'test-observer.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ProcessTests.setUpClass()
        cls.binary = fixtures.ProcessTests.binary

    @classmethod
    def tearDownClass(cls): fixtures.ProcessTests.tearDownClass()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rgi-c4-controls-')
        self.work = Path(self.temp.name)
        self.root = self.work / 'mmx'
        self.payload = self.work / 'payload'; self.payload.mkdir()
        self.sd = self.work / 'sd'; self.sd.mkdir()
        self.tools = self.work / 'bin'; self.tools.mkdir()
        for command in ('ls', 'cat', 'cp', 'chmod', 'mkdir', 'rm', 'dd', 'sync'):
            (self.tools / command).symlink_to(shutil.which(command))
        self.script = self.work / 'control.sh'
        self.script.write_text((HERE / 'observer/control.sh').read_text()
                               .replace('@BUILD_ID@', 'C4-test')
                               .replace('@BINARY_SIZE@', str(self.binary.stat().st_size)))
        for name, size in [('ifs/lsd.jxe', 52751492),
                           ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 743196),
                           ('mnt/system/etc/mm/iap2.cfg', 6006)]:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('wb') as f: f.truncate(size)
        self.marker = self.root / 'mnt/app/route-guidance-b1/VERSION'
        self.marker.parent.mkdir(); self.marker.write_text('MU1427-iAP2-RGI-B4-3760797a\n')
        (self.root / 'ramdisk').mkdir()
        self.capture = self.root / 'ramdisk/cpmap-rgi-C4'
        source = self.root / 'dev/ipod0/rgi-events'; source.parent.mkdir(parents=True)
        source.write_bytes(fixtures.guiding())
        shutil.copy2(self.binary, self.payload / 'rgi-observer')
        (self.payload / 'VERSION').write_text('C4-test\n')
        self.env = dict(os.environ, PATH=str(self.tools), CPMAP_TEST_ROOT=str(self.root), CPMAP_TEST_VOL=str(self.sd))

    def tearDown(self):
        if self.capture.is_dir():
            subprocess.run([str(self.binary), 'stop', str(self.capture)], capture_output=True, timeout=5)
        self.temp.cleanup()

    def control(self, action, expected=0):
        r = subprocess.run(['/bin/bash', str(self.script), action, str(self.payload)],
                           env=self.env, capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r.stdout

    def test_start_duplicate_protection_stop_and_removal_preserve_b4(self):
        self.assertIn('CPMAP_RGI_C4_STARTED', self.control('start'))
        self.assertIn('PREVIOUS_RUN', self.control('start', 1))
        self.assertIn('CPMAP_RGI_C4_STOPPED', self.control('stop'))
        self.assertIn('status=ended', self.control('status'))
        self.assertIn('CPMAP_RGI_C4_REMOVED', self.control('remove'))
        self.assertFalse(self.capture.exists())
        self.assertEqual((self.root / 'mnt/app/armle/lib/dll/ipod-drvr-iap2.so').stat().st_size, 743196)
        self.assertEqual(self.marker.read_text(), 'MU1427-iAP2-RGI-B4-3760797a\n')

    def test_export_stops_reader_copies_complete_journal_and_keeps_ram(self):
        self.control('start')
        self.assertIn('CPMAP_RGI_C4_EXPORT_OK', self.control('export'))
        output, = (self.sd / 'Log').glob('cpmap-rgi-C4-*')
        self.assertEqual((output / 'events.rgj').read_bytes(), (self.capture / 'events.rgj').read_bytes())
        with (output / 'events.rgj').open('rb') as f: summary = fixtures.observer.replay(f)
        self.assertEqual(summary['end_reason'], 1)
        self.assertTrue(self.capture.is_dir())
        self.assertEqual((output / 'ipod-drvr-iap2.so').stat().st_size, 743196)

    def test_wrong_firmware_or_driver_refused_before_ram_copy(self):
        for name in ['ifs/lsd.jxe', 'mnt/app/armle/lib/dll/ipod-drvr-iap2.so']:
            p = self.root / name
            original = p.stat().st_size
            with p.open('wb') as f: f.truncate(7)
            self.control('start', 1)
            self.assertFalse((self.root / 'ramdisk/cpmap-rgi-observer-C4').exists())
            with p.open('wb') as f: f.truncate(original)

    def test_wrong_b4_marker_refused(self):
        self.marker.write_text('MU1427-iAP2-RGI-B3-bfd79ed0\n')
        self.assertIn('B4_MARKER_REQUIRED', self.control('start', 1))
        self.assertFalse(self.capture.exists())

    def test_wrong_payload_marker_and_size_refused(self):
        (self.payload / 'VERSION').write_text('wrong\n')
        self.assertIn('PAYLOAD_VERSION', self.control('start', 1))
        (self.payload / 'VERSION').write_text('C4-test\n')
        (self.payload / 'rgi-observer').write_bytes(b'bad')
        self.assertIn('PAYLOAD_SIZE', self.control('start', 1))

    def test_missing_sd_export_preserves_capture_for_retry(self):
        self.control('start')
        self.env['CPMAP_TEST_VOL'] = str(self.work / 'missing-sd')
        self.assertIn('SD_NOT_FOUND', self.control('export', 1))
        self.assertTrue((self.capture / 'events.rgj').exists())
        self.env['CPMAP_TEST_VOL'] = str(self.sd)
        self.control('export')

    def test_copy_failure_does_not_report_export_success_or_remove_ram(self):
        self.control('start')
        (self.tools / 'dd').unlink()
        (self.tools / 'dd').write_text('#!/bin/sh\nexit 1\n'); (self.tools / 'dd').chmod(0o755)
        output = self.control('export', 1)
        self.assertIn('EXPORT_COPY', output)
        self.assertNotIn('EXPORT_OK', output)
        self.assertTrue((self.capture / 'events.rgj').exists())

    def test_stop_and_remove_do_not_require_valid_driver_or_payload(self):
        self.control('start')
        self.marker.unlink()
        (self.root / 'mnt/app/armle/lib/dll/ipod-drvr-iap2.so').unlink()
        shutil.rmtree(self.payload)
        self.control('stop')
        self.control('remove')


if __name__ == '__main__': unittest.main()
