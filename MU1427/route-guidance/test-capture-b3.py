#!/usr/bin/env python3
"""Run all focused-collector regressions plus B3's single-read snapshot path.

Usage: python test-capture-b3.py BUILT_C3_COLLECTOR
"""
import importlib.util
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import unittest

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location('capture_tests', Path(__file__).with_name('test-capture.py'))
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
base.SCRIPT = SCRIPT


class CaptureB3Tests(base.CaptureTests):
    def setUp(self):
        super().setUp()
        self.pub = self.put('dev/ipod0/rgi-events', b'X' * 33088)

    def run_capture(self):
        p = subprocess.run([base.SHELL, str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=10)
        outs = list((self.sd / 'Log').glob('cpmap-navrecon-C3-*'))
        self.assertEqual(len(outs), 1)
        return p, outs[0]

    def test_single_full_snapshot_read(self):
        actual_dd = shutil.which('dd')
        (self.tools / 'dd').unlink()
        calls = self.root / 'snapshot-calls'
        (self.tools / 'dd').write_text(f'''#!/bin/sh
case "$1" in {shlex.quote('if=' + str(self.pub))})
    [ "$3" = bs=65536 ] && [ "$4" = count=1 ] || exit 9
    echo called >> {shlex.quote(str(calls))};;
esac
exec {shlex.quote(actual_dd)} "$@"
''')
        (self.tools / 'dd').chmod(0o755)
        result, out = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((out / 'rgi-events.bin').read_bytes(), self.pub.read_bytes())
        self.assertEqual(calls.read_text(), 'called\n')

    def test_missing_symlink_short_and_failed_snapshot_preserve_log_and_report_partial(self):
        for reason in ('missing', 'symlink', 'short', 'read'):
            with self.subTest(reason=reason):
                if self.pub.exists() or self.pub.is_symlink(): self.pub.unlink()
                if reason == 'symlink': self.pub.symlink_to(self.iap)
                elif reason == 'short': self.pub.write_bytes(b'X')
                elif reason == 'read':
                    self.pub.write_bytes(b'X' * 33088)
                    (self.tools / 'dd').unlink()
                    (self.tools / 'dd').write_text(f'''#!/bin/sh
case "$1" in {shlex.quote('if=' + str(self.pub))}) exit 11;; esac
exec {shlex.quote(shutil.which('dd'))} "$@"
''')
                    (self.tools / 'dd').chmod(0o755)
                result, out = self.run_capture()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('CPMAP_RGI_CAPTURE_PARTIAL=1', result.stdout)
                self.assertEqual((out / 'iap2.log').read_bytes(), self.iap.read_bytes())
                shutil.rmtree(out)


if __name__ == '__main__': unittest.main(verbosity=2)
