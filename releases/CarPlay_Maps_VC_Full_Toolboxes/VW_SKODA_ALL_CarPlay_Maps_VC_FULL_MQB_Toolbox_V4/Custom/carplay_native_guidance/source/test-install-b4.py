#!/usr/bin/env python3
"""B4 installer regressions, including direct upgrades from real B2 and B3.

Usage: python test-install-b4.py STOCK_DRIVER STOCK_CONFIG BUILT_B4_SD_PAYLOAD
"""
import importlib.util
from pathlib import Path
import shlex
import shutil
import unittest

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


base = module('b3_install_tests', HERE / 'test-install-b3.py')
patch = module('b3_patch', HERE / 'patch-publication.py')
B3_DATA = patch.build(base.base.STOCK_DRIVER.read_bytes())[0]


class InstallB4Tests(base.InstallB3Tests):
    def b3_active(self):
        self.install(); self.restore()
        self.driver.write_bytes(B3_DATA)
        shutil.copyfile(base.base.PAYLOAD / 'iap2.cfg', self.config)
        (self.backup / 'VERSION').write_text('MU1427-iAP2-RGI-B3-bfd79ed0\n')

    def test_direct_b3_upgrade_keeps_oem_backups_and_local_restore(self):
        self.b3_active()
        originals = [(self.backup / n).read_bytes() for n in ('stock-driver.so', 'stock-iap2.cfg')]
        self.install()
        self.assertEqual([(self.backup / n).read_bytes() for n in ('stock-driver.so', 'stock-iap2.cfg')], originals)
        self.restore(script=self.backup / 'rg-b1.sh')

    def test_wrong_b3_marker_refused_without_modification(self):
        self.b3_active()
        (self.backup / 'VERSION').write_text('unknown-build\n')
        result = self.invoke('install')
        self.assertIn('DIFFERENT_BUILD_RESTORE_FIRST', result.stdout)
        self.assertEqual(self.driver.read_bytes(), B3_DATA)
        self.restore()

    def test_b3_upgrade_second_rename_failure_restores_oem(self):
        self.b3_active()
        once = shlex.quote(str(self.root / 'failed-once'))
        stubs = self.fault('mv', f'if [ "$2" = {shlex.quote(str(self.config))} ] && [ ! -f {once} ]; then echo failed > {once}; exit 1; fi')
        result = self.invoke('install', stubs=stubs)
        self.assertIn('CONFIG_REPLACE_FAILED_STOCK_RESTORED', result.stdout)
        self.stock(); self.restore(script=self.backup / 'rg-b1.sh')


if __name__ == '__main__': unittest.main(verbosity=2)
